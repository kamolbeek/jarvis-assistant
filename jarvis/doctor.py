"""Diagnostika — har bir bo'g'inni alohida tekshiradi.

To'liq zanjir (mikrofon → uyg'onish → STT → miya → ovoz) birinchi marta
ishga tushganda nimadir ishlamasligi tabiiy. Hammasi birdan ishlamasa,
sababini topish qiyin — shuning uchun bu buyruq har bir qismni alohida
sinaydi va aynan qaysi bo'g'in uzilganini aytadi.

    python -m jarvis doctor
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from dataclasses import dataclass

import numpy as np

from .config import Config, load_config

# Terminal ranglari — natijani bir qarashda o'qish uchun.
GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
OK, FAIL, WARN = f"{GREEN}✓{RESET}", f"{RED}✗{RESET}", f"{YELLOW}!{RESET}"


@dataclass
class Result:
    ok: bool
    detail: str = ""
    fatal: bool = False   # True bo'lsa, keyingi tekshiruvlar ma'nosiz


def _say(mark: str, title: str, detail: str = "") -> None:
    print(f"  {mark} {title}")
    for line in detail.splitlines():
        if line.strip():
            print(f"      {DIM}{line}{RESET}")


def _header(text: str) -> None:
    print(f"\n{text}")


# ---------------------------------------------------------------- tekshiruvlar


def check_env(cfg: Config) -> Result:
    """Kalitlar joyidami?

    Miya uchun ikki yo'l bor va ikkalasi ham yaroqli: API kaliti (har so'rov
    uchun to'lov) yoki Claude Code obunasi. Claude Agent SDK ichida Claude Code
    buyrug'ini ishlatadi, shuning uchun `claude` o'rnatilgan va unga kirilgan
    bo'lsa, kalitsiz ham ishlashi mumkin. Buni faqat haqiqiy so'rov aniqlaydi,
    shuning uchun bu yerda to'xtatmaymiz — miya tekshiruvi hal qiladi.
    """
    missing: list[str] = []
    notes: list[str] = []

    if os.environ.get("ANTHROPIC_API_KEY"):
        notes.append("Miya: API kaliti")
    elif shutil.which("claude"):
        notes.append("Miya: API kaliti yo'q, Claude Code orqali sinaladi")
    else:
        missing.append(
            "ANTHROPIC_API_KEY yo'q va `claude` ham o'rnatilmagan — miya ishlamaydi.\n"
            "Yo .env ga kalit qo'ying, yo Claude Code o'rnatib obunangiz bilan kiring."
        )

    stt = str(cfg.get("voice.stt.provider", "elevenlabs"))
    tts = str(cfg.get("voice.tts.provider", "elevenlabs"))
    needed = {
        "elevenlabs": "ELEVENLABS_API_KEY",
        "mohir": "MOHIR_API_KEY",
        "azure": "AZURE_SPEECH_KEY",
    }
    for provider, role in ((stt, "STT"), (tts, "TTS")):
        key = needed.get(provider)
        if key and not os.environ.get(key):
            missing.append(f"{key} — {role} ({provider}) ishlamaydi")

    if missing:
        return Result(False, "\n".join(missing), fatal=True)
    return Result(True, "\n".join([f"STT: {stt} · TTS: {tts}", *notes]))


def check_devices(cfg: Config) -> Result:
    """Audio qurilmalari ko'rinyaptimi?"""
    try:
        import sounddevice as sd
    except Exception as exc:
        return Result(False, f"sounddevice yuklanmadi: {exc}\n"
                             f"`brew install portaudio` va qayta o'rnating", fatal=True)

    try:
        devices = sd.query_devices()
    except Exception as exc:
        return Result(False, f"Qurilmalar ro'yxati olinmadi: {exc}", fatal=True)

    inputs = [d for d in devices if d["max_input_channels"] > 0]
    if not inputs:
        return Result(False, "Kirish qurilmasi topilmadi — mikrofon ulanganmi?", fatal=True)

    try:
        default_in = sd.query_devices(kind="input")["name"]
    except Exception:
        default_in = "?"

    listing = "\n".join(f"{d['name']}" for d in inputs[:6])
    return Result(True, f"Standart mikrofon: {default_in}\n{listing}")


