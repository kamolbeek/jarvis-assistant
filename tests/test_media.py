"""YouTube qidiruv natijasidan videoni ajratish.

Bu qismning zaifligi oldindan ma'lum: u YouTube sahifasining tuzilishiga
tayanadi. Shuning uchun ajratish alohida funksiyada va testlar aynan
sahifada uchraydigan shakllarni tekshiradi — tuzilish o'zgarsa, testlar
darhol qizaradi va sabab aniq bo'ladi.
"""

from __future__ import annotations

from jarvis.tools.media import first_video, watch_url

# Sahifadagi haqiqiy shaklga yaqin bo'lak.
PAGE = (
    '{"responseContext":{},"contents":{"twoColumnSearchResultsRenderer":'
    '{"primaryContents":{"sectionListRenderer":{"contents":[{"itemSectionRenderer":'
    '{"contents":[{"videoRenderer":{"videoId":"dQw4w9WgXcQ","thumbnail":{},'
    '"title":{"runs":[{"text":"Roshka - Ishondingmi (Official Music Video)"}]},'
    '"longBylineText":{}}},{"videoRenderer":{"videoId":"aaaaaaaaaaa",'
    '"title":{"runs":[{"text":"Boshqa video"}]}}}]}}]}}}}'
)


def test_first_result_is_taken():
    found = first_video(PAGE)

    assert found is not None
    assert found[0] == "dQw4w9WgXcQ"
    assert found[1] == "Roshka - Ishondingmi (Official Music Video)"


def test_escaped_characters_in_the_title_are_decoded():
    """Sahifada `&` va tirnoq qochirilgan holda keladi."""
    page = ('{"videoId":"abcdefghijk","title":{"runs":[{"text":'
            '"Sevinch \\u0026 Ozoda - \\"Yor\\""}]}}')

    found = first_video(page)

    assert found == ("abcdefghijk", 'Sevinch & Ozoda - "Yor"')


def test_video_without_a_title_still_plays():
    """Sarlavha topilmasa ham qo'shiq qo'yilishi kerak — asosiysi ID."""
    found = first_video('{"videoId":"12345678901","boshqa":"maydon"}')

    assert found == ("12345678901", "")


def test_empty_or_broken_page_returns_nothing():
    assert first_video("") is None
    assert first_video("<html>hech nima yo'q</html>") is None


def test_ids_are_exactly_eleven_characters():
    """Qisqa yoki uzun qiymat ID emas — noto'g'ri havola ochilmasin."""
    assert first_video('{"videoId":"qisqa"}') is None
    assert first_video('{"videoId":"juda-uzun-identifikator"}') is None


def test_watch_url_without_a_start_time():
    assert watch_url("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_watch_url_with_a_start_time():
    """«20-sekunddan qo'y» — havolaning o'zida beriladi."""
    assert watch_url("dQw4w9WgXcQ", 20).endswith("&t=20s")
    assert watch_url("dQw4w9WgXcQ", 0) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
