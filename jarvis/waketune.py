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

    results: dict[str, Measurement] = {}
    try:
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
