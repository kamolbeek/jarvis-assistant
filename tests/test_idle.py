"""Sukut holati: uzoq jimlikdan keyin so'nish, chaqirilganda qaytish.

Vaqtni kutib o'tirmaymiz — soat qiymatini o'zimiz beramiz. Shu sababli
mantiq alohida modulda: uni mikrofonsiz ham, oynasiz ham sinash mumkin.
"""

from __future__ import annotations

from jarvis.idle import StandbyWatch


def test_stays_awake_before_the_timeout():
    watch = StandbyWatch(after_sec=300)
    watch.touch(1000.0)

    assert watch.due(1000.0 + 299) is False
    assert watch.on is False


def test_goes_to_standby_after_the_timeout():
    watch = StandbyWatch(after_sec=300)
    watch.touch(1000.0)

    assert watch.due(1000.0 + 300) is True
    assert watch.force(1000.0 + 300) is True
    assert watch.on is True


def test_standby_is_announced_only_once():
    """Sukutga o'tgach, taymer yana «o'tdi» demasligi kerak — sahna bir marta yopiladi."""
    watch = StandbyWatch(after_sec=60)
    watch.touch(0.0)
    watch.force(100.0)

    assert watch.due(200.0) is False
    assert watch.due(9999.0) is False
    assert watch.force(9999.0) is False, "ikkinchi marta yopish buyrug'i berilmaydi"


def test_cancel_goes_to_standby_immediately():
    """«Bekor qil» — vaqt tugashini kutmaydi."""
    watch = StandbyWatch(after_sec=300)
    watch.touch(1000.0)

    assert watch.due(1001.0) is False, "hali vaqti kelmagan"
    assert watch.force(1001.0) is True
    assert watch.on is True


def test_cancel_works_even_when_standby_is_disabled():
    """Taymer o'chirilgan bo'lsa ham, aniq aytilgan «bekor qil» ishlaydi."""
    watch = StandbyWatch(after_sec=0)

    assert watch.force(5.0) is True
    assert watch.on is True


def test_activity_wakes_it_up():
    watch = StandbyWatch(after_sec=60)
    watch.touch(0.0)
    watch.force(100.0)

    assert watch.touch(101.0) is True, "sukutdan qaytgani bir marta bildiriladi"
    assert watch.on is False
    assert watch.touch(102.0) is False, "uyg'oq holatda qayta bildirilmaydi"


def test_timer_restarts_after_each_interaction():
    watch = StandbyWatch(after_sec=60)
    watch.touch(0.0)

    watch.touch(50.0)
    assert watch.due(100.0) is False, "50-soniyadagi muloqot hisobni qaytadan boshlaydi"
    assert watch.due(111.0) is True


def test_zero_disables_standby():
    watch = StandbyWatch(after_sec=0)
    watch.touch(0.0)

    assert watch.enabled is False
    assert watch.due(1e9) is False
    assert watch.on is False


def test_remaining_counts_down_and_never_goes_negative():
    watch = StandbyWatch(after_sec=300)
    watch.touch(1000.0)

    assert watch.remaining(1000.0) == 300
    assert watch.remaining(1100.0) == 200
    assert watch.remaining(1e9) == 0.0
