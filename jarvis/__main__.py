"""Jarvis yadrosi — barcha qismlarni birlashtiruvchi asosiy sikl.

Oqim:
    uyg'otish (so'z / qarsak / bosish)
        -> tinglash (VAD gapirish tugaganini aniqlaguncha)
        -> matnga aylantirish (STT)
        -> o'ylash va ish qilish (Claude Agent SDK + xavfsizlik darvozasi)
        -> gapirish (TTS, gap-gap)
        -> yana kutish
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import signal
import sys
from typing import Any

import numpy as np

from .audio.clap import ClapDetector
from .audio.mic import MicStream, frame_level
from .audio.vad import Endpointer, build_speech_detector
from .audio.wake import build_wake_detector
from .brain.agent import Brain
from .brain.memory import Memory
from .brain.prompts import ERROR_REPLY, FIRST_GREETING, GREETINGS, NOT_UNDERSTOOD
from .bus import EventBus, State
from .config import Config, load_config
from .safety.gate import SafetyGate
from .ui.server import UiServer
from .voice.stt import build_stt, transcribe_guarded
from .voice.tts import Speaker, build_tts

log = logging.getLogger("jarvis")


def chime(sample_rate: int = 24000, freq: float = 880.0, duration: float = 0.12) -> np.ndarray:
    """Uyg'onganini bildiruvchi qisqa signal.

    Fayl saqlamaymiz — generatsiya qilish arzon va o'rnatishni soddalashtiradi.
    Boshi va oxiri silliqlanadi, aks holda "chirt" eshitiladi.
    """
    t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
    wave = np.sin(2 * np.pi * freq * t)
    fade = int(sample_rate * 0.015)
    if fade * 2 < wave.size:
        wave[:fade] *= np.linspace(0.0, 1.0, fade)
        wave[-fade:] *= np.linspace(1.0, 0.0, fade)
    return (wave * 0.25 * 32767).astype(np.int16)


class Jarvis:
    """Yadro. Bitta event loop'da ishlaydi."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.bus = EventBus()
        self.memory = Memory(config.memory_path)
        self.gate = SafetyGate(config=config, bus=self.bus)
        self.brain = Brain(config=config, bus=self.bus, memory=self.memory, gate=self.gate)

        self.stt = build_stt(config.section("voice.stt"))
        self.tts = build_tts(config.section("voice.tts"))
        self.speaker = Speaker(device=config.get("audio.output_device"))

        self.ui = UiServer(
            self.bus,
            host=str(config.get("ui.host", "127.0.0.1")),
            port=int(config.get("ui.port", 8765)),
        )

        self.mic = MicStream(
            sample_rate=config.sample_rate,
            frame_samples=config.frame_samples,
            device=config.get("audio.input_device"),
            preroll_ms=int(config.get("audio.endpointing.preroll_ms", 300)),
        )

        self._wake = build_wake_detector(config.section("activation.wake_word"))
        clap_cfg = config.section("activation.clap")
        self._clap = (
            ClapDetector(
                sample_rate=config.sample_rate,
                onset_ratio=float(clap_cfg.get("onset_ratio", 8.0)),
                min_gap_sec=float(clap_cfg.get("min_gap_sec", 0.12)),
                max_gap_sec=float(clap_cfg.get("max_gap_sec", 0.70)),
                cooldown_sec=float(clap_cfg.get("cooldown_sec", 2.0)),
            )
            if clap_cfg.get("enabled", True)
            else None
        )

        self._activate = asyncio.Event()
        self._shutdown = asyncio.Event()
        self._greeted = False

    # --- Hayot sikli ---

    async def start(self) -> None:
        self.config.ensure_dirs()

        self.ui.on("activate", self._on_activate)
        self.ui.on("stop", self._on_stop)
        self.ui.on("text", self._on_text_input)

        await self.ui.start()
        await self.brain.start()
        await self.mic.start()
        await self.bus.set_state(State.IDLE)

        stats = self.memory.stats()
        log.info(
            "Jarvis tayyor — %d fakt, %d suhbat qatori xotirada",
            stats["faktlar"], stats["suhbat_qatorlari"],
        )
        await self.bus.log_line("Jarvis tayyor. «Hey Jarvis» deb chaqiring.")

    def request_stop(self) -> None:
        """Asosiy siklga to'xtash haqida xabar beradi."""
        self._shutdown.set()

    async def stop(self) -> None:
        self._shutdown.set()
        self.speaker.stop()
        await self.mic.stop()
        await self.brain.stop()
        await self.ui.stop()
        await self.stt.aclose()
        await self.tts.aclose()
        if self._wake is not None:
            self._wake.close()
        self.memory.close()
        log.info("Jarvis to'xtadi")

    # --- UI buyruqlari ---

    async def _on_activate(self, message: dict[str, Any]) -> None:
        """Orb bosildi — uyg'otuvchi so'zsiz ishga tushirish."""
        self._activate.set()

    async def _on_stop(self, message: dict[str, Any]) -> None:
        """Foydalanuvchi to'xtatdi."""
        self.speaker.stop()
        await self.brain.interrupt()
        await self.bus.set_state(State.IDLE)

    async def _on_text_input(self, message: dict[str, Any]) -> None:
        """Orb'dan matn keldi — ovozsiz rejim (shovqinli joyda foydali)."""
        text = str(message.get("text", "")).strip()
        if text:
            await self._handle_utterance(text)

    # --- Asosiy sikl ---

    async def run(self) -> None:
        await self.start()
        try:
            await self._listen_loop()
        finally:
            await self.stop()

    async def _listen_loop(self) -> None:
        """Doimiy tinglash: uyg'otuvchi so'z va qarsakni kutadi."""
        frame_count = 0

        async for frame in self.mic.frames():
            if self._shutdown.is_set():
                return

            # Jarvis gapirayotganda o'z ovozidan uyg'onmasligi kerak.
            if self.speaker.speaking:
                continue

            # Har uchinchi kadrda daraja yuboramiz — UI'ni ortiqcha yuklamaslik uchun.
            frame_count += 1
            if frame_count % 3 == 0 and self.bus.state is State.IDLE:
                await self.bus.level(frame_level(frame))

            triggered = self._activate.is_set()
            if triggered:
                self._activate.clear()
            else:
                if self._wake is not None and self._wake.push(frame):
                    triggered = True
                elif self._clap is not None and self._clap.push(frame):
                    triggered = True

            if triggered:
                await self._session()
                # Seansdan keyin buferlarni tozalaymiz — eski audio yangi
                # seansga o'tib ketmasin.
                self.mic.drain()
                if self._wake is not None:
                    self._wake.reset()
                if self._clap is not None:
                    self._clap.reset()

    async def _session(self) -> None:
        """Bitta muloqot sikli: uyg'onish -> tinglash -> javob."""
        await self.bus.set_state(State.WAKE)
        await self._play_chime()

        if not self._greeted:
            self._greeted = True
            await self._speak(
                FIRST_GREETING.format(
                    user=self.config.get("identity.user_name", ""),
                    name=self.config.get("identity.name", "Jarvis"),
                )
            )
        else:
            await self._speak(random.choice(GREETINGS))

        text = await self._capture_utterance()
        if not text:
            await self._speak(random.choice(NOT_UNDERSTOOD))
            await self.bus.set_state(State.IDLE)
            return

        await self._handle_utterance(text)

    async def _capture_utterance(self) -> str:
        """Foydalanuvchini tinglaydi va aytganini matnga aylantiradi."""
        await self.bus.set_state(State.LISTENING)

        endpoint_cfg = self.config.section("audio.endpointing")
        endpointer = Endpointer(
            detector=build_speech_detector(endpoint_cfg, self.config.sample_rate),
            frame_ms=int(self.config.get("audio.frame_ms", 20)),
            silence_ms=int(endpoint_cfg.get("silence_ms", 900)),
            max_utterance_sec=float(endpoint_cfg.get("max_utterance_sec", 30)),
        )
        endpointer.prime(self.mic.take_preroll())

        # Foydalanuvchi umuman gapirmasa, cheksiz kutib qolmaymiz.
        silence_budget = int(6_000 / max(1, int(self.config.get("audio.frame_ms", 20))))
        idle_frames = 0

        async for frame in self.mic.frames():
            if self._shutdown.is_set():
                return ""

            endpointer.push(frame)
            await self.bus.level(frame_level(frame))

            if endpointer.finished:
                break
            if not endpointer.started:
                idle_frames += 1
                if idle_frames >= silence_budget:
                    log.info("Hech kim gapirmadi, seans bekor qilindi")
                    return ""

        await self.bus.set_state(State.THINKING)
        audio = endpointer.result()
        text = await transcribe_guarded(self.stt, audio, self.config.sample_rate)

        if text:
            log.info("Eshitildi: %s", text)
            await self.bus.transcript(text)
        return text

    async def _handle_utterance(self, text: str) -> None:
        """Matnni miyaga beradi va javobni ovozga chiqaradi."""
        await self.bus.set_state(State.THINKING)
        spoke_anything = False

        try:
            async for sentence in self.brain.ask(text):
                if self._shutdown.is_set():
                    return
                spoke_anything = True
                await self._speak(sentence)
        except Exception as exc:
            log.exception("Javob olishda xato")
            await self.bus.set_state(State.ERROR)
            await self._speak(ERROR_REPLY.format(error=type(exc).__name__))
        finally:
            if not spoke_anything and self.brain.last_reply:
                await self._speak(self.brain.last_reply)
            await self.bus.set_state(State.IDLE)

    # --- Ovoz chiqarish ---

    async def _speak(self, text: str) -> None:
        """Matnni ovozga chiqaradi va UI'ga ko'rsatadi."""
        text = text.strip()
        if not text:
            return

        await self.bus.set_state(State.SPEAKING)
        await self.bus.say(text)
        log.info("Jarvis: %s", text)

        def on_level(value: float) -> None:
            # `Speaker` buni event loop oqimidan chaqiradi, shuning uchun bu yerda
            # to'g'ridan-to'g'ri vazifa yaratsa bo'ladi. Kutmaymiz: daraja yangilanishi
            # animatsiya uchun, kechiksa yoki yo'qolsa ham ijroni to'xtatmasligi kerak.
            asyncio.ensure_future(self.bus.level(value))

        try:
            await self.speaker.play(self.tts.stream(text), self.tts.sample_rate, on_level)
        except Exception:
            log.exception("Ovozga chiqarib bo'lmadi")
            await self.bus.log_line(f"[ovozsiz] {text}", level="warn")

    async def _play_chime(self) -> None:
        """Uyg'onish signalini chaladi."""

        async def one_chunk():
            yield chime(self.tts.sample_rate)

        try:
            await self.speaker.play(one_chunk(), self.tts.sample_rate)
        except Exception:
            log.debug("Signal chalinmadi", exc_info=True)


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)-22s %(message)s",
        datefmt="%H:%M:%S",
    )
    # Kutubxonalarning shovqinini pasaytiramiz
    for noisy in ("httpx", "httpcore", "websockets", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def amain(args: argparse.Namespace) -> int:
    config = load_config()
    jarvis = Jarvis(config)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def request_stop() -> None:
        log.info("To'xtatish signali olindi")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            pass  # Windows

    runner = asyncio.create_task(jarvis.run())
    waiter = asyncio.create_task(stop_event.wait())

    done, pending = await asyncio.wait({runner, waiter}, return_when=asyncio.FIRST_COMPLETED)

    if runner not in done:
        jarvis.request_stop()
        runner.cancel()
        try:
            await runner
        except asyncio.CancelledError:
            pass
    for task in pending:
        task.cancel()

    if runner in done and runner.exception() is not None:
        log.error("Jarvis yiqildi: %s", runner.exception())
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="jarvis", description="Ovozli shaxsiy AI yordamchi"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Batafsil jurnal")
    args = parser.parse_args()

    configure_logging(args.verbose)
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
