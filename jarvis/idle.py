"""Sukut holati — uzoq jimlikdan keyin Jarvis o'zini bosadi.

Jarvis doim tinglab turadi: uyg'otuvchi so'zni eshitish uchun mikrofon
hech qachon o'chmaydi. Lekin "tinglab turish" bilan "ekranni band qilib
turish" — bir narsa emas. Suhbat jimlik bilan tugaganda HUD ataylab ochiq
qoladi (foydalanuvchi davom ettirishi mumkin), va agar hech kim qaytmasa,
u shu holida soatlab turaveradi.

Shuning uchun oddiy taymer: belgilangan vaqt davomida hech qanday
muloqot bo'lmasa, sahna yopiladi va orb xiralashadi. Chaqiruv esa
ishlashda davom etadi — «Hey Jarvis» deyilishi bilan hammasi qaytadi.

Mantiq ataylab shu yerda, alohida: uni vaqt o'tishini kutmasdan,
mikrofonsiz va oynasiz sinab ko'rish mumkin.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StandbyWatch:
    """Muloqotsiz o'tgan vaqtni kuzatadi.

    `after_sec` <= 0 bo'lsa, sukut holati o'chirilgan hisoblanadi.
    """

    after_sec: float
    _last: float = field(default=0.0)
    _on: bool = field(default=False)

    @property
    def on(self) -> bool:
        """Hozir sukut holatidami?"""
        return self._on

    @property
    def enabled(self) -> bool:
        return self.after_sec > 0

    def touch(self, now: float) -> bool:
        """Muloqot bo'ldi. Sukutdan uyg'ongan bo'lsa True qaytaradi."""
        self._last = now
        if self._on:
            self._on = False
            return True
        return False

    def due(self, now: float) -> bool:
        """Sukutga o'tish vaqti keldimi? Faqat bir marta True qaytaradi."""
        if not self.enabled or self._on:
            return False
        if now - self._last < self.after_sec:
            return False
        self._on = True
        return True

    def remaining(self, now: float) -> float:
        """Sukutgacha necha soniya qolgani (0 dan kichik bo'lmaydi)."""
        if not self.enabled or self._on:
            return 0.0
        return max(0.0, self.after_sec - (now - self._last))
