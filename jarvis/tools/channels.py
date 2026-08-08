"""Tashqi kanallar: Telegram va n8n.

Diqqat: Telegram bu yerda **interfeys emas**. Jarvis bilan gaplashish ovoz orqali
bo'ladi; Telegram esa faqat chiqish kanali — Jarvis kompyuterda ish qilib turib
sizga xabar yuborishi uchun (masalan, uzoq ish tugaganda).
"""

from __future__ import annotations

import logging

import httpx

from ..config import env

log = logging.getLogger("jarvis.tools.channels")


class ChannelError(RuntimeError):
    """Kanalga yuborib bo'lmadi."""


async def send_telegram(text: str, chat_id: str = "") -> str:
    """Telegram orqali xabar yuboradi."""
    token = env("TELEGRAM_BOT_TOKEN")
    target = chat_id or env("TELEGRAM_CHAT_ID")
    if not token or not target:
        raise ChannelError(
            "Telegram sozlanmagan — .env da TELEGRAM_BOT_TOKEN va TELEGRAM_CHAT_ID ni to'ldiring"
        )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": target, "text": text, "disable_web_page_preview": True},
        )
        if response.status_code != 200:
            raise ChannelError(f"Telegram xatosi {response.status_code}: {response.text[:200]}")

    log.info("Telegram xabari yuborildi (%d belgi)", len(text))
    return "Telegram'ga yuborildi"


async def call_n8n(payload: dict, url: str = "") -> str:
    """n8n webhook'ini chaqiradi — mavjud avtomatlashtirishlaringizga ulanish uchun."""
    endpoint = url or env("N8N_WEBHOOK_URL")
    if not endpoint:
        raise ChannelError("n8n sozlanmagan — .env da N8N_WEBHOOK_URL ni to'ldiring")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(endpoint, json=payload)
        if response.status_code >= 400:
            raise ChannelError(f"n8n xatosi {response.status_code}: {response.text[:200]}")
        return response.text[:2000] or "n8n chaqirildi"
