"""Sozlamani buyruq bilan o'zgartirish.

Bu modul haqiqiy nosozlikdan keyin yozildi: foydalanuvchidan YAML faylini
qo'lda tahrirlashni so'radim, bo'sh joylar siljidi va Jarvis umuman ishga
tushmay qoldi. Bo'sh joyga sezgir faylni qo'lda tahrirlash — noto'g'ri yo'l.

Ikkita talab: izohlar saqlanishi kerak (ular hujjatning o'zi), va buzilgan
natija diskka tushmasligi kerak.
"""

from __future__ import annotations

import pytest
import yaml

from jarvis.configpatch import patch_file, set_in_block

SAMPLE = """\
identity:
  name: "Jarvis"

activation:
  wake_word:
    enabled: true
    model: "hey_jarvis"
    threshold: 0.5                 # 0..1 — pastroq = sezgirroq
    cooldown_sec: 2.0

  clap:
    enabled: true
    onset_ratio: 8.0

audio:
  sample_rate: 16000
"""


def test_updates_the_value_in_place():
    out = set_in_block(SAMPLE, "wake_word", {"threshold": 0.33})

    assert "    threshold: 0.33" in out
    assert yaml.safe_load(out)["activation"]["wake_word"]["threshold"] == 0.33


def test_keeps_the_comment_on_the_line():
    """Izohlar hujjatning o'zi — ularni yo'qotish yaramaydi."""
    out = set_in_block(SAMPLE, "wake_word", {"threshold": 0.33})

    assert "# 0..1 — pastroq = sezgirroq" in out


def test_adds_a_missing_key_inside_the_block():
    out = set_in_block(SAMPLE, "wake_word", {"candidate_threshold": 0.25})

    data = yaml.safe_load(out)
    assert data["activation"]["wake_word"]["candidate_threshold"] == 0.25
    # Qo'shni bloklarga tegmasligi kerak
    assert data["activation"]["clap"]["enabled"] is True


def test_does_not_touch_a_key_of_the_same_name_elsewhere():
    """`enabled` ikkala blokda ham bor — faqat kerakligi o'zgarishi kerak."""
    out = set_in_block(SAMPLE, "wake_word", {"enabled": False})

    data = yaml.safe_load(out)
    assert data["activation"]["wake_word"]["enabled"] is False
    assert data["activation"]["clap"]["enabled"] is True


def test_the_rest_of_the_file_is_untouched():
    out = set_in_block(SAMPLE, "wake_word", {"threshold": 0.4})

    data = yaml.safe_load(out)
    assert data["identity"]["name"] == "Jarvis"
    assert data["audio"]["sample_rate"] == 16000


def test_missing_block_is_an_error():
    with pytest.raises(KeyError, match="wake_word"):
        set_in_block("audio:\n  sample_rate: 16000\n", "wake_word", {"threshold": 0.3})


def test_list_values_are_written_as_yaml():
    out = set_in_block(SAMPLE, "wake_word", {"phrases": ["hey jarvis", "hi jarvis"]})

    assert yaml.safe_load(out)["activation"]["wake_word"]["phrases"] == [
        "hey jarvis", "hi jarvis",
    ]


def test_patch_file_writes_and_backs_up(tmp_path):
    path = tmp_path / "jarvis.yaml"
    path.write_text(SAMPLE)

    patch_file(path, "wake_word", {"threshold": 0.33, "candidate_threshold": 0.25})

    data = yaml.safe_load(path.read_text())
    assert data["activation"]["wake_word"]["threshold"] == 0.33
    assert data["activation"]["wake_word"]["candidate_threshold"] == 0.25
    assert (tmp_path / "jarvis.yaml.bak").read_text() == SAMPLE


def test_broken_result_never_reaches_the_disk(tmp_path, monkeypatch):
    """Yozishdan oldin YAML o'qib ko'riladi — buzilgani saqlanmasligi kerak."""
    path = tmp_path / "jarvis.yaml"
    path.write_text(SAMPLE)

    monkeypatch.setattr("jarvis.configpatch.set_in_block",
                        lambda *a, **k: "activation:\n  wake_word:\n   bad: [\n")

    with pytest.raises(yaml.YAMLError):
        patch_file(path, "wake_word", {"threshold": 0.33})

    assert path.read_text() == SAMPLE, "asl fayl tegilmagan bo'lishi kerak"


# --- Ishonch rejimi ------------------------------------------------------------


def test_trust_on_flips_the_gated_tools(tmp_path, monkeypatch):
    """`trust on` — tasdiq so'ralmaydi, lekin taqiqlar joyida qoladi."""
    import yaml as _yaml

    from jarvis import trust

    config = tmp_path / "jarvis.yaml"
    config.write_text(
        "safety:\n"
        '  default: "ask"\n'
        "  rules:\n"
        '    Read: "allow"\n'
        '    Bash: "ask"\n'
        '    Write: "ask"\n'
        "  forbidden_patterns:\n"
        '    - "rm -rf /"\n'
    )
    monkeypatch.setattr("jarvis.config.CONFIG_PATH", config)

    assert trust.apply("on") == 0

    data = _yaml.safe_load(config.read_text())["safety"]
    assert data["default"] == "allow"
    assert data["rules"]["Bash"] == "allow"
    assert data["rules"]["Write"] == "allow"
    assert data["forbidden_patterns"] == ["rm -rf /"], "taqiqlar tegilmasligi kerak"

    assert trust.apply("off") == 0
    data = _yaml.safe_load(config.read_text())["safety"]
    assert data["default"] == "ask"
    assert data["rules"]["Bash"] == "ask"


def test_trust_rejects_a_bad_mode(tmp_path, monkeypatch):
    from jarvis import trust

    monkeypatch.setattr("jarvis.config.CONFIG_PATH", tmp_path / "jarvis.yaml")

    assert trust.apply("maybe") == 2
