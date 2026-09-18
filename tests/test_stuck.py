"""Qotib qolishdan chiqish.

Haqiqiy hodisa: foydalanuvchi «o'chir» dedi, tasdiq berildi, keyin miya
javob qaytarmadi. Ekranda «O'YLAYAPTI» turib qoldi va shundan keyin NA
chaqiruv, na orbni bosish ishladi — Jarvisni faqat terminaldan o'ldirish
mumkin edi.

Sababi arxitekturada edi: seans tinglash siklining ICHIDA kutilardi. Ya'ni
seans qotsa, uni to'xtatadigan kod umuman ishga tushmasdi.

Bu yerda aynan shu holat qayta tiklanadi: hech qachon tugamaydigan seans
qo'yiladi va uchta yo'lning uchalasi ham tekshiriladi — qo'riqchi o'zi
uzishi, orbni bosish va «to'xta» buyrug'i.
"""

from __future__ import annotations

import asyncio

import pytest

from jarvis.app import Jarvis
from jarvis.bus import EventBus, State


class _FakeSpeaker:
    def __init__(self) -> None:
        self.speaking = False
        self.stopped = 0

    def stop(self) -> None:
        self.stopped += 1


class _FakeMic:
    def __init__(self) -> None:
        self.drained = 0

    def drain(self) -> None:
        self.drained += 1


class _FakeBrain:
    def __init__(self) -> None:
        self.interrupts = 0

    async def interrupt(self) -> None:
        self.interrupts += 1


def _core(stuck_after: float = 0.05) -> Jarvis:
    """Yadroning faqat qotib qolishga aloqador qismini yig'adi.

    To'liq konstruktor mikrofon, kalitlar va tarmoqni talab qiladi —
    bularning hech biri bu yerda tekshirilayotgan mantiqqa taalluqli emas.
    """
    core = Jarvis.__new__(Jarvis)
    core.bus = EventBus()
    core.speaker = _FakeSpeaker()
    core.mic = _FakeMic()
    core.brain = _FakeBrain()
    core._shutdown = asyncio.Event()
    core._activate = asyncio.Event()
    core._session_task = None
    core._confirm_task = None
    core._last_progress = asyncio.get_event_loop().time()
    core._speaking_since = None
    core._stuck_after = stuck_after
    core.bus.subscribe(core._note_progress)

    spoken: list[str] = []

    async def speak(text: str, remote: str | None = None) -> None:
        spoken.append(text)

    core._speak = speak  # type: ignore[method-assign]
    core.spoken = spoken  # type: ignore[attr-defined]
    return core


async def _never_ends() -> None:
    await asyncio.Event().wait()


# --- Qo'riqchi ---------------------------------------------------------------


async def test_watchdog_aborts_a_frozen_session():
    """Taraqqiyotsiz qolgan seans o'zi to'xtatiladi va holat IDLE ga qaytadi."""
    core = _core(stuck_after=0.05)
    core._session_task = asyncio.create_task(_never_ends())
    await core.bus.set_state(State.THINKING)
    core._last_progress -= 10  # allaqachon uzoq vaqt qotgan

    guard = asyncio.create_task(core._stuck_watchdog())
    try:
        for _ in range(60):
            await asyncio.sleep(0.1)
            if core._session_task is None:
                break
    finally:
        guard.cancel()

    assert core._session_task is None, "seans to'xtatilmadi"
    assert core.bus.state is State.IDLE
    assert core.brain.interrupts == 1
    assert "javob kelmadi" in " ".join(core.spoken).lower()


async def test_watchdog_reports_the_reason_on_screen():
    """Jimgina uzish yetarli emas — nima bo'lganini foydalanuvchi bilishi kerak."""
    core = _core(stuck_after=0.05)
    core._session_task = asyncio.create_task(_never_ends())
    core._last_progress -= 10

    guard = asyncio.create_task(core._stuck_watchdog())
    try:
        for _ in range(60):
            await asyncio.sleep(0.1)
            if core.bus.problem_text:
                break
    finally:
        guard.cancel()

    assert "seans" in core.bus.problem_text.lower()


async def test_watchdog_leaves_a_speaking_session_alone():
    """Uzun javobni aytish — qotish emas."""
    core = _core(stuck_after=0.05)
    core._session_task = asyncio.create_task(_never_ends())
    await core.bus.set_state(State.SPEAKING)
    core.speaker.speaking = True
    core._last_progress -= 10

    guard = asyncio.create_task(core._stuck_watchdog())
    try:
        await asyncio.sleep(0.4)
    finally:
        guard.cancel()
        core._session_task.cancel()

    assert core.bus.state is not State.IDLE
    assert core.brain.interrupts == 0


async def test_watchdog_waits_while_a_confirm_is_pending():
    """Foydalanuvchi o'ylab turgan bo'lishi mumkin — tasdiqni uzib yubormaymiz."""
    core = _core(stuck_after=0.05)
    core._session_task = asyncio.create_task(_never_ends())
    core._last_progress -= 10

    asking = asyncio.create_task(core.bus.request_confirm("O'chirilsinmi?", "", timeout=5))
    await asyncio.sleep(0)  # so'rov ro'yxatga tushsin

    guard = asyncio.create_task(core._stuck_watchdog())
    try:
        await asyncio.sleep(0.4)
        assert core.brain.interrupts == 0, "tasdiq kutilayotganda uzilmasligi kerak"
    finally:
        guard.cancel()
        asking.cancel()
        core._session_task.cancel()


