"""Diagnostika testlari.

Eng muhimi: `doctor` aynan nimadir buzilganda kerak bo'ladi, shuning uchun
u og'ir kutubxonalarsiz ham ishga tusha olishi kerak.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from jarvis.config import Config
from jarvis.doctor import check_env, check_permissions


def _cfg(stt: str = "elevenlabs", tts: str = "elevenlabs") -> Config:
    return Config(data={"voice": {"stt": {"provider": stt}, "tts": {"provider": tts}}})


def test_env_check_reports_every_missing_key(monkeypatch: pytest.MonkeyPatch):
    for key in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    result = check_env(_cfg())

    assert result.ok is False
    assert result.fatal is True, "kalitsiz qolgan tekshiruvlar ma'nosiz"
    assert "ANTHROPIC_API_KEY" in result.detail
    assert "ELEVENLABS_API_KEY" in result.detail


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
