"""`jarvis wake-test` — chaqiruv ballini jonli o'lchash.

Nima uchun kerak: uyg'otuvchi so'z modeli har bir ovoz, mikrofon va xonada
boshqacha ball beradi. Chegarani hujjatdagi raqam bilan emas, aynan shu
mashinadagi o'lchov bilan qo'yish kerak.

Ishlatilishi: buyruqni ishga tushirasiz, har bir iborani bir necha marta
aytasiz, ekranda ball jonli ko'rinadi. Oxirida har bir ibora uchun eng
yuqori ball va tavsiya qilingan chegara chiqadi.

Diagnostikadan farqi: `doctor` bitta yozuvni tekshiradi va "ishlaydi/yo'q"
deydi. Bu esa sozlash asbobi — raqam beradi.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from dataclasses import dataclass

from .config import load_config

BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
AMBER = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"

# Har bir ibora uchun shuncha soniya tinglaymiz.
LISTEN_SEC = 6.0


def bar(score: float, width: int = 34) -> str:
    filled = int(min(1.0, max(0.0, score)) * width)
    return "█" * filled + " " * (width - filled)


def colour(score: float, threshold: float, candidate: float) -> str:
    if score >= threshold:
        return GREEN
    if score >= candidate:
        return AMBER
    return DIM


@dataclass
class Measurement:
    """Bitta ibora uchun o'lchov natijasi."""

    peak: float = 0.0          # modelning eng yuqori bali
    loudest: float = 0.0       # eng baland namuna (to'liq shkalaning ulushi)
    clipped: float = 0.0       # kesilgan namunalar ulushi
    confident: int = 0         # chegaradan o'tgan chaqiruvlar
    candidates: int = 0        # faqat shubhali chegaradan o'tganlar

    @property
    def distorted(self) -> bool:
        """Signal buzilganmi? Shunda ball haqida gapirish ma'nosiz."""
        return self.clipped > 0.005


async def measure(phrase: str, cfg, detector, threshold: float,
                  candidate: float) -> Measurement:
    """Bitta iborani tinglaydi va o'lchovni qaytaradi."""
    from .audio.mic import MicStream, clip_fraction, frame_peak

    print(f"\n{BOLD}«{phrase}»{RESET} deb ayting — {LISTEN_SEC:.0f} soniya "
          f"{DIM}(bir necha marta aytsangiz yaxshi){RESET}")

    mic = MicStream(
        sample_rate=cfg.sample_rate,
        frame_samples=cfg.frame_samples,
        device=cfg.get("audio.input_device"),
        gain=float(cfg.get("audio.input_gain", 1.0)),
    )

    # Model ichida oxirgi ~2 soniyaning izi qoladi. Tozalamasak, oldingi
    # iboradan qolgan quyruq keyingisining hisobiga yozilib, natijalar
    # o'rin almashib ketadi — aynan shu chalkashlikni ko'rdik.
    detector.reset()
    detector.clear_peak()

    out = Measurement()
    clipped_frames = 0
    needed = int(LISTEN_SEC * cfg.sample_rate / cfg.frame_samples)
    settle = int(0.4 * cfg.sample_rate / cfg.frame_samples)

    await mic.start()
    try:
        seen = 0
        async for frame in mic.frames():
            seen += 1
            # Oqim ochilgandagi birinchi kadrlarda "chirt" bo'ladi — hisobga olmaymiz.
            if seen <= settle:
                continue

            out.loudest = max(out.loudest, frame_peak(frame))
            if clip_fraction(frame) > 0.02:
                clipped_frames += 1

            hit = detector.push(frame)
            if hit is not None:
                if hit.confident:
                    out.confident += 1
                else:
                    out.candidates += 1

            tint = colour(detector.peak, threshold, candidate)
            warn = f" {RED}KESILYAPTI{RESET}" if clipped_frames else ""
            print(f"\r  ball {tint}{detector.peak:.3f}{RESET} "
                  f"[{tint}{bar(detector.peak)}{RESET}] "
                  f"cho'qqi {out.loudest:.2f}{warn}   ", end="", flush=True)

            if seen >= needed:
                break
    finally:
        await mic.stop()
        print()

    out.peak = detector.peak
    out.clipped = clipped_frames / max(1, needed - settle)

    if out.confident:
        print(f"  {GREEN}{out.confident} marta darhol uyg'ondi{RESET}")
    if out.candidates:
        print(f"  {AMBER}{out.candidates} marta shubhali deb belgilandi{RESET}")
    if out.distorted:
        print(f"  {RED}Ovoz kesilib buzilgan — bu balllarga ishonib bo'lmaydi{RESET}")
    return out


