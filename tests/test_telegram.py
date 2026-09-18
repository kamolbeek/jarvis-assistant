"""Telegram boshqaruvi — tarmoqsiz tekshiriladigan qismlari.

Haqiqiy Telegram bilan gaplashib bo'lmaydi (hisob va kod kerak), lekin eng
ko'p xato qiladigan joylar aynan tarmoqdan oldin: papka nomini qaysi turda
yuborish, qaysi suhbat allaqachon papkada borligini aniqlash, nomni suhbatga
aylantirish. Shular shu yerda sinaladi.
"""

from __future__ import annotations

import pytest

from jarvis.tools import telegram as tg

telethon = pytest.importorskip("telethon")
from telethon.tl import types  # noqa: E402 — kutubxona bor-yo'qligi tekshirilgandan keyin


# --- Nomlar va turlar ---------------------------------------------------------


def test_entity_title_prefers_title_then_name():
    channel = types.Channel(id=9, title="Click Jobs", photo=None, date=None)
    user = types.User(id=7, first_name="Ali", last_name="Vali")
    anonymous = types.User(id=8, username="kamol")

    assert tg.entity_title(channel) == "Click Jobs"
    assert tg.entity_title(user) == "Ali Vali"
    assert tg.entity_title(anonymous) == "@kamol"


def test_describe_kind_separates_channel_from_supergroup():
    """Kanal va superguruh bitta turdagi obyekt — farqi faqat bitta bayroqda.

    Bu farq muhim: kanalga yozish huquqi boshqacha, a'zolar ro'yxati boshqacha.
    """
    assert tg.describe_kind(types.Channel(id=1, title="K", photo=None, date=None)) == "kanal"
    assert tg.describe_kind(
        types.Channel(id=2, title="G", photo=None, date=None, megagroup=True)
    ) == "superguruh"
    assert tg.describe_kind(types.User(id=3, first_name="A")) == "shaxs"
    assert tg.describe_kind(types.User(id=4, first_name="B", bot=True)) == "bot"


# --- Papka nomi ---------------------------------------------------------------


def test_folder_title_round_trip():
    """Nom yuborilgan ko'rinishda qaytib o'qilishi kerak."""
    title = tg._make_title("Ish / Vakansiya")
    assert tg._filter_title(types.DialogFilter(
        id=2, title=title, pinned_peers=[], include_peers=[], exclude_peers=[],
    )) == "Ish / Vakansiya"


def test_folder_title_accepts_plain_string():
    """Eski Telethon papka nomini oddiy satr sifatida qaytaradi.

    Ikkala ko'rinish ham o'qilishi kerak — aks holda kutubxona yangilanganda
    papkalar ro'yxati bo'sh nomlar bilan chiqadi.
    """

    class OldStyle:
        title = "Ish"

    assert tg._filter_title(OldStyle()) == "Ish"


# --- Papka identifikatori -----------------------------------------------------


def test_free_folder_id_starts_at_two():
    """0 va 1 Telegram uchun band (barcha suhbatlar va arxiv)."""
    assert tg._free_filter_id([]) == tg.FIRST_FOLDER_ID == 2


def test_free_folder_id_skips_used():
    used = [types.DialogFilter(id=i, title=tg._make_title(str(i)), pinned_peers=[],
                               include_peers=[], exclude_peers=[]) for i in (2, 3, 5)]
    assert tg._free_filter_id(used) == 4


# --- Suhbatni taqqoslash ------------------------------------------------------


def test_peer_key_distinguishes_kinds():
    """Kanal 9 va foydalanuvchi 9 — bir xil raqam, boshqa suhbat."""
    channel = types.InputPeerChannel(channel_id=9, access_hash=1)
    user = types.InputPeerUser(user_id=9, access_hash=1)
    assert tg._peer_key(channel) != tg._peer_key(user)


def test_peer_key_ignores_access_hash():
    """Access hash seansga bog'liq va o'zgarishi mumkin — u taqqoslashga kirmaydi."""
    first = types.InputPeerChannel(channel_id=9, access_hash=111)
    second = types.InputPeerChannel(channel_id=9, access_hash=222)
    assert tg._peer_key(first) == tg._peer_key(second)


# --- Soxta mijoz bilan to'liq oqim --------------------------------------------


class FakeDialog:
    def __init__(self, entity):
        self.entity = entity
        self.unread_count = 0


class FakeClient:
    """Telethon mijozining kerakli qismini taqlid qiladi."""

    def __init__(self, entities, filters=None):
        self._entities = entities
        self.filters = list(filters or [])
        self.sent: list = []
        self.scans = 0

    def is_connected(self):
        return True

    def iter_dialogs(self):
        self.scans += 1
        entities = self._entities

        class Iterator:
            def __aiter__(self):
                self._items = iter(entities)
                return self

            async def __anext__(self):
                try:
                    return FakeDialog(next(self._items))
                except StopIteration:
                    raise StopAsyncIteration from None

        return Iterator()

    async def get_input_entity(self, entity):
        return types.InputPeerChannel(channel_id=entity.id, access_hash=0)

    async def __call__(self, request):
        from telethon.tl import functions

        if isinstance(request, functions.messages.GetDialogFiltersRequest):
            return types.messages.DialogFilters(filters=self.filters)
        if isinstance(request, functions.messages.UpdateDialogFilterRequest):
            self.sent.append(request)
            self.filters = [f for f in self.filters
                            if getattr(f, "id", None) != request.id]
            if request.filter is not None:
                self.filters.append(request.filter)
            return True
        raise AssertionError(f"kutilmagan so'rov: {type(request).__name__}")


