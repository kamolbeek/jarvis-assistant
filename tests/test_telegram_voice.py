"""Ovozli xabarlarni matnga aylantirish va suhbatni eksport qilish.

Nima uchun kerak bo'lgani: kelishmovchilik. «Berganman» — «bermagansiz».
Dalil esa ovozli xabarlar ichida bo'lishi mumkin, Telegram qidiruvi ularni
umuman ko'rmaydi (ovozli xabarning ichida matn yo'q).

Shuning uchun bu yerda ikki narsa qat'iy sinaladi:

  * bir marta aylantirilgan yozuv KESHDA qoladi — aks holda har qidiruv
    qaytadan daqiqalab ishlardi;
  * bitta yozuv aylanmasa ham butun ish to'xtamaydi — uzun suhbatda bitta
    buzuq fayl hammasini yo'qqa chiqarmasligi kerak.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jarvis.tools import telegram_user as tg


class _AsyncList:
    def __init__(self, items: list) -> None:
        self.items = items

    def __call__(self, *args, **kwargs):
        return self

    def __aiter__(self):
        self._it = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


def _voice_message(msg_id: int, sender: str = "Asad") -> SimpleNamespace:
    """Ovozli xabar: hujjatida `voice` bayrog'i bor."""
    document = SimpleNamespace(attributes=[SimpleNamespace(voice=True)])
    return SimpleNamespace(
        id=msg_id, message="", date=None,
        media=SimpleNamespace(document=document),
        sender=SimpleNamespace(first_name=sender, last_name=None, username=None),
    )


def _text_message(msg_id: int, text: str, sender: str = "Asad") -> SimpleNamespace:
    return SimpleNamespace(
        id=msg_id, message=text, date=None, media=None,
        sender=SimpleNamespace(first_name=sender, last_name=None, username=None),
    )


class _VoiceClient:
    """Ovozli xabarlarni qaytaradigan soxta mijoz."""

    def __init__(self, messages: list, premium_text: dict[int, str] | None = None) -> None:
        self.messages = messages
        self.premium_text = premium_text or {}
        self.transcribe_calls = 0
        self.downloads = 0
        self.iter_messages = _AsyncList(messages)

    async def __call__(self, request):
        name = type(request).__name__
        if name == "TranscribeAudioRequest":
            self.transcribe_calls += 1
            text = self.premium_text.get(request.msg_id, "")
            return SimpleNamespace(text=text, pending=not text)
        raise AssertionError(f"kutilmagan so'rov: {name}")

    async def download_media(self, message, file=None):
        self.downloads += 1
        return f"{file}/voice-{message.id}.ogg"


@pytest.fixture
def cache_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tg, "STATE_DIR", tmp_path)
    monkeypatch.setattr(tg, "TRANSCRIPT_CACHE", tmp_path / "transcripts.json")
    return tmp_path / "transcripts.json"


def _wire(monkeypatch, client: _VoiceClient) -> None:
    async def fake_client():
        return client

    async def fake_resolve(_client, who):
        return SimpleNamespace(id=777), "Asad"

    monkeypatch.setattr(tg, "get_client", fake_client)
    monkeypatch.setattr(tg, "resolve", fake_resolve)
    monkeypatch.setattr(tg, "_when", lambda m: "2026-03-01 12:00")
    monkeypatch.setattr(tg, "_sender_name", lambda m: "Asad")


# --- Aylantirish --------------------------------------------------------------


async def test_telegram_transcription_is_preferred(cache_file, monkeypatch):
    """Telegramning o'zi aylantira olsa, fayl yuklab olinmaydi."""
    client = _VoiceClient([_voice_message(1)], premium_text={1: "pulni berdim"})
    _wire(monkeypatch, client)

    rows = await tg.voice_transcripts("Asad", limit=5)

    assert rows[0]["matn"] == "pulni berdim"
    assert client.downloads == 0, "Premium aylantirsa, yuklab olish shart emas"


async def test_local_transcription_is_the_fallback(cache_file, monkeypatch):
    """Premium bo'lmasa, fayl yuklab olinib o'zimiznikiga beriladi."""
    client = _VoiceClient([_voice_message(1)])
    _wire(monkeypatch, client)

    async def fake_local(path):
        return "besh ming dollar berdim"

    monkeypatch.setattr(tg, "_local_transcribe", fake_local)

    rows = await tg.voice_transcripts("Asad", limit=5)

    assert "besh ming" in rows[0]["matn"]
    assert client.downloads == 1