async def synth(cfg, text: str) -> tuple:
    """TTS bilan iborani sintez qiladi. Qaytadi: (audio, sample_rate)."""
    import numpy as np

    from .voice.tts import build_tts

    provider = build_tts(cfg.section("voice.tts"))
    try:
        chunks = [chunk async for chunk in provider.stream(text) if chunk.size]
    finally:
        await provider.aclose()
    if not chunks:
        return np.zeros(0, dtype=np.int16), provider.sample_rate
    return np.concatenate(chunks), provider.sample_rate


async def check_pipeline(cfg, detector) -> float:
    """Quvur sinovi: TTS aytgan «hey jarvis» ni to'g'ridan-to'g'ri modelga beramiz.

    Bu yerda mikrofon, xona va talaffuz qatnashmaydi. Ball baland chiqsa,
    kod va model joyida — muammoni tashqarida qidirish kerak. Past chiqsa,
    muammo aynan shu yerda va mikrofonni sozlashning ma'nosi yo'q.
    """
    from .audio.mic import resample

    audio, rate = await synth(cfg, "Hey Jarvis")
    if audio.size == 0:
        return -1.0
    converted = resample(audio, rate, cfg.sample_rate)
    return detector.scan(converted, cfg.frame_samples)


async def check_room(cfg, detector) -> tuple[float, float]:
    """Xona sinovi: TTS dinamikdan chalinadi, mikrofon eshitadi.

    Quvur sinovi o'tib, bu o'tmasa — muammo mikrofon yo'lida yoki xonada.
    Qaytadi: (ball, cho'qqi).
    """
    import numpy as np

    from .audio.mic import MicStream, frame_peak
    from .voice.tts import Speaker

    audio, rate = await synth(cfg, "Hey Jarvis")
    if audio.size == 0:
        return -1.0, 0.0

    mic = MicStream(
        sample_rate=cfg.sample_rate,
        frame_samples=cfg.frame_samples,
        device=cfg.get("audio.input_device"),
        gain=float(cfg.get("audio.input_gain", 1.0)),
    )
    speaker = Speaker(device=cfg.get("audio.output_device"))

    async def one_chunk():
        yield audio

    frames: list = []
    loudest = 0.0

    await mic.start()

    async def collect() -> None:
        nonlocal loudest
        async for frame in mic.frames():
            frames.append(frame)
            loudest = max(loudest, frame_peak(frame))

    reader = asyncio.create_task(collect())
    try:
        await speaker.play(one_chunk(), rate)
        # Oxirgi kadrlar navbatda qolmasin
        await asyncio.sleep(0.3)
    finally:
        reader.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reader
        await mic.stop()

    if not frames:
        return -1.0, 0.0
    heard = np.concatenate(frames)
    return detector.scan(heard, cfg.frame_samples), loudest


