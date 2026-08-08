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


async def measure(phrase: str, cfg, detector, threshold: float, candidate: float) -> float:
    """Bitta iborani tinglaydi va eng yuqori ballni qaytaradi."""
    from .audio.mic import MicStream, frame_level

    print(f"\n{BOLD}«{phrase}»{RESET} deb ayting — {LISTEN_SEC:.0f} soniya "
          f"{DIM}(bir necha marta aytsangiz yaxshi){RESET}")

    mic = MicStream(
        sample_rate=cfg.sample_rate,
        frame_samples=cfg.frame_samples,
        device=cfg.get("audio.input_device"),
        gain=float(cfg.get("audio.input_gain", 1.0)),
    )

    detector.clear_peak()
    fired = 0
    loud = 0.0
    needed = int(LISTEN_SEC * cfg.sample_rate / cfg.frame_samples)

    await mic.start()
    try:
        seen = 0
        async for frame in mic.frames():
            seen += 1
            loud = max(loud, frame_level(frame))
            if detector.push(frame) is not None:
                fired += 1

            score = detector.peak
            tint = colour(score, threshold, candidate)
            print(f"\r  ball {tint}{score:.3f}{RESET} [{tint}{bar(score)}{RESET}] "
                  f"ovoz {loud:.2f}", end="", flush=True)

            if seen >= needed:
                break
    finally:
        await mic.stop()
        print()

    if fired:
        print(f"  {GREEN}{fired} marta ishga tushdi{RESET}")
    return detector.peak


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

    results: dict[str, float] = {}
    try:
        for phrase in phrases:
            results[phrase] = await measure(phrase, cfg, detector, threshold, candidate)
    finally:
        detector.close()

    print(f"\n{BOLD}Natija{RESET}")
    for phrase, peak in results.items():
        if peak >= threshold:
            verdict = f"{GREEN}darhol uyg'onadi{RESET}"
        elif peak >= candidate:
            verdict = f"{AMBER}matn bilan tekshiriladi (STT, ~0.5 s){RESET}"
        else:
            verdict = f"{RED}sezilmadi{RESET}"
        print(f"  {peak:.3f}  «{phrase}» — {verdict}")

    # Tavsiya: model umuman sezmagan iboralar uchun chegarani pasaytirish
    # ma'nosiz — u shovqin darajasiga tushib ketadi.
    weak = [p for p, v in results.items() if v < candidate]
    strong = [v for v in results.values() if v >= candidate]

    print()
    if strong:
        floor = min(strong)
        suggested = max(0.05, round(floor * 0.6, 2))
        print(f"{DIM}Eng past sezilgan ball: {floor:.3f}. "
              f"`candidate_threshold: {suggested}` qo'yib ko'ring.{RESET}")
    if weak:
        print(f"{AMBER}Model bu iboralarni umuman sezmadi: "
              f"{', '.join(weak)}{RESET}")
        print(f"{DIM}Chegarani 0.05 dan pastga tushirish yaramaydi — shovqin ham\n"
              f"o'tib ketadi va har safar STT chaqiriladi. Bu iboralar uchun\n"
              f"o'z modelini o'rgatish kerak (README: «To'liq lokal yechim»)\n"
              f"yoki Porcupine bilan tayyor ibora yasash.{RESET}")
    if not weak:
        print(f"{GREEN}Uch xil chaqiruvning hammasi ishlaydi.{RESET}")

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
