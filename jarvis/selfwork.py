"""O'z ustida ishlash — Jarvisning o'z kodini o'zgartirishi.

G'oya oddiy: «bu menga yoqmadi» deganingizda javob «xo'p, keyingi versiyada»
emas, balki HOZIR tuzatish bo'lishi kerak. Jarvisning kodi shu kompyuterda
turibdi, u esa kod yoza oladi — demak o'zini o'zi tuzata oladi.

Uchta narsa buni xavfsiz qiladi:

1. **Ko'rinadigan belgi.** O'z ustida ishlayotganda orbda «O'Z USTIDA ISHLAMOQDA»
   yozuvi turadi. Bu paytda gapirsangiz, gapingiz behuda ketadi — sahna band.
   Shuning uchun belgi ish boshlanishida yoqiladi, tugaganda o'chadi.

2. **Git.** Har o'zgarishdan oldin holat suratga olinadi. Yangi xatti-harakat
   yoqmasa yoki Jarvis butunlay ishlamay qolsa, bitta gap bilan orqaga
   qaytariladi — `git checkout` esa hech qanday «tuzatishga urinish» dan
   ishonchliroq.

3. **Tekshiruv.** O'zgarish kiritilgach testlar va linter ishga tushadi.
   Ular yiqilsa, qayta ishga tushirish taklif qilinmaydi: buzuq kod bilan
   qayta ishga tushish — Jarvisni umuman yo'qotish demak.

Qayta ishga tushirish `os.execv` orqali bo'ladi: jarayon o'zini o'zi almashtiradi.
Shuning uchun `run.sh` ostidagi orb ham, launchd ostidagi kuzatuv ham buzilmaydi —
tashqaridan qaraganda jarayon o'sha-o'sha, faqat ichidagi kod yangilangan.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

from .config import REPO_ROOT, expand

log = logging.getLogger("jarvis.selfwork")

# Kamchiliklar daftari. Jarvis o'zi sezgan xatolar ham, sizning
# «bu yoqmadi» degan gaplaringiz ham shu yerga tushadi.
JOURNAL_PATH = expand("~/.jarvis/improvements.jsonl")

# Bitta yozuvning eng ko'p uzunligi — daftar cheksiz o'smasin.
MAX_TEXT = 2000

# Yozuv turlari: shikoyat — foydalanuvchi aytgan; xato — Jarvis o'zi sezgan;
# bajarildi — tuzatilgan (o'sha matnli ochiq yozuvlarni yopadi).

# Tekshiruv buyruqlari. Tartib muhim: testlar asosiy, linter qo'shimcha.
CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("testlar", [sys.executable, "-m", "pytest", "tests/", "-q"]),
    ("linter", [sys.executable, "-m", "ruff", "check", "jarvis", "tests"]),
)


def stamp() -> str:
    """Joriy vaqt — daftar yozuvlari uchun."""
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def note(kind: str, text: str, detail: str = "") -> None:
    """Daftarga yozadi. Yiqilmaydi — kamchilik yozuvi tufayli Jarvis to'xtamasin."""
    entry = {
        "ts": stamp(),
        "kind": kind,
        "text": str(text)[:MAX_TEXT],
        "detail": str(detail)[:MAX_TEXT],
        "done": False,
    }
    try:
        JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        log.exception("Kamchiliklar daftariga yozib bo'lmadi")


def _read_all() -> list[dict]:
    if not JOURNAL_PATH.exists():
        return []
    rows: list[dict] = []
    try:
        with JOURNAL_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        log.exception("Kamchiliklar daftarini o'qib bo'lmadi")
    return rows


def open_issues(limit: int = 20) -> list[dict]:
    """Hali tuzatilmagan kamchiliklar (yangisidan eskisiga).

    Bir xil xato qayta-qayta yozilishi mumkin (masalan har safar STT yiqilganda),
    shuning uchun takrorlanadigan matnlar birlashtiriladi va nechinchi marta
    uchragani ko'rsatiladi — eng ko'p takrorlangani eng muhim kamchilik.
    """
    merged: dict[str, dict] = {}
    for row in _read_all():
        if row.get("done"):
            merged.pop(row.get("text", ""), None)
            continue
        key = str(row.get("text", ""))
        if key in merged:
            merged[key]["marta"] += 1
            merged[key]["ts"] = row.get("ts", "")
        else:
            merged[key] = {
                "vaqt": row.get("ts", ""),
                "ts": row.get("ts", ""),
                "turi": row.get("kind", ""),
                "matn": key,
                "izoh": row.get("detail", ""),
                "marta": 1,
            }
    rows = sorted(merged.values(), key=lambda r: r["ts"], reverse=True)
    for row in rows:
        row.pop("ts", None)
    return rows[:limit]


