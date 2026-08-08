"""Tashqi xizmatlarsiz tekshiriladigan mantiq testlari.

Bu yerda audio qurilma, API kalitlari yoki tarmoq kerak emas — shuning uchun
testlar CI'da ham, kalitsiz mashinada ham ishlaydi.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import numpy as np
import pytest

from jarvis.audio.clap import ClapDetector
from jarvis.audio.vad import Endpointer, SpeechDetector
from jarvis.brain.agent import clean_for_speech
from jarvis.brain.memory import Memory
from jarvis.bus import EventBus, State
from jarvis.config import Config, load_config
from jarvis.safety.gate import SafetyGate

SAMPLE_RATE = 16000
FRAME = 320  # 20 ms


# ---------------------------------------------------------------- Konfiguratsiya


def test_config_loads_defaults():
    cfg = load_config()
    assert cfg.get("identity.name") == "Jarvis"
    assert cfg.sample_rate == 16000
    assert cfg.frame_samples == 320


def test_config_dotted_lookup_missing_key():
    cfg = Config(data={"a": {"b": 1}})
    assert cfg.get("a.b") == 1
    assert cfg.get("a.z", "yo'q") == "yo'q"
    assert cfg.get("x.y.z") is None


# ---------------------------------------------------------------- Hodisa shinasi


async def test_bus_broadcasts_state():
    bus = EventBus()
    received: list[dict] = []

    bus.subscribe(lambda event: _collect(received, event))
    await bus.set_state(State.LISTENING)

    assert bus.state is State.LISTENING
    assert received == [{"type": "state", "state": "listening"}]


async def _collect(sink: list, event: dict) -> None:
    sink.append(event)


async def test_bus_confirm_resolves():
    bus = EventBus()
    confirm_ids: list[str] = []

    async def watch(event: dict) -> None:
        if event.get("type") == "confirm":
            confirm_ids.append(event["id"])

    bus.subscribe(watch)
    task = asyncio.create_task(bus.request_confirm("Buyruq?", "ls -la"))

    # Tasdiq so'rovi chiqishini kutamiz
    for _ in range(50):
        await asyncio.sleep(0.01)
        if confirm_ids:
            break

    assert confirm_ids, "tasdiq so'rovi yuborilmadi"
    assert bus.resolve_confirm(confirm_ids[0], True) is True
    assert await task is True


async def test_bus_confirm_timeout_denies():
    bus = EventBus()
    assert await bus.request_confirm("Buyruq?", "rm x", timeout=0.05) is False


async def test_bus_survives_failing_subscriber():
    bus = EventBus()
    ok: list[dict] = []

    async def broken(event: dict) -> None:
        raise RuntimeError("qasddan yiqilish")

    bus.subscribe(broken)
    bus.subscribe(lambda event: _collect(ok, event))
    await bus.set_state(State.IDLE)

    assert len(ok) == 1, "bir obunachi yiqilsa, boshqasi baribir xabar olishi kerak"


# ---------------------------------------------------------------- Qarsak aniqlash


def _silence(frames: int = 1) -> list[np.ndarray]:
    rng = np.random.default_rng(7)
    return [rng.normal(0, 40, FRAME).astype(np.int16) for _ in range(frames)]


def _clap_frame() -> np.ndarray:
    """Qarsakka o'xshash kadr: keng spektrli, kuchli zarba."""
    rng = np.random.default_rng(11)
    return (rng.normal(0, 9000, FRAME)).astype(np.int16)


def _speech_frame() -> np.ndarray:
    """Nutqqa o'xshash kadr: energiya past chastotalarda."""
    t = np.arange(FRAME) / SAMPLE_RATE
    wave = sum(np.sin(2 * np.pi * f * t) for f in (150, 300, 450, 600))
    return (wave / 4 * 9000).astype(np.int16)


def test_double_clap_detected():
    detector = ClapDetector(sample_rate=SAMPLE_RATE)

    for frame in _silence(30):
        assert detector.push(frame) is False

    assert detector.push(_clap_frame()) is False, "birinchi qarsak hali yetarli emas"
    for frame in _silence(8):  # ~160 ms tanaffus
        detector.push(frame)

    assert detector.push(_clap_frame()) is True, "ikkinchi qarsak ishga tushirishi kerak"


def test_single_clap_does_not_fire():
    detector = ClapDetector(sample_rate=SAMPLE_RATE)
    for frame in _silence(30):
        detector.push(frame)

    detector.push(_clap_frame())
    for frame in _silence(60):  # max_gap dan uzoq kutamiz
        assert detector.push(frame) is False