async def check_microphone(cfg: Config, seconds: float = 3.0) -> Result:
    """Mikrofon haqiqatan ovoz eshityaptimi?

    Faqat oqim ochilganini emas, **signal borligini** tekshiradi: macOS'da
    ruxsat berilmagan bo'lsa, oqim ochiladi-yu, faqat jimlik keladi.
    """
    from .audio.mic import MicStream, frame_level

    print(f"      {DIM}Gapiring… ({seconds:.0f} soniya){RESET}")

    mic = MicStream(
        sample_rate=cfg.sample_rate,
        frame_samples=cfg.frame_samples,
        device=cfg.get("audio.input_device"),
        gain=float(cfg.get("audio.input_gain", 1.0)),
    )

    frames: list[np.ndarray] = []
    peak = 0.0
    try:
        await mic.start()
        needed = int(seconds * cfg.sample_rate / cfg.frame_samples)
        async for frame in mic.frames():
            frames.append(frame)
            level = frame_level(frame)
            peak = max(peak, level)

            bars = int(level * 40)
            print(f"\r      [{'█' * bars}{' ' * (40 - bars)}] {level:.2f}", end="", flush=True)

            if len(frames) >= needed:
                break
    except Exception as exc:
        return Result(False, f"Mikrofon ochilmadi: {exc}", fatal=True)
    finally:
        await mic.stop()
        print()

    if peak < 0.01:
        return Result(
            False,
            "Faqat jimlik eshitildi.\n"
            "Tizim sozlamalari > Maxfiylik va xavfsizlik > Mikrofon da\n"
            "Terminal'ga (yoki iTerm'ga) ruxsat berilganini tekshiring.",
            fatal=True,
        )
    if peak < 0.06:
        return Result(True, f"Signal juda past (eng yuqori {peak:.2f}).\n"
                            f"`audio.input_gain` ni 2.0–3.0 ga ko'taring.")

    check_microphone.audio = np.concatenate(frames)  # type: ignore[attr-defined]
    return Result(True, f"Eng yuqori daraja: {peak:.2f}")


def check_wake_word(cfg: Config) -> Result:
    """Uyg'otuvchi so'z modeli yuklanadimi?"""
    section = cfg.section("activation.wake_word")
    if not section.get("enabled", True):
        return Result(True, "O'chirilgan (qarsak va tugma ishlaydi)")

    try:
        from .audio.wake import build_wake_detector

        detector = build_wake_detector(section)
        if detector is None:
            return Result(True, "O'chirilgan")
        detector.close()
    except Exception as exc:
        return Result(False, f"{type(exc).__name__}: {exc}\n"
                             f"Birinchi ishga tushirishda model yuklab olinadi — "
                             f"internet kerak.")

    return Result(True, f"Model: {section.get('model', 'hey_jarvis')} "
                        f"(chegara {section.get('threshold', 0.5)})")


async def check_stt(cfg: Config) -> Result:
    """Yozib olingan ovoz matnga aylanadimi?"""
    audio = getattr(check_microphone, "audio", None)
    if audio is None:
        return Result(False, "Mikrofon sinovi o'tmagani uchun o'tkazib yuborildi")

    from .voice.stt import build_stt, transcribe_guarded

    provider = build_stt(cfg.section("voice.stt"))
    try:
        text = await transcribe_guarded(provider, audio, cfg.sample_rate)
    finally:
        await provider.aclose()

    if not text:
        return Result(False, "Matn qaytmadi. Kalitni va provayder nomini tekshiring,\n"
                             "yoki balandroq va aniqroq gapirib qaytadan urinib ko'ring.")
    return Result(True, f"Eshitildi: «{text}»")


async def check_tts(cfg: Config) -> Result:
    """Ovoz chiqadimi va eshitiladimi?"""
    from .voice.tts import Speaker, build_tts

    phrase = "Salom. Men Jarvisman. Ovoz tekshiruvi muvaffaqiyatli o'tdi."
    provider = build_tts(cfg.section("voice.tts"))
    speaker = Speaker(device=cfg.get("audio.output_device"))

    print(f"      {DIM}Eshitilyaptimi?{RESET}")
    try:
        await speaker.play(provider.stream(phrase), provider.sample_rate)
    except Exception as exc:
        return Result(False, f"{type(exc).__name__}: {exc}")
    finally:
        await provider.aclose()

    return Result(True, f"«{phrase}»")


