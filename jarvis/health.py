"""Bo'g'inlarning tirikligi — HUD shu ma'lumot bilan yashaydi.

Ekrandagi har bir aylanuvchi siferblat aynan bitta bo'g'inga bog'langan.
Aylanayotgani — o'sha qism ishlayapti; tezroq aylanishi — hozir ish bajaryapti;
qizarishi — buzilgan. Ya'ni ekranga bir qarabroq qayerda muammo borligi
ko'rinadi, jurnal titkilash shart emas.

Ishlatilishi:

    async with health.busy(System.STT):
        text = await stt.transcribe(audio)

Blok ichida xato chiqsa, bo'g'in avtomatik `DOWN` ga o'tadi va sabab saqlanadi.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

log = logging.getLogger("jarvis.health")


class System(StrEnum):
    """Kuzatiladigan bo'g'inlar. Qiymat — HUD'dagi siferblat identifikatori."""

    MIC = "mic"
    WAKE = "wake"
    STT = "stt"
    BRAIN = "brain"
    TTS = "tts"
    MEMORY = "memory"
    AGENDA = "agenda"
    TOOLS = "tools"
    NET = "net"


class Status(StrEnum):
    """Bo'g'in holati. HUD har biriga o'z rangi va aylanish tezligini beradi."""

    UNKNOWN = "unknown"  # hali ishlatilmagan — xira kulrang, sekin
    READY = "ready"      # tayyor, kutmoqda — siyon, sekin aylanadi
    ACTIVE = "active"    # hozir ish bajaryapti — oq-siyon, tez aylanadi
    WARN = "warn"        # ishlaydi, lekin nimadir noto'g'ri — sariq
    DOWN = "down"        # ishlamayapti — qizil, aylanish to'xtaydi


# HUD'da siferblat yonida turadigan qisqa oq yozuv.
LABELS: dict[System, str] = {
    System.MIC: "MIKROFON",
    System.WAKE: "UYG'OTISH",
    System.STT: "NUTQ",
    System.BRAIN: "MIYA",
    System.TTS: "OVOZ",
    System.MEMORY: "XOTIRA",
    System.AGENDA: "REJA",
    System.TOOLS: "ASBOB",
    System.NET: "TARMOQ",
}

# `ACTIVE` holatidan keyin siferblat shuncha soniya "qizigan" bo'lib qoladi.
# Bir zumda so'nib qolsa, ko'z ish bo'lganini ilg'amaydi.
AFTERGLOW = 1.6


@dataclass
class Reading:
    """Bitta bo'g'inning ayni damdagi holati."""

    system: System
    status: Status = Status.UNKNOWN
    detail: str = ""
    since: float = field(default_factory=time.monotonic)
    last_active: float = 0.0

    def heat(self, now: float) -> float:
        """0..1 — yaqinda qancha ish bo'lganini bildiradi (siferblat tezligi uchun)."""
        if self.status is Status.ACTIVE:
            return 1.0
        if not self.last_active:
            return 0.0
        elapsed = now - self.last_active
        return max(0.0, 1.0 - elapsed / AFTERGLOW)

    def to_dict(self, now: float) -> dict[str, Any]:
        return {
            "id": str(self.system),
            "label": LABELS[self.system],
            "status": str(self.status),
            "detail": self.detail,
            "heat": round(self.heat(now), 3),
        }


Emitter = Callable[[dict[str, Any]], Awaitable[None]]