def test_clap_gap_measured_in_audio_time():
    """Oraliq audio davomiyligi bo'yicha o'lchanishi kerak, qayta ishlash tezligi bo'yicha emas.

    Kadrlar navbatda to'planib qolsa, ular birdaniga ketma-ket qayta ishlanadi.
    Agar vaqt real soat bilan o'lchansa, 300 ms oraliqdagi ikki qarsak
    mikrosoniya oraliq deb hisoblanib, aniqlanmay qolardi.
    """
    # 2 kadr = 40 ms — min_gap (120 ms) dan kam, ishga tushmasligi kerak
    too_close = ClapDetector(sample_rate=SAMPLE_RATE)
    for frame in _silence(30):
        too_close.push(frame)
    too_close.push(_clap_frame())
    for frame in _silence(2):
        too_close.push(frame)
    assert too_close.push(_clap_frame()) is False, "40 ms oraliq juda qisqa"

    # 20 kadr = 400 ms — max_gap (700 ms) ichida, ishga tushishi kerak
    just_right = ClapDetector(sample_rate=SAMPLE_RATE)
    for frame in _silence(30):
        just_right.push(frame)
    just_right.push(_clap_frame())
    for frame in _silence(20):
        just_right.push(frame)
    assert just_right.push(_clap_frame()) is True, "400 ms oraliq qabul qilinishi kerak"


def test_clap_cooldown_blocks_immediate_retrigger():
    """Ishga tushgandan keyin qisqa vaqt ichida qayta ishga tushmasligi kerak."""
    detector = ClapDetector(sample_rate=SAMPLE_RATE, cooldown_sec=1.0)
    for frame in _silence(30):
        detector.push(frame)
    detector.push(_clap_frame())
    for frame in _silence(8):
        detector.push(frame)
    assert detector.push(_clap_frame()) is True

    # Darhol yana ikki qarsak — sovish davri tufayli e'tiborsiz qoldirilishi kerak
    detector.push(_clap_frame())
    for frame in _silence(8):
        detector.push(frame)
    assert detector.push(_clap_frame()) is False


def test_speech_does_not_trigger_clap():
    """Gapirish qarsak deb qabul qilinmasligi kerak — bu eng ko'p uchraydigan yolg'on ishga tushish."""
    detector = ClapDetector(sample_rate=SAMPLE_RATE)
    for frame in _silence(30):
        detector.push(frame)

    fired = False
    for _ in range(40):
        if detector.push(_speech_frame()):
            fired = True
        for frame in _silence(2):
            if detector.push(frame):
                fired = True

    assert fired is False, "past chastotali nutq qarsak sifatida qabul qilindi"


# ---------------------------------------------------------------- Endpointing


class _ScriptedDetector(SpeechDetector):
    """Oldindan belgilangan ketma-ketlik bo'yicha javob beradigan soxta detektor."""

    def __init__(self, script: list[bool]) -> None:
        self._script = list(script)
        self._index = 0

    def is_speech(self, frame: np.ndarray) -> bool:
        if self._index < len(self._script):
            value = self._script[self._index]
            self._index += 1
            return value
        return False


def test_endpointer_finishes_after_silence():
    # 10 kadr nutq, keyin jimlik
    detector = _ScriptedDetector([True] * 10 + [False] * 100)
    ep = Endpointer(detector, frame_ms=20, silence_ms=200)  # 10 kadr jimlik kerak

    frame = np.zeros(FRAME, dtype=np.int16)
    for _ in range(10):
        ep.push(frame)
    assert ep.started is True
    assert ep.finished is False

    for _ in range(10):
        ep.push(frame)
    assert ep.finished is True
    assert ep.result().size == 20 * FRAME


def test_endpointer_ignores_leading_silence():
    detector = _ScriptedDetector([False] * 50)
    ep = Endpointer(detector, frame_ms=20, silence_ms=200)

    frame = np.zeros(FRAME, dtype=np.int16)
    for _ in range(50):
        ep.push(frame)

    assert ep.started is False, "gapirish boshlanmagan bo'lsa, tugash ham bo'lmasligi kerak"
    assert ep.finished is False


def test_endpointer_respects_max_duration():
    detector = _ScriptedDetector([True] * 1000)
    ep = Endpointer(detector, frame_ms=20, silence_ms=5000, max_utterance_sec=0.5)

    frame = np.zeros(FRAME, dtype=np.int16)
    for _ in range(100):
        ep.push(frame)
        if ep.finished:
            break

    assert ep.finished is True
    assert ep.duration_sec <= 0.6


