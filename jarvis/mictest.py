"""Mikrofonlarni yonma-yon o'lchash: qaysi biri toza signal beradi?

Uyg'otuvchi so'z modeli signal buzilgan bo'lsa ishlamaydi — to'lqinning uchi
kesilganda u o'zi o'rgangan shaklni tanimaydi. Muammo esa ko'pincha
mikrofonning o'zida emas, TANLANGAN qurilmada yoki kirish balandligida
bo'ladi. Bu buyruq har bir kirish qurilmasini alohida tinglab, raqamlarni
yonma-yon qo'yadi va qaysi birini sozlamaga yozishni aytadi:

    python -m jarvis mic-test          # hamma qurilmani jim holatda o'lchaydi
    python -m jarvis mic-test 1        # bitta qurilmani gapirib sinaydi
"""

from __future__ import annotations

SECONDS = 2.5
RATE = 16000

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _measure(device: int, seconds: float = SECONDS):
    """Qurilmadan yozib oladi va (rms, cho'qqi, kesilish ulushi, doimiy siljish)."""
    import numpy as np
    import sounddevice as sd

    frames = int(seconds * RATE)
    audio = sd.rec(frames, samplerate=RATE, channels=1, dtype="int16", device=device)
    sd.wait()
    data = audio.reshape(-1).astype(np.int32)
    if data.size == 0:
        return 0.0, 0.0, 0.0, 0.0
    rms = float(np.sqrt(np.mean((data.astype(np.float64) / 32767.0) ** 2)))
    peak = float(np.max(np.abs(data))) / 32767.0
    clip = float(np.count_nonzero(np.abs(data) >= 32000)) / data.size
    offset = float(np.mean(data)) / 32767.0
    return rms, peak, clip, offset


def _verdict(rms: float, peak: float, clip: float, quiet: bool) -> tuple[str, str]:
    """Raqamlarni bahoga aylantiradi: (rang, izoh)."""
    if clip > 0.01 or peak >= 0.999:
        return RED, "signal kesilyapti — kirish balandligini pasaytiring"
    if quiet and rms > 0.15:
        return RED, "jim turganda ham juda shovqinli — boshqa qurilmani sinang"
    if quiet and rms > 0.05:
        return YELLOW, "shovqin bor — kirish balandligi baland"
    if quiet and rms < 0.0005:
        return YELLOW, "signal umuman yo'q — qurilma ulanmagan bo'lishi mumkin"
    if not quiet and peak < 0.05:
        return RED, "deyarli hech narsa eshitilmadi — bu qurilma ishlamayapti"
    if not quiet and peak > 0.95:
        return YELLOW, "cho'qqi juda baland — biroz pasaytiring"
    return GREEN, "toza" if quiet else "yaxshi (cho'qqi 0.5–0.8 ideal)"


def _inputs():
    import sounddevice as sd

    devices = sd.query_devices()
    return [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else []
    try:
        import sounddevice as sd  # noqa: F401
    except Exception as exc:
        print(f"sounddevice yuklanmadi: {exc}")
        print("`brew install portaudio` va `pip install -e .` ni bajaring.")
        return 1

    inputs = _inputs()
    if not inputs:
        print("Kirish qurilmasi topilmadi — mikrofon ulanganmi?")
        return 1

    # --- Bitta qurilmani gapirib sinash ---
    if argv:
        from .audio.devices import resolve_input_device

        try:
            index = resolve_input_device(argv[0])
        except ValueError as exc:
            print(exc)
            return 1
        name = next((d["name"] for i, d in inputs if i == index), None)
        if name is None:
            print(f"{index}-raqamli kirish qurilmasi yo'q")
            return 1
        print(f"\n{BOLD}{name}{RESET} — «hey jarvis» deb ayting ({SECONDS:.0f} soniya)…")
        rms, peak, clip, offset = _measure(index)
        colour, note = _verdict(rms, peak, clip, quiet=False)
        print(f"  RMS {rms:.3f}   cho'qqi {peak:.2f}   kesilish {clip * 100:.1f}%")
        print(f"  {colour}{note}{RESET}\n")
        return 0

    # --- Hamma qurilmani jim holatda o'lchash ---
    print(f"\n{BOLD}Mikrofonlarni tekshirish{RESET}")
    print(f"{DIM}Har bir qurilma {SECONDS:.0f} soniya tinglanadi — iltimos, JIM turing.{RESET}\n")

    rows = []
    for index, device in inputs:
        name = str(device["name"])
        print(f"  {index}. {name} … ", end="", flush=True)
        try:
            rms, peak, clip, offset = _measure(index)
        except Exception as exc:
            print(f"{RED}ochilmadi{RESET} {DIM}({exc}){RESET}")
            continue
        colour, note = _verdict(rms, peak, clip, quiet=True)
        print(f"RMS {rms:.3f}  cho'qqi {peak:.2f}  kesilish {clip * 100:.1f}%  "
              f"{colour}{note}{RESET}")
        rows.append((index, name, rms, peak, clip))

    # O'lik qurilma ham "jim" ko'rinadi — uni tavsiya qilmaymiz
    healthy = [r for r in rows
               if r[4] <= 0.01 and r[3] < 0.999 and 0.0005 <= r[2] <= 0.05]
    print()
    if not rows:
        print(f"{RED}Hech bir qurilma ochilmadi.{RESET}")
        return 1
    if healthy:
        index, name, *_ = min(healthy, key=lambda r: r[2])
        print(f"{GREEN}Eng tozasi: {index}. {name}{RESET}")
        print(f"{DIM}Sozlamaga yozish — config/jarvis.yaml:{RESET}")
        print("    audio:")
        print(f'      input_device: "{name}"')
        # Raqam qulayroq, lekin u qurilmalar ulanganda siljib ketadi
        # (masalan iPhone yaqin kelsa) — shuning uchun nom ustun turadi.
        print(f'{DIM}      # yoki raqami bilan: input_device: {index}{RESET}')
        print(f"\n{DIM}Keyin gapirib sinang:{RESET}  python -m jarvis mic-test {index}")
    else:
        print(f"{RED}Hamma qurilmada signal buzuq ko'rinyapti.{RESET}")
        print("Odatda sabab bitta: kirish balandligi juda baland.")
        print("  Tizim sozlamalari > Ovoz > Kirish > «Kirish balandligi»ni yarmiga tushiring")
        print("  va shu buyruqni qaytadan ishga tushiring.")
    return 0
