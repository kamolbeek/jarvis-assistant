"""Hodisa shinasi — yadro bilan orb (UI) o'rtasidagi yagona aloqa nuqtasi.

Yadro holat o'zgarishlarini shu yerga yozadi, UI serveri ularni WebSocket orqali
orb'ga uzatadi. Tasdiq so'rovlari ham shu yerdan o'tadi.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

log = logging.getLogger("jarvis.bus")


class State(StrEnum):
    """Jarvis'ning ko'rinadigan holatlari — orb shu holatlarga qarab rang/animatsiya oladi."""

    IDLE = "idle"           # kutmoqda, xira pulsatsiya
    WAKE = "wake"           # endi uyg'ondi, bir zumlik yorqin chaqnash
    LISTENING = "listening" # tinglayapti, to'lqin animatsiyasi
    THINKING = "thinking"   # o'ylayapti, aylanish
    SPEAKING = "speaking"   # gapiryapti, ovozga mos pulsatsiya
    CONFIRM = "confirm"     # tasdiq kutmoqda, sariq
    ERROR = "error"         # xato, qizil


@dataclass
class PendingConfirm:
    """Foydalanuvchidan tasdiq kutayotgan amal."""

    id: str
    action: str
    detail: str
    future: asyncio.Future[bool]


Subscriber = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class EventBus:
    """Yagona nashr-obuna shinasi. Thread-safe emas — hammasi bitta event loop'da."""

    _subscribers: list[Subscriber] = field(default_factory=list)
    _pending: dict[str, PendingConfirm] = field(default_factory=dict)
    state: State = State.IDLE
    # Sukut holati holatlar qatoriga kirmaydi (yadro baribir IDLE da
    # tinglaydi), lekin yangi ulangan mijoz uni bilishi kerak — aks holda
    # orb yashiringan bo'lsa ham qaytadan chiqib qolardi.
    standby_on: bool = False
    # Bo'sh bo'lmasa — Jarvis uzoq, o'zi boshqaradigan ish bilan band
    # (masalan o'z kodini o'zgartiryapti). Orbda yozuv bo'lib turadi.
    working: str = ""
    # Hozir aynan nima qilinyapti (asbob nomi, bosqich) va oxirgi nosozlik.
    # Ikkalasi ham ekranda turadi — jimlikning sababi ko'rinmay qolmasin.
    activity_text: str = ""
    problem_text: str = ""

    def subscribe(self, callback: Subscriber) -> Callable[[], None]:
        """Obuna bo'ladi. Qaytgan funksiyani chaqirib obunani bekor qilish mumkin."""
        self._subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe

    async def emit(self, event: dict[str, Any]) -> None:
        """Hodisani barcha obunachilarga yuboradi.

        Bitta obunachi yiqilsa, qolganlari davom etadi.
        """
        for callback in list(self._subscribers):
            try:
                await callback(event)
            except Exception:
                log.exception("Obunachi hodisani qayta ishlashda yiqildi")

    # --- Qulaylik metodlari ---

    async def set_state(self, state: State, **extra: Any) -> None:
        # Yangi bosqich boshlandi — oldingi asbobning nomi ekranda qolib
        # ketmasin, aks holda «hali ham Telegramda ishlayapti» degan
        # noto'g'ri taassurot qoladi.
        if self.activity_text and state is not State.THINKING:
            self.activity_text = ""
            await self.emit({"type": "activity", "text": ""})
        self.state = state
        await self.emit({"type": "state", "state": str(state), **extra})

    async def level(self, value: float) -> None:
        """Mikrofon darajasi (0..1) — to'lqin animatsiyasi uchun."""
        await self.emit({"type": "level", "value": round(float(value), 4)})

    async def transcript(self, text: str, *, final: bool = True) -> None:
        await self.emit({"type": "transcript", "text": text, "final": final})

    async def say(self, text: str) -> None:
        """Jarvis nima deyayotganini UI'ga ko'rsatish uchun."""
        await self.emit({"type": "say", "text": text})

    async def log_line(self, text: str, level: str = "info") -> None:
        await self.emit({"type": "log", "level": level, "text": text})

    async def work(self, text: str) -> None:
        """«Band» belgisini yoqadi/o'chiradi. Bo'sh matn — ish tugadi.

        Nima uchun alohida hodisa, holat emas: bu ish suhbat holatiga
        parallel ketadi (Jarvis kod yozayotganda ham savolga javob bera
        oladi). Holatlar mashinasiga aralashtirsak, ish tugagach qaysi
        holatga qaytishni bilib bo'lmay qoladi.
        """
        self.working = text
        if text:
            log.info("Band: %s", text)
        await self.emit({"type": "work", "active": bool(text), "text": text})

    async def activity(self, text: str) -> None:
        """«Hozir aynan nima qilyapti» — ekrandagi holat qatorining ikkinchi qismi.

        Holat («o'ylayapti») nima bo'layotganini umumiy aytadi, bu esa
        aniq: «Telegram: papka yig'yapti», «matnga aylantiryapti».
        Ikkisi bitta hodisa bo'lmasligi kerak: holat suhbat siklidan,
        bu esa asbob chaqiruvlaridan keladi.

        Bo'sh matn — aniq ish tugadi, faqat holat qoladi.
        """
        self.activity_text = text
        await self.emit({"type": "activity", "text": text})

    async def problem(self, text: str) -> None:
        """Ko'rinadigan nosozlik: ekranda qoladi, vaqt bo'yicha yo'qolmaydi.

        `log_line` jurnalga yozadi va 9 soniyadan keyin so'nadi — jimlikning
        sababini topish uchun bu yetarli emas edi. Nosozlik keyingi muvaffaqiyatli
        qadamgacha ko'rinib tursin.
        """
        self.problem_text = text
        log.warning("Nosozlik: %s", text)
        await self.emit({"type": "problem", "text": text})

    async def clear_problem(self) -> None:
        if self.problem_text:
            self.problem_text = ""
            await self.emit({"type": "problem", "text": ""})

    async def hud(self, action: str) -> None:
        """To'liq ekranli HUD oynasini ochish/yopish.

        Buni yadro aniq buyruq sifatida yuboradi. Ilgari renderer buni
        holat o'zgarishidan taxmin qilardi — natijada nima uchun ochilmagani
        jurnaldan ko'rinmasdi. Endi sabab ham, buyruq ham bitta joyda.
        """
        log.info("HUD: %s", action)
        await self.emit({"type": "hud", "action": action})

    async def standby(self, on: bool) -> None:
        """Sukut holati yoqildi/o'chirildi.

        Bu holat emas, ustidagi qatlam: yadro baribir IDLE da tinglab
        turadi, faqat ko'rinish so'nadi. Shuning uchun `State` ga yangi
        qiymat qo'shilmaydi — eski UI'lar buni e'tiborsiz qoldiradi va
        hech narsa buzilmaydi.
        """
        self.standby_on = bool(on)
        await self.emit({"type": "standby", "on": self.standby_on})

    # --- Tasdiq oqimi ---

    async def request_confirm(self, action: str, detail: str, timeout: float = 60.0) -> bool:
        """UI'dan (yoki ovoz orqali) tasdiq so'raydi. Vaqt tugasa — rad etilgan hisoblanadi."""
        confirm_id = uuid.uuid4().hex[:8]
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._pending[confirm_id] = PendingConfirm(confirm_id, action, detail, future)

        previous = self.state
        await self.set_state(State.CONFIRM)
        await self.emit(
            {"type": "confirm", "id": confirm_id, "action": action, "detail": detail}
        )

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("Tasdiq so'rovi vaqti tugadi: %s", action)
            await self.emit({"type": "confirm_closed", "id": confirm_id, "approved": False})
            return False
        finally:
            self._pending.pop(confirm_id, None)
            # Tasdiq oynasi yopildi — oldingi holatga qaytamiz
            if self.state is State.CONFIRM:
                await self.set_state(previous)

    def is_pending(self, confirm_id: str) -> bool:
        """Tasdiq hali javob kutyaptimi? Ovozli tasdiq sikli shu bilan to'xtaydi."""
        pending = self._pending.get(confirm_id)
        return pending is not None and not pending.future.done()

    def resolve_confirm(self, confirm_id: str, approved: bool) -> bool:
        """UI javob berganda chaqiriladi. Topilsa True qaytaradi."""
        pending = self._pending.get(confirm_id)
        if pending is None or pending.future.done():
            return False
        pending.future.set_result(approved)
        return True

    def has_pending_confirms(self) -> bool:
        return bool(self._pending)
