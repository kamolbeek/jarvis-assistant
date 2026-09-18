"""Tinglash paytida musiqani jim qilish.

Haqiqiy holat: YouTube'da qo'shiq chalinib turibdi, foydalanuvchi gapira
boshlaydi — mikrofon ikkalasini birga eshitadi va matnga aylantirish
buziladi. Shuning uchun tinglash boshlanganda tizim ovozi 0 ga tushadi,
tugagach esa AVVALGI darajaga qaytadi: ish bajarilayotganda musiqa
chalinaveradi.

Eng nozik joyi — ichma-ich chaqirilish. Suhbat ichida yana tinglansa,
ikkinchi chaqiruv "eski daraja" deb allaqachon pasaytirilgan qiymatni
saqlab qo'yishi mumkin, va musiqa butunlay jim bo'lib qolardi.
"""

from __future__ import annotations

import sys
import types

import pytest

from jarvis.app import Jarvis


class _FakeVolume:
    """macOS ovoz boshqaruvining o'rnini bosadi."""

    def __init__(self, level: int = 70) -> None:
        self.level = level
        self.history: list[int] = []

    async def get_volume(self) -> int:
        return self.level

    async def set_volume(self, value: int) -> None:
        self.level = int(value)
        self.history.append(self.level)


class MacOsError(RuntimeError):
    pass


@pytest.fixture
def volume(monkeypatch) -> _FakeVolume:
    fake = _FakeVolume()
    module = types.ModuleType("jarvis.tools.macos")
    module.get_volume = fake.get_volume
    module.set_volume = fake.set_volume
    module.MacOsError = MacOsError
    monkeypatch.setitem(sys.modules, "jarvis.tools.macos", module)
    return fake


def _jarvis(level: int = 0, enabled: bool = True) -> Jarvis:
    jarvis = Jarvis.__new__(Jarvis)
    jarvis._duck_enabled = enabled
    jarvis._duck_level = level
    jarvis._duck_depth = 0
    return jarvis


async def test_music_is_muted_while_listening(volume):
    jarvis = _jarvis()

    async with jarvis._ducked():
        assert volume.level == 0, "gapirayotganda musiqa eshitilmasligi kerak"

    assert volume.level == 70, "tinglash tugagach eski daraja qaytadi"


async def test_nested_listening_keeps_the_original_level(volume):
    """Suhbat ichidagi ikkinchi tinglash musiqani o'chirib yubormasin."""
    jarvis = _jarvis()

    async with jarvis._ducked():
        async with jarvis._ducked():
            assert volume.level == 0
        # Ichki blok tugadi — hali tinglayapmiz, ovoz ko'tarilmasligi kerak.
        assert volume.level == 0

    assert volume.level == 70


async def test_partial_ducking_is_possible(volume):
    """Kimdir «butunlay jim bo'lmasin» desa, sozlama shuni ham beradi."""
    jarvis = _jarvis(level=20)

    async with jarvis._ducked():
        assert volume.level == 20

    assert volume.level == 70


async def test_quiet_music_is_left_alone(volume):
    """Ovoz allaqachon past bo'lsa, uni ko'tarib yubormaymiz."""
    volume.level = 0
    jarvis = _jarvis(level=20)

    async with jarvis._ducked():
        assert volume.level == 0

    assert volume.history == [], "hech narsa o'zgartirilmasligi kerak edi"


async def test_level_is_restored_after_an_error(volume):
    """Tinglashda xato bo'lsa ham musiqa jim qolib ketmasin."""
    jarvis = _jarvis()

    with pytest.raises(RuntimeError):
        async with jarvis._ducked():
            raise RuntimeError("STT yiqildi")

    assert volume.level == 70


async def test_disabled_ducking_touches_nothing(volume):
    jarvis = _jarvis(enabled=False)

    async with jarvis._ducked():
        pass

    assert volume.history == []