async def test_progress_events_postpone_the_abort():
    """Ish ketayotgan bo'lsa (asbob chaqiruvlari kelyapti) — uzilmaydi."""
    core = _core(stuck_after=0.3)
    core._session_task = asyncio.create_task(_never_ends())

    guard = asyncio.create_task(core._stuck_watchdog())

    async def keep_working() -> None:
        for _ in range(6):
            await asyncio.sleep(0.1)
            await core.bus.activity("Telegram: o'qiyapti")

    try:
        await keep_working()
        assert core.brain.interrupts == 0
    finally:
        guard.cancel()
        core._session_task.cancel()


# --- Foydalanuvchining chiqish yo'llari --------------------------------------


async def test_orb_click_breaks_a_frozen_session():
    """Orbni bosish — qo'ldagi yagona ishonchli tugma, u har doim ishlashi kerak."""
    core = _core()
    core._session_task = asyncio.create_task(_never_ends())
    await core.bus.set_state(State.THINKING)

    await core._on_activate({})

    assert core._session_task is None
    assert core.bus.state is State.IDLE
    # Bosish yangi seans ochmasligi kerak: u avval turganini uzdi.
    assert not core._activate.is_set()


async def test_orb_click_still_wakes_when_nothing_is_running():
    core = _core()

    await core._on_activate({})

    assert core._activate.is_set()


async def test_stop_command_breaks_a_frozen_session():
    core = _core()
    core._session_task = asyncio.create_task(_never_ends())
    await core.bus.set_state(State.THINKING)

    await core._on_stop({})

    assert core._session_task is None
    assert core.bus.state is State.IDLE
    assert core.speaker.stopped >= 1


async def test_abort_clears_the_activity_line():
    """Ekranda «o'chiryapti task» yozuvi qolib ketmasin."""
    core = _core()
    core._session_task = asyncio.create_task(_never_ends())
    await core.bus.set_state(State.THINKING)
    await core.bus.activity("o'chiryapti task")

    await core._abort_session("sinov")

    assert core.bus.activity_text == ""


# --- Uzilgan seans tinglashni o'ldirmaydi ------------------------------------


async def test_listening_survives_an_aborted_session():
    """Eng muhim xossa: uzish Jarvisni butunlay o'chirib qo'ymasligi kerak.

    `_run_session` uzilganda `CancelledError` ni yutishi shart — aks holda
    u tinglash siklini ham yiqitardi va Jarvis chaqiruvga javob bermay
    qolardi. Ya'ni «tuzatish» muammoni yomonlashtirardi.
    """
    core = _core()

    async def hang(source: str) -> None:
        await asyncio.Event().wait()

    core._session = hang  # type: ignore[method-assign]

    running = asyncio.create_task(core._run_session("so'z"))
    await asyncio.sleep(0.05)
    await core._abort_session("sinov")

    # `_run_session` xatosiz tugashi kerak.
    await asyncio.wait_for(running, timeout=1.0)
    assert core._session_task is None


async def test_abort_is_safe_when_nothing_is_running():
    core = _core()
    await core._abort_session("bo'sh")  # ko'tarilmasligi kerak
    assert core.bus.state is State.IDLE


@pytest.mark.parametrize("event", ["state", "activity", "say", "transcript"])
async def test_meaningful_events_count_as_progress(event: str):
    core = _core()
    core._last_progress = 0.0

    await core._note_progress({"type": event})

    assert core._last_progress > 0.0


async def test_microphone_level_is_not_progress():
    """Daraja Jarvis qotib qolganda ham kelib turadi — u dalil emas."""
    core = _core()
    core._last_progress = 0.0

    await core._note_progress({"type": "level", "value": 0.3})

    assert core._last_progress == 0.0


# --- Ovoz oqimi osilib qolsa --------------------------------------------------


async def test_endless_speaking_is_also_a_hang():
    """`speaking` bayrog'i tushmay qolsa, qo'riqchi umuman ishga tushmasdi.

    Bu himoyaning ichidagi teshik edi: «gapiryapti» deb hisoblangan har
    qanday holat tekshiruvdan chetda qolardi.
    """
    core = _core(stuck_after=0.05)
    core.MAX_SPEAK_SEC = 0.2
    core._session_task = asyncio.create_task(_never_ends())
    await core.bus.set_state(State.SPEAKING)
    core.speaker.speaking = True

    guard = asyncio.create_task(core._stuck_watchdog())
    try:
        for _ in range(60):
            await asyncio.sleep(0.1)
            if core._session_task is None:
                break
    finally:
        guard.cancel()

    assert core._session_task is None, "osilib qolgan ovoz to'xtatilmadi"
    assert "ovoz" in core.bus.problem_text.lower()


async def test_normal_speaking_is_not_cut_off():
    """Chegara uzun javobni bo'lib yubormasligi kerak."""
    core = _core(stuck_after=0.05)
    core.MAX_SPEAK_SEC = 30.0
    core._session_task = asyncio.create_task(_never_ends())
    await core.bus.set_state(State.SPEAKING)
    core.speaker.speaking = True

    guard = asyncio.create_task(core._stuck_watchdog())
    try:
        await asyncio.sleep(0.4)
    finally:
        guard.cancel()
        core._session_task.cancel()

    assert core.brain.interrupts == 0