# ---------------------------------------------------------------- Xotira


def test_memory_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        memory = Memory(Path(tmp) / "m.db")

        memory.remember("ish_vaqti", "9:00 - 18:00", "jadval")
        assert memory.recall("ish_vaqti") == "9:00 - 18:00"

        # Qayta yozish yangilashi kerak, dublikat yaratmasligi
        memory.remember("ish_vaqti", "10:00 - 19:00", "jadval")
        assert memory.recall("ish_vaqti") == "10:00 - 19:00"
        assert len(memory.all_facts()) == 1

        assert memory.forget("ish_vaqti") is True
        assert memory.forget("ish_vaqti") is False
        assert memory.recall("ish_vaqti") is None

        memory.close()


def test_memory_search_and_context():
    with tempfile.TemporaryDirectory() as tmp:
        memory = Memory(Path(tmp) / "m.db")
        memory.remember("ilevel_hisobot", "har kuni ertalab", "ish")
        memory.remember("sevimli_til", "o'zbekcha", "shaxsiy")
        memory.add_turn("s1", "user", "iLevel hisobotini yubor")

        assert len(memory.search("ilevel")) == 1
        assert len(memory.search_turns("hisobot")) == 1

        context = memory.context_block()
        assert "[ish]" in context and "[shaxsiy]" in context
        memory.close()


# ---------------------------------------------------------------- Xavfsizlik


def _gate(tmp: str, **overrides) -> SafetyGate:
    data = {
        "brain": {"workspace": f"{tmp}/ws"},
        "memory": {"path": f"{tmp}/m.db"},
        "safety": {
            "default": "ask",
            "rules": {"Read": "allow", "Bash": "ask", "Write": "ask"},
            "forbidden_patterns": ["rm -rf /", "sudo rm", "mkfs"],
            "writable_roots": [f"{tmp}/ws"],
            "audit_log": f"{tmp}/audit.log",
        },
    }
    data.update(overrides)
    cfg = Config(data=data)
    cfg.ensure_dirs()
    return SafetyGate(config=cfg, bus=EventBus())


async def test_gate_allows_read():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        decision = await gate.evaluate("Read", {"file_path": "/etc/hosts"})
        assert decision.allowed is True
        assert decision.asked is False


async def test_gate_blocks_forbidden_command():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        decision = await gate.evaluate("Bash", {"command": "sudo rm -rf /tmp/x"})
        assert decision.allowed is False
        assert decision.asked is False, "taqiqlangan amal uchun tasdiq so'ralmasligi kerak"


async def test_gate_normalizes_whitespace_in_forbidden_check():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        # Ortiqcha probellar bilan yashirishga urinish
        decision = await gate.evaluate("Bash", {"command": "sudo    rm   -rf  /tmp"})
        assert decision.allowed is False


async def test_gate_blocks_write_outside_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        decision = await gate.evaluate("Write", {"file_path": "/etc/passwd"})
        assert decision.allowed is False
        assert "tashqarida" in decision.reason


async def test_gate_asks_for_write_inside_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        bus = gate.bus

        async def approve(event: dict) -> None:
            if event.get("type") == "confirm":
                bus.resolve_confirm(event["id"], True)

        bus.subscribe(approve)
        decision = await gate.evaluate("Write", {"file_path": f"{tmp}/ws/note.md"})

        assert decision.allowed is True
        assert decision.asked is True


async def test_gate_remembers_session_grant():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        asks = 0

        async def approve(event: dict) -> None:
            nonlocal asks
            if event.get("type") == "confirm":
                asks += 1
                gate.bus.resolve_confirm(event["id"], True)

        gate.bus.subscribe(approve)
        await gate.evaluate("Bash", {"command": "git status"})
        await gate.evaluate("Bash", {"command": "git log --oneline"})

        assert asks == 1, "bir xil turdagi buyruq uchun qayta so'ralmasligi kerak"


async def test_gate_detects_shell_redirect_outside_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        gate = _gate(tmp)
        decision = await gate.evaluate("Bash", {"command": "echo hack > /etc/cron.d/evil"})
        assert decision.allowed is False, "shell yo'naltirishi orqali yozish o'tkazilmasligi kerak"