async def check_brain(cfg: Config) -> Result:
    """Miya javob beradimi va asboblari joyidami?"""
    try:
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
    except ImportError:
        return Result(False, "claude-agent-sdk o'rnatilmagan: pip install -e .")

    options = ClaudeAgentOptions(
        system_prompt="Sen sinov rejimidasan. Faqat o'zbek tilida, bitta qisqa gap bilan javob ber.",
        model=str(cfg.get("brain.model", "claude-opus-5")),
        max_turns=1,
    )

    parts: list[str] = []
    try:
        async for message in query(prompt="Ishlayapsanmi? Bitta gap bilan javob ber.",
                                   options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        parts.append(block.text)
    except Exception as exc:
        return Result(False, f"{type(exc).__name__}: {exc}\n"
                             f"ANTHROPIC_API_KEY to'g'rimi va balansda mablag' bormi?")

    reply = " ".join(parts).strip()
    if not reply:
        return Result(False, "Javob bo'sh keldi")
    return Result(True, f"Javob: «{reply[:120]}»")


def check_permissions() -> Result:
    """macOS ruxsatlari haqida eslatma (dasturiy tekshirib bo'lmaydi)."""
    if sys.platform != "darwin":
        return Result(True, "macOS emas — o'tkazib yuborildi")

    tools = []
    if not shutil.which("osascript"):
        tools.append("osascript topilmadi")
    if not shutil.which("shortcuts"):
        tools.append("`shortcuts` yo'q — telefon ko'prigi ishlamaydi (macOS 12+ kerak)")

    note = ("Quyidagilarni qo'lda tekshiring — Tizim sozlamalari > Maxfiylik:\n"
            "  Mikrofon           -> Terminal\n"
            "  Kirish imkoni      -> Terminal (global tugma uchun)\n"
            "  Avtomatlashtirish  -> Terminal (Messages, System Events)")
    if tools:
        note = "\n".join(tools) + "\n" + note
    return Result(True, note)


# ---------------------------------------------------------------- ishga tushirish


async def run_doctor() -> int:
    cfg = load_config()
    print(f"\n{'═' * 58}\n  Jarvis diagnostikasi\n{'═' * 58}")

    failures = 0
    stop = False

    def report(title: str, result: Result) -> None:
        nonlocal failures, stop
        _say(OK if result.ok else FAIL, title, result.detail)
        if not result.ok:
            failures += 1
            if result.fatal:
                stop = True

    _header("Sozlamalar")
    report("Kalitlar (.env)", check_env(cfg))
    report("macOS ruxsatlari", check_permissions())

    if stop:
        print(f"\n{RED}Kalitlar yo'q — qolgan tekshiruvlar o'tkazib yuborildi.{RESET}")
        print(f"{DIM}.env faylni to'ldiring va qaytadan ishga tushiring.{RESET}\n")
        return 1

    _header("Audio")
    report("Qurilmalar", check_devices(cfg))
    if not stop:
        report("Mikrofon", await check_microphone(cfg))
    report("Uyg'otuvchi so'z", check_wake_word(cfg))

    _header("Ovoz")
    if not stop:
        report("Nutqni matnga (STT)", await check_stt(cfg))
    report("Matnni ovozga (TTS)", await check_tts(cfg))

    _header("Miya")
    report("Claude Agent SDK", await check_brain(cfg))

    print(f"\n{'─' * 58}")
    if failures == 0:
        print(f"  {GREEN}Hammasi joyida.{RESET} Ishga tushiring: ./scripts/run.sh\n")
        return 0
    print(f"  {RED}{failures} ta muammo topildi.{RESET} Yuqoridagi izohlarga qarang.\n")
    return 1


def main() -> int:
    try:
        return asyncio.run(run_doctor())
    except KeyboardInterrupt:
        print()
        return 130