async def run() -> int:
    cfg = load_config()
    section = cfg.section("activation.wake_word")
    threshold = float(section.get("threshold", 0.5))
    candidate = float(section.get("candidate_threshold", threshold))
    phrases = [str(p) for p in (section.get("phrases") or ["hey jarvis"])]

    print(f"\n{CYAN}{BOLD}Chaqiruv ballini o'lchash{RESET}")
    print(f"{DIM}Model: {section.get('model', 'hey_jarvis')} · "
          f"chegara {threshold:.2f} · shubhali {candidate:.2f}{RESET}")
    print(f"{DIM}Yashil = darhol uyg'onadi · sariq = matn bilan tekshiriladi · "
          f"xira = sezilmadi{RESET}")

    print(f"\n{DIM}Model yuklanmoqda…{RESET}")
    from .audio.wake import build_wake_detector

    detector = await asyncio.to_thread(build_wake_detector, section)
    if detector is None:
        print(f"{RED}Uyg'otuvchi so'z o'chirilgan "
              f"(activation.wake_word.enabled: false){RESET}")
        return 1

    # Avval quvurni o'zini tekshiramiz. Bu tartib muhim: agar model tayyor
    # yozuvni ham tanimasa, mikrofonni sozlash bilan vaqt yo'qotish behuda.
    pipeline = room = -1.0
    room_loud = 0.0
    results: dict[str, Measurement] = {}
    try:
        print(f"\n{BOLD}1. Quvur sinovi{RESET} {DIM}— TTS aytadi, to'g'ridan-to'g'ri "
              f"modelga beriladi (mikrofon qatnashmaydi){RESET}")
        try:
            pipeline = await check_pipeline(cfg, detector)
        except Exception as exc:  # noqa: BLE001 — sinov o'tmasa ham davom etamiz
            print(f"  {AMBER}O'tkazib yuborildi: {type(exc).__name__}: {exc}{RESET}")
        else:
            tint = colour(pipeline, threshold, candidate)
            print(f"  ball {tint}{pipeline:.3f}{RESET} [{tint}{bar(pipeline)}{RESET}]")

        print(f"\n{BOLD}2. Xona sinovi{RESET} {DIM}— TTS dinamikdan chalinadi, "
              f"mikrofon eshitadi{RESET}")
        try:
            room, room_loud = await check_room(cfg, detector)
        except Exception as exc:  # noqa: BLE001
            print(f"  {AMBER}O'tkazib yuborildi: {type(exc).__name__}: {exc}{RESET}")
        else:
            tint = colour(room, threshold, candidate)
            print(f"  ball {tint}{room:.3f}{RESET} [{tint}{bar(room)}{RESET}] "
                  f"cho'qqi {room_loud:.2f}")

        print(f"\n{BOLD}3. Sizning ovozingiz{RESET}")
        for phrase in phrases:
            results[phrase] = await measure(phrase, cfg, detector, threshold, candidate)
    finally:
        detector.close()

    print(f"\n{BOLD}Natija{RESET}")
    for phrase, m in results.items():
        if m.peak >= threshold:
            verdict = f"{GREEN}darhol uyg'onadi{RESET}"
        elif m.peak >= candidate:
            verdict = f"{AMBER}matn bilan tekshiriladi (STT, ~0.5 s){RESET}"
        else:
            verdict = f"{RED}sezilmadi{RESET}"
        print(f"  {m.peak:.3f}  «{phrase}» — {verdict}"
              f"{DIM}  (cho'qqi {m.loudest:.2f}){RESET}")

    print()

    # Signal buzilgan bo'lsa, ballar haqida xulosa chiqarish yaramaydi —
    # avval mikrofonni tuzatish kerak, keyin qaytadan o'lchash.
    distorted = [p for p, m in results.items() if m.distorted]
    if distorted:
        worst = max(m.clipped for m in results.values())
        print(f"{RED}{BOLD}Ovoz kesilib buzilgan "
              f"(kadrlarning {worst * 100:.0f}%){RESET}")
        print(f"{DIM}Kesilganda to'lqinning uchi yo'qoladi va model o'zi\n"
              f"o'rgangan shaklni tanimaydi — shuning uchun bir xil ibora\n"
              f"har safar boshqa ball oladi. Yuqoridagi raqamlar ishonchsiz.\n"
              f"\n"
              f"Tuzatish: Tizim sozlamalari > Ovoz > Kirish — «Kirish\n"
              f"balandligi» surgichini o'rtaga tushiring. Keyin shu buyruqni\n"
              f"qaytadan ishga tushiring: cho'qqi 0.5–0.8 orasida bo'lsa yaxshi,\n"
              f"1.00 bo'lsa — hali baland.{RESET}")
        return 1

    quiet = [p for p, m in results.items() if m.loudest < 0.08]
    if quiet:
        print(f"{AMBER}Signal juda past: {', '.join(quiet)}{RESET}")
        print(f"{DIM}Kirish balandligini ko'taring yoki mikrofonga yaqinroq "
              f"gapiring.{RESET}")
        return 1

    # Uch sinovni solishtirib, aybdorni ko'rsatamiz. Har bir shart alohida
    # xulosa beradi — "nimadir ishlamayapti" degan gap foyda keltirmaydi.
    best_voice = max((m.peak for m in results.values()), default=0.0)

    if 0 <= pipeline < candidate:
        print(f"{RED}{BOLD}Model tayyor yozuvni ham tanimadi{RESET}")
        print(f"{DIM}Mikrofon, xona va talaffuz bu sinovda qatnashmagan — demak\n"
              f"muammo modelda yoki uni ishlatishimizda. Mikrofonni sozlash\n"
              f"foyda bermaydi. Modelni qaytadan yuklab ko'ring:\n"
              f"  rm -rf .venv/lib/python3*/site-packages/openwakeword/resources/models\n"
              f"so'ng shu buyruqni qaytadan ishga tushiring.{RESET}")
        return 1

    if pipeline >= candidate and 0 <= room < candidate:
        print(f"{AMBER}{BOLD}Quvur ishlaydi, lekin mikrofon orqali tanilmadi{RESET}")
        print(f"{DIM}TTS ovozi to'g'ridan-to'g'ri berilganda {pipeline:.3f}, xuddi\n"
              f"o'sha ovoz dinamik va mikrofon orqali kelganda {room:.3f}.\n"
              f"Demak muammo mikrofon yo'lida: dinamik juda past bo'lishi,\n"
              f"mikrofon boshqa qurilma bo'lishi yoki xona shovqini sabab.\n"
              f"Cho'qqi {room_loud:.2f} — 0.2 dan past bo'lsa, ovoz shunchaki\n"
              f"yetib bormagan.{RESET}")
        return 1

    if pipeline >= candidate and room >= candidate and best_voice < candidate:
        print(f"{AMBER}{BOLD}Model ishlaydi, lekin sizning talaffuzingizni "
              f"tanimaydi{RESET}")
        print(f"{DIM}TTS ovozini mikrofon orqali ham tanidi ({room:.3f}), sizning\n"
              f"ovozingizda esa eng yuqori ball {best_voice:.3f}. Bu model faqat\n"
              f"inglizcha sintetik ovozlarda o'rgatilgan — boshqa talaffuzda\n"
              f"ball keskin tushadi. Chegarani pasaytirish yechim emas.\n"
              f"\n"
              f"Ishlaydigan yo'l — o'z ovozingizda model yasash yoki\n"
              f"uyg'otuvchi so'zni butunlay boshqa usulga o'tkazish.\n"
              f"README: «To'liq lokal yechim».{RESET}")
        return 1

    # Model umuman sezmagan iboralar uchun chegarani pasaytirish ma'nosiz —
    # u shovqin darajasiga tushib ketadi.
    weak = [p for p, m in results.items() if m.peak < candidate]
    strong = [m.peak for m in results.values() if m.peak >= candidate]

    if strong:
        floor = min(strong)
        suggested = max(0.05, round(floor * 0.6, 2))
        print(f"{DIM}Eng past sezilgan ball: {floor:.3f}. "
              f"`candidate_threshold: {suggested}` qo'yib ko'ring.{RESET}")
    if weak:
        print(f"{AMBER}Model bu iboralarni sezmadi: {', '.join(weak)}{RESET}")
        print(f"{DIM}Chegarani 0.05 dan pastga tushirish yaramaydi — shovqin ham\n"
              f"o'tib ketadi va har safar STT chaqiriladi. Bu iboralar uchun\n"
              f"o'z modelini o'rgatish kerak (README: «To'liq lokal yechim»)\n"
              f"yoki Porcupine bilan tayyor ibora yasash.{RESET}")
    else:
        print(f"{GREEN}Hamma chaqiruv ishlaydi.{RESET}")

    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # noqa: BLE001 — foydalanuvchiga sabab ko'rinishi kerak
        print(f"\n{RED}{type(exc).__name__}: {exc}{RESET}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main())