async def test_transcripts_are_cached(cache_file, monkeypatch):
    """Ikkinchi qidiruv qaytadan aylantirmasligi kerak — aks holda har
    safar daqiqalab kutiladi."""
    client = _VoiceClient([_voice_message(1)], premium_text={1: "berdim"})
    _wire(monkeypatch, client)

    await tg.voice_transcripts("Asad", limit=5)
    first = client.transcribe_calls
    await tg.voice_transcripts("Asad", limit=5)

    assert client.transcribe_calls == first, "kesh ishlamadi"
    assert cache_file.exists()


# --- Qidiruv ------------------------------------------------------------------


async def test_voice_search_finds_the_phrase(cache_file, monkeypatch):
    client = _VoiceClient(
        [_voice_message(1), _voice_message(2)],
        premium_text={1: "ertaga uchrashamiz", 2: "besh ming dollarni berdim"},
    )
    _wire(monkeypatch, client)

    result = await tg.voice_search("Asad", "besh ming")

    assert result["topildi"] == 1
    assert result["natijalar"][0]["id"] == 2


async def test_voice_search_says_nothing_found(cache_file, monkeypatch):
    """Topilmagan narsani «yo'q» deb aytish ham natija — taxmin emas."""
    client = _VoiceClient([_voice_message(1)], premium_text={1: "salom"})
    _wire(monkeypatch, client)

    result = await tg.voice_search("Asad", "besh ming dollar")

    assert result["topildi"] == 0
    assert result["qidirildi"] == 1


async def test_empty_query_is_refused(cache_file, monkeypatch):
    _wire(monkeypatch, _VoiceClient([]))

    with pytest.raises(tg.TelegramUserError, match="ayting"):
        await tg.voice_search("Asad", "   ")


# --- Eksport ------------------------------------------------------------------


async def test_export_writes_a_file_with_both_kinds(cache_file, monkeypatch, tmp_path):
    """Faylda matn ham, ovozli ham bo'lishi kerak — vaqt bo'yicha tartibda."""
    client = _VoiceClient(
        [_text_message(1, "qachon berasiz?"), _voice_message(2)],
        premium_text={2: "kecha besh ming berdim"},
    )
    _wire(monkeypatch, client)

    result = await tg.export_chat("Asad", limit=10, out_dir=str(tmp_path))

    text = (tmp_path / result["fayl"].rsplit("/", 1)[-1]).read_text(encoding="utf-8")
    assert "qachon berasiz?" in text
    assert "[ovozli] kecha besh ming berdim" in text
    assert result["ovozli"] == 1
    assert result["xabar"] == 2


async def test_export_survives_one_broken_recording(cache_file, monkeypatch, tmp_path):
    """Uzun suhbatda bitta buzuq yozuv butun ishni yo'qqa chiqarmasin."""
    client = _VoiceClient([_voice_message(1), _voice_message(2)],
                          premium_text={2: "ikkinchisi aylandi"})
    _wire(monkeypatch, client)

    async def broken(path):
        raise RuntimeError("fayl buzuq")

    monkeypatch.setattr(tg, "_local_transcribe", broken)

    result = await tg.export_chat("Asad", limit=10, out_dir=str(tmp_path))

    text = (tmp_path / result["fayl"].rsplit("/", 1)[-1]).read_text(encoding="utf-8")
    assert "(aylantirilmadi)" in text, "aylanmagani ham faylda ko'rinishi kerak"
    assert "ikkinchisi aylandi" in text


async def test_export_can_skip_voice(cache_file, monkeypatch, tmp_path):
    """Tez eksport kerak bo'lsa, ovozlisiz ham bo'ladi."""
    client = _VoiceClient([_text_message(1, "salom"), _voice_message(2)])
    _wire(monkeypatch, client)

    result = await tg.export_chat("Asad", limit=10, voice=False, out_dir=str(tmp_path))

    assert result["ovozli"] == 0
    assert client.transcribe_calls == 0


def test_voice_message_is_recognised():
    assert tg._is_voice(_voice_message(1)) is True
    assert tg._is_voice(_text_message(1, "matn")) is False


def test_round_video_counts_as_voice():
    """Doira-video ham «gapirib yuborilgan» xabar."""
    document = SimpleNamespace(attributes=[SimpleNamespace(round_message=True)])
    message = SimpleNamespace(id=9, media=SimpleNamespace(document=document))
    assert tg._is_voice(message) is True