# ---------------------------------------------------------------- Nutq uchun tozalash


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("**Muhim** matn", "Muhim matn"),
        ("# Sarlavha\n\nMatn", "Sarlavha Matn"),
        ("- birinchi\n- ikkinchi", "birinchi ikkinchi"),
        ("Mana: ```python\nprint(1)\n``` tayyor", "Mana: kod bloki tayyor"),
        ("  ortiqcha   probellar  ", "ortiqcha probellar"),
    ],
)
def test_clean_for_speech(raw: str, expected: str):
    assert clean_for_speech(raw) == expected


# --- Signal sifati: kesilishni aniqlash ---------------------------------------
#
# Bu o'lchovlar kerak bo'lgani real muammodan chiqdi: kirish balandligi
# oxirigacha ko'tarilganda uyg'otuvchi so'z modeli bir xil iboraga har safar
# boshqa ball berdi. Sababi kesilish edi, lekin RMS darajasi buni ko'rsatmadi —
# u 8000 da 1.00 ga yetib to'xtaydi.


def test_frame_level_saturates_and_hides_loudness():
    """RMS darajasi «baland» va «juda baland» ni ajratmaydi — shuni tasdiqlaymiz."""
    from jarvis.audio.mic import frame_level

    loud = np.full(320, 9000, dtype=np.int16)
    louder = np.full(320, 32000, dtype=np.int16)

    assert frame_level(loud) == 1.0
    assert frame_level(louder) == 1.0


def test_frame_peak_shows_the_real_headroom():
    from jarvis.audio.mic import frame_peak

    quiet = np.full(320, 3276, dtype=np.int16)
    full = np.full(320, 32767, dtype=np.int16)

    assert frame_peak(quiet) == pytest.approx(0.1, abs=0.01)
    assert frame_peak(full) == pytest.approx(1.0, abs=0.001)
    assert frame_peak(np.zeros(0, dtype=np.int16)) == 0.0


def test_clip_fraction_counts_flattened_samples():
    from jarvis.audio.mic import clip_fraction

    clean = np.full(100, 10000, dtype=np.int16)
    half = np.concatenate([np.full(50, 32767, dtype=np.int16),
                           np.full(50, 1000, dtype=np.int16)])

    assert clip_fraction(clean) == 0.0
    assert clip_fraction(half) == pytest.approx(0.5)


def test_clip_fraction_catches_both_polarities():
    """Kesilish pastdan ham bo'ladi — manfiy tomonini o'tkazib yubormaslik kerak."""
    from jarvis.audio.mic import clip_fraction

    negative = np.full(64, -32768, dtype=np.int16)

    assert clip_fraction(negative) == 1.0


# --- Mikrofon haqiqatan ovoz beryaptimi ---------------------------------------
#
# macOS ruxsat bermaganda oqim ochiladi, xato bermaydi, lekin ichida faqat
# NOL keladi. Jarvis «tayyor» deb turadi va chaqiruvni hech qachon
# eshitmaydi. Haqiqiy jimlikda ham fon shovqini bo'ladi — mutlaq nol aynan
# bloklanganning belgisi.


class _SilentMic:
    def __init__(self, value: int = 0, sample_rate: int = 16000, frame: int = 320):
        self.value = value
        self.sample_rate = sample_rate
        self.frame_samples = frame

    async def frames(self):
        while True:
            yield np.full(self.frame_samples, self.value, dtype=np.int16)


async def _run_mic_check(value: int):
    """Yadroning mikrofon tekshiruvini yolg'iz o'zi ishga tushiradi."""
    from jarvis.app import Jarvis
    from jarvis.bus import EventBus
    from jarvis.config import Config
    from jarvis.health import Health, System

    jarvis = Jarvis.__new__(Jarvis)
    jarvis.config = Config(data={"audio": {"sample_rate": 16000, "frame_ms": 20}})
    jarvis.bus = EventBus()
    jarvis.health = Health(jarvis.bus.emit)
    jarvis.mic = _SilentMic(value)

    await jarvis._check_mic_delivers_audio(seconds=0.1)
    return jarvis.health.snapshot(), System


@pytest.mark.asyncio
async def test_silent_mic_is_reported_as_down():
    snapshot, System = await _run_mic_check(0)

    mic = next(s for s in snapshot["systems"] if s["id"] == System.MIC.value)
    assert mic["status"] == "down"
    assert "macOS" in (mic.get("detail") or ""), "sabab aytilishi kerak"


@pytest.mark.asyncio
async def test_working_mic_is_left_alone():
    """Ovoz kelayotgan bo'lsa, tekshiruv hech nimaga tegmaydi."""
    snapshot, System = await _run_mic_check(120)

    mic = next(s for s in snapshot["systems"] if s["id"] == System.MIC.value)
    assert mic["status"] != "down"