class Health:
    """Bo'g'inlar holatining yagona reyestri.

    O'zgarish bo'lganda darhol UI'ga xabar yuboradi. Bundan tashqari
    `heartbeat()` davriy ravishda to'liq manzarani yuboradi — `heat` vaqt
    o'tishi bilan so'nadi, buni faqat davriy yangilanish ko'rsata oladi.
    """

    def __init__(self, emit: Emitter | None = None) -> None:
        self._emit = emit
        self._readings: dict[System, Reading] = {
            system: Reading(system) for system in System
        }

    def bind(self, emit: Emitter) -> None:
        """Hodisa uzatuvchini keyinroq ulash (yadro tuzilgach)."""
        self._emit = emit

    # ------------------------------------------------------------- o'qish

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            "type": "health",
            "systems": [r.to_dict(now) for r in self._readings.values()],
        }

    def status_of(self, system: System) -> Status:
        return self._readings[system].status

    def troubled(self) -> list[Reading]:
        """Muammoli bo'g'inlar — ovozli hisobot berish uchun."""
        return [
            r for r in self._readings.values()
            if r.status in (Status.WARN, Status.DOWN)
        ]

    # ------------------------------------------------------------- yozish

    async def mark(
        self, system: System, status: Status, detail: str = "", *, quiet: bool = False
    ) -> None:
        """Bo'g'in holatini o'rnatadi. O'zgarish bo'lsagina UI'ga xabar ketadi."""
        reading = self._readings[system]
        now = time.monotonic()

        if status is Status.ACTIVE:
            reading.last_active = now

        unchanged = reading.status is status and reading.detail == detail
        reading.status = status
        reading.detail = detail
        if not unchanged:
            reading.since = now
            if status is Status.DOWN:
                log.warning("Bo'g'in ishlamayapti — %s: %s", LABELS[system], detail)

        if not unchanged and not quiet:
            await self._push()

    async def ping(self, system: System) -> None:
        """Bir zumlik hodisa: siferblat chaqnaydi va o'zi so'nadi.

        `mark(ACTIVE)` dan farqi — holat `READY` bo'lib qoladi, faqat `heat`
        ko'tariladi. Boshi bor, oxiri yo'q hodisalar (mikrofonga ovoz tushishi,
        uyg'otuvchi so'z eshitilishi) uchun aynan shu kerak: aks holda
        siferblat abadiy "ishlayapti" holatida qotib qolardi.
        """
        reading = self._readings[system]
        reading.last_active = time.monotonic()
        # Nosoz bo'g'inni chaqnash tuzatib yubormasin — qizil qizilligicha qoladi.
        if reading.status is Status.UNKNOWN:
            reading.status = Status.READY
        await self._push()

    @asynccontextmanager
    async def busy(self, system: System) -> AsyncIterator[None]:
        """Ish davomida bo'g'inni `ACTIVE`, tugagach `READY` qiladi.

        Xato chiqsa `DOWN` ga o'tadi va xatoni yuqoriga o'tkazib yuboradi —
        holatni belgilash chaqiruvchining mantiqini o'zgartirmaydi.
        Bekor qilinish (`CancelledError`) nosozlik emas: bu Jarvis'ning
        o'zi ishni to'xtatgani, shuning uchun bo'g'in `READY` bo'lib qoladi.
        """
        await self.mark(system, Status.ACTIVE)
        try:
            yield
        except asyncio.CancelledError:
            await self.mark(system, Status.READY)
            raise
        except Exception as exc:
            await self.mark(system, Status.DOWN, f"{type(exc).__name__}: {exc}"[:160])
            raise
        else:
            await self.mark(system, Status.READY)

    async def _push(self) -> None:
        if self._emit is None:
            return
        try:
            await self._emit(self.snapshot())
        except Exception:
            log.exception("Holat manzarasini yuborib bo'lmadi")

    async def heartbeat(self, period: float = 1.0) -> None:
        """`heat` so'nishini ko'rsatish uchun davriy to'liq manzara.

        Faqat kimdir yaqinda ishlagan bo'lsa yuboradi — Jarvis butunlay bo'sh
        turganda tarmoqni bekorga band qilmaydi.
        """
        while True:
            await asyncio.sleep(period)
            now = time.monotonic()
            if any(r.heat(now) > 0 for r in self._readings.values()):
                await self._push()
