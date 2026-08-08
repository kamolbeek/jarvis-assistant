"""Diagnostika testlari.

Eng muhimi: `doctor` aynan nimadir buzilganda kerak bo'ladi, shuning uchun
u og'ir kutubxonalarsiz ham ishga tusha olishi kerak.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time

import pytest

from jarvis.config import Config
from jarvis.doctor import (
    check_env,
    check_permissions,
    check_wake_word,
    collect_logs,
    hint_for,
)


def _cfg(stt: str = "elevenlabs", tts: str = "elevenlabs") -> Config:
    return Config(data={"voice": {"stt": {"provider": stt}, "tts": {"provider": tts}}})


def test_env_check_reports_every_missing_key(monkeypatch: pytest.MonkeyPatch):
    for key in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    # `claude` ham yo'q — miya uchun hech qanday yo'l qolmaydi
    monkeypatch.setattr("jarvis.doctor.shutil.which", lambda _: None)

    result = check_env(_cfg())

    assert result.ok is False
    assert result.fatal is True, "kalitsiz qolgan tekshiruvlar ma'nosiz"
    assert "ANTHROPIC_API_KEY" in result.detail
    assert "ELEVENLABS_API_KEY" in result.detail


def test_claude_code_counts_as_brain_auth(monkeypatch: pytest.MonkeyPatch):
    """API kaliti yo'q, lekin Claude Code bor — bu ham yaroqli yo'l."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")
    monkeypatch.setattr("jarvis.doctor.shutil.which", lambda name: "/usr/bin/claude")

    result = check_env(_cfg())

    assert result.ok is True, result.detail
    assert "Claude Code" in result.detail


def test_env_check_passes_when_keys_present(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "el-test")

    result = check_env(_cfg())

    assert result.ok is True
    assert "elevenlabs" in result.detail


def test_env_check_follows_configured_provider(monkeypatch: pytest.MonkeyPatch):
    """Azure tanlangan bo'lsa, ElevenLabs kaliti so'ralmasligi kerak."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("AZURE_SPEECH_KEY", "az-test")
    monkeypatch.setenv("MOHIR_API_KEY", "mo-test")

    result = check_env(_cfg(stt="mohir", tts="azure"))

    assert result.ok is True, result.detail


def test_env_check_ignores_keyless_providers(monkeypatch: pytest.MonkeyPatch):
    """Lokal Whisper va macOS `say` uchun kalit kerak emas."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    result = check_env(_cfg(stt="whisper_local", tts="macos"))

    assert result.ok is True, result.detail


def test_permissions_check_never_fails():
    """Ruxsatlarni dasturiy tekshirib bo'lmaydi — bu faqat eslatma."""
    assert check_permissions().ok is True


def test_doctor_runs_without_heavy_dependencies():
    """`jarvis doctor` og'ir kutubxonalar bo'lmasa ham ishga tushishi kerak.

    Aks holda "nimadir ishlamayapti" holatida aynan diagnostika buyrug'i
    ham ishlamay qolardi. `httpx` va `sounddevice` ni bloklab tekshiramiz.
    """
    blocker = (
        "import sys\n"
        "class Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name in ('httpx', 'sounddevice', 'websockets'): return self\n"
        "    def load_module(self, name):\n"
        "        raise ImportError(name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "from jarvis.__main__ import main\n"
        "sys.argv = ['jarvis', 'doctor']\n"
        "sys.exit(main())\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", blocker], capture_output=True, text=True, timeout=60
    )

    assert "Jarvis diagnostikasi" in result.stdout, result.stderr[:500]
    assert "ModuleNotFoundError" not in result.stderr


def test_hint_recognises_elevenlabs_key_id_mistake():
    """ElevenLabs ro'yxatdagi ID ni kalit deb qo'yish — juda ko'p uchraydigan xato."""
    error = ('{"detail":{"type":"authentication_error","code":"invalid_api_key",'
             '"message":"API key ID used as API key"}}')

    advice = hint_for(error)

    assert "sk_" in advice
    assert "ID" in advice


def test_hint_is_empty_for_unknown_errors():
    """Tanimagan xatoga o'ylab topilgan maslahat bermaymiz."""
    assert hint_for("ConnectionResetError: tarmoq uzildi") == ""


@pytest.mark.asyncio
async def test_wake_check_gives_up_instead_of_hanging(monkeypatch: pytest.MonkeyPatch):
    """Model yuklanmasa, diagnostika jim qotib turmasligi kerak.

    openWakeWord modeli har bir venv uchun qaytadan yuklanadi va bu qadam
    hech nima chop etmaydi — tashqaridan qarasa, dastur muzlab qolgandek.
    Muddat tugasa, sababi va yo'li aytilishi kerak.
    """
    import jarvis.audio.wake as wake_module

    def never_finishes(_cfg):
        time.sleep(5)
        raise AssertionError("bu yergacha yetmasligi kerak")

    monkeypatch.setattr(wake_module, "build_wake_detector", never_finishes)
    monkeypatch.setattr("jarvis.doctor.WAKE_TIMEOUT_SEC", 0.2)

    result = await check_wake_word(Config(data={}))

    assert result.ok is False
    assert result.fatal is False, "uyg'otuvchi so'zsiz ham ishlatish mumkin"
    assert "enabled: false" in result.detail, "chiqish yo'li ko'rsatilishi kerak"


@pytest.mark.asyncio
async def test_wake_check_skips_quickly_when_disabled():
    """O'chirilgan bo'lsa, model umuman yuklanmasligi kerak."""
    cfg = Config(data={"activation": {"wake_word": {"enabled": False}}})

    result = await check_wake_word(cfg)

    assert result.ok is True
    assert "qarsak" in result.detail


def test_collect_logs_captures_then_detaches():
    """Sabab jurnalga tushsa, natijaga chiqishi kerak — va keyin ushlab qolmasligi."""
    log = logging.getLogger("jarvis.voice.test")

    with collect_logs("jarvis.voice") as collected:
        log.error("STT xatosi 400: invalid_api_key")
    log.error("bu allaqachon tashqarida")

    assert collected.lines == ["STT xatosi 400: invalid_api_key"]