@pytest.fixture
def fake_telegram(monkeypatch):
    """Modul darajasidagi ulanishni soxta mijoz bilan almashtiradi."""
    channels = [
        types.Channel(id=101, title="Click Jobs", photo=None, date=None),
        types.Channel(id=102, title="UzDev Jobs", photo=None, date=None),
        types.Channel(id=103, title="Freelancer Uz", photo=None, date=None),
    ]
    client = FakeClient(channels)

    async def fake_client():
        return client

    monkeypatch.setattr(tg, "client", fake_client)
    # Kesh modul darajasida — bir sinov ikkinchisiga o'tib ketmasin.
    tg.forget_dialogs()
    yield client
    tg.forget_dialogs()


async def test_folder_set_creates_folder_with_channels(fake_telegram):
    message = await tg.folder_set("Ish", add=["Click Jobs", "UzDev Jobs"])

    assert "yaratildi" in message
    created = fake_telegram.filters[0]
    assert tg._filter_title(created) == "Ish"
    assert len(created.include_peers) == 2
    # Toifa bo'yicha avtomatik qo'shish yoqilmasligi kerak — papkada aynan
    # sanab o'tilganlar turishi shart.
    assert created.groups is False
    assert created.broadcasts is False


async def test_folder_set_is_idempotent(fake_telegram):
    """Bir xil kanalni ikki marta qo'shish uni ikkilantirmasligi kerak."""
    await tg.folder_set("Ish", add=["Click Jobs"])
    await tg.folder_set("Ish", add=["Click Jobs", "UzDev Jobs"])

    stored = fake_telegram.filters[0]
    assert len(stored.include_peers) == 2


async def test_folder_set_removes_channel(fake_telegram):
    await tg.folder_set("Ish", add=["Click Jobs", "UzDev Jobs"])
    message = await tg.folder_set("Ish", remove=["Click Jobs"])

    assert "olib tashlandi" in message
    assert len(fake_telegram.filters[0].include_peers) == 1


async def test_folder_set_refuses_to_empty_a_folder(fake_telegram):
    """Bo'sh papka Telegram tomonidan rad etiladi — sababini oldindan aytamiz."""
    await tg.folder_set("Ish", add=["Click Jobs"])
    with pytest.raises(tg.TelegramError, match="bo'sh qolmasligi"):
        await tg.folder_set("Ish", remove=["Click Jobs"])


async def test_resolve_by_name_is_case_insensitive(fake_telegram):
    entity = await tg.resolve("click jobs")
    assert entity.id == 101


async def test_resolve_refuses_ambiguous_name(fake_telegram):
    """Ikkita kanal mos kelsa, taxmin qilinmaydi — noto'g'ri joyga yozib
    yuborishdan ko'ra qayta so'ragan afzal."""
    with pytest.raises(tg.TelegramError, match="bir nechtasi"):
        await tg.resolve("Jobs")


async def test_resolve_unknown_name_suggests_next_step(fake_telegram):
    with pytest.raises(tg.TelegramError, match="tg_chats"):
        await tg.resolve("Bunday kanal yo'q")


async def test_resolve_self_words_map_to_saved_messages(fake_telegram):
    assert await tg.resolve("men") == "me"
    assert await tg.resolve("") == "me"


async def test_folder_delete_removes_only_the_folder(fake_telegram):
    await tg.folder_set("Ish", add=["Click Jobs"])
    message = await tg.folder_delete("Ish")

    assert "suhbatlar joyida" in message
    assert fake_telegram.filters == []


async def test_folder_delete_reports_missing_folder(fake_telegram):
    with pytest.raises(tg.TelegramError, match="topilmadi"):
        await tg.folder_delete("Yo'q papka")


# --- Xatolarni tushunarli qilish ----------------------------------------------


@pytest.mark.parametrize(
    ("error_name", "expected"),
    [
        ("UserPrivacyRestrictedError", "maxfiylik"),
        ("UserNotMutualContactError", "kontaktiga"),
        ("PeerFloodError", "cheklab"),
        ("UserAlreadyParticipantError", "a'zo"),
    ],
)
def test_invite_failure_has_a_human_reason(error_name: str, expected: str):
    """«Qo'shilmadi» degan javob o'zi hech nima tushuntirmaydi.

    Odam qo'shilmasligining sabablari turlicha va har birida foydalanuvchi
    boshqa ish qilishi kerak — shuning uchun sabab aytilishi shart.
    """
    exc = type(error_name, (Exception,), {})("xom matn")
    assert expected in tg._invite_reason(exc)


def test_unknown_invite_error_falls_back_to_raw_text():
    assert "nimadir" in tg._invite_reason(RuntimeError("nimadir buzildi"))


# --- Suhbatlar keshi ----------------------------------------------------------


async def test_dialogs_are_scanned_once_for_many_lookups(fake_telegram):
    """O'n ikkita kanalni papkaga solish o'n ikki marta skanerlash bo'lmasin.

    Har bir nomni yechish uchun butun ro'yxatni tarmoqdan olish — bu bitta
    oddiy ish uchun o'nlab so'rov degani.
    """
    await tg.folder_set("Ish", add=["Click Jobs", "UzDev Jobs", "Freelancer Uz"])
    assert fake_telegram.scans == 1


async def test_new_chat_invalidates_the_cache(fake_telegram):
    """Yangi kanal ochilgach, uni darhol topa olish kerak."""
    await tg.resolve("Click Jobs")
    assert fake_telegram.scans == 1

    tg.forget_dialogs()
    await tg.resolve("Click Jobs")
    assert fake_telegram.scans == 2