def close_issue(text: str) -> bool:
    """Kamchilikni bajarilgan deb belgilaydi."""
    needle = str(text).strip().casefold()
    match = next(
        (r for r in _read_all()
         if not r.get("done") and needle and needle in str(r.get("text", "")).casefold()),
        None,
    )
    if match is None:
        return False
    try:
        JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(
                {"ts": stamp(), "kind": "bajarildi", "text": match.get("text", ""),
                 "detail": "", "done": True},
                ensure_ascii=False,
            ) + "\n")
    except OSError:
        log.exception("Daftarga yozib bo'lmadi")
        return False
    return True


# ---------------------------------------------------------------- git va tekshiruv


async def _run(
    command: list[str], cwd: Path | None = None, timeout: float = 300.0
) -> tuple[int, str]:
    """Buyruqni bajaradi va (kod, chiqish) qaytaradi."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd or REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        return 124, f"«{' '.join(command[:3])}» juda uzoq ishladi va to'xtatildi"
    return process.returncode or 0, stdout.decode("utf-8", "replace")


async def git_status() -> str:
    """Kodning hozirgi holati: shox va saqlanmagan o'zgarishlar."""
    _, branch = await _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    code, changes = await _run(["git", "status", "--short"])
    if code != 0:
        return "Git ishlamadi — kod nazoratsiz o'zgartirilyapti"
    changed = [line for line in changes.splitlines() if line.strip()]
    if not changed:
        return f"Shox: {branch.strip()}. Saqlanmagan o'zgarish yo'q."
    return f"Shox: {branch.strip()}. Saqlanmagan o'zgarishlar:\n" + "\n".join(changed[:40])


async def snapshot(reason: str) -> str:
    """O'zgarishdan oldingi holatni git'ga saqlaydi.

    Yangi commit qilinadi, chunki `stash` ni keyin ochish kerak bo'ladi va uni
    unutib qo'yish oson. Commit esa tarixda qoladi: nima o'zgargani va qachon
    o'zgargani hamisha ko'rinadi.
    """
    code, changes = await _run(["git", "status", "--porcelain"])
    if code != 0:
        return "Git yo'q — surat olinmadi"
    if not changes.strip():
        return "Saqlanmagan o'zgarish yo'q — surat kerak emas"

    await _run(["git", "add", "-A"])
    message = f"jarvis: {reason[:60]} (o'z-o'zini o'zgartirishdan oldingi holat)"
    code, out = await _run(["git", "commit", "-m", message])
    if code != 0:
        return f"Surat olinmadi: {out.strip()[:200]}"
    return "Oldingi holat git'ga saqlandi"


async def revert() -> str:
    """Saqlanmagan barcha o'zgarishlarni bekor qiladi — «orqaga qaytar»."""
    code, out = await _run(["git", "checkout", "--", "."])
    if code != 0:
        return f"Qaytarib bo'lmadi: {out.strip()[:200]}"
    await _run(["git", "clean", "-fd", "jarvis", "ui", "tests"])
    return "Oxirgi o'zgarishlar bekor qilindi. Qayta ishga tushirish kerak."


async def run_checks() -> tuple[bool, str]:
    """Testlar va linterni ishga tushiradi. (hammasi_joyidami, hisobot)."""
    report: list[str] = []
    ok = True
    for name, command in CHECKS:
        code, output = await _run(command)
        if code == 0:
            report.append(f"{name}: joyida")
            continue
        ok = False
        tail = "\n".join(output.strip().splitlines()[-25:])
        report.append(f"{name}: YIQILDI\n{tail}")
    return ok, "\n\n".join(report)


# ---------------------------------------------------------------- qayta ishga tushirish


def restart_command() -> list[str]:
    """Jarayonni almashtirish uchun buyruq."""
    return [sys.executable, "-m", "jarvis", *sys.argv[1:]]


def restart_now() -> None:
    """Jarayonni o'zini o'zi almashtiradi. Bu funksiya qaytmaydi."""
    command = restart_command()
    log.warning("Qayta ishga tushirilmoqda: %s", " ".join(command))
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(command[0], command)


def schedule_restart(delay: float = 2.0) -> None:
    """Javob aytilib bo'lgach qayta ishga tushiradi.

    Darhol almashtirsak, foydalanuvchi «qayta ishga tushiryapman» degan gapni
    eshitmay qoladi — jarayon gap tugamasdan o'ladi. Shuning uchun kichik
    kechikish qo'yiladi.
    """
    loop = asyncio.get_running_loop()
    loop.call_later(max(0.5, delay), restart_now)
