"""Jarvis'ning o'z asboblari — Claude Agent SDK ichidagi MCP serveri sifatida.

Bu yerdagi asboblar Claude'ning tayyor asboblari (Read/Write/Bash/WebSearch)
ustiga qo'shiladi: xotira, macOS boshqaruvi, telefon ko'prigi va kanallar.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

from ..brain.memory import Memory
from . import channels, macos

log = logging.getLogger("jarvis.tools")

SERVER_NAME = "jarvis"

# Bu asboblar tashqi dunyoga ta'sir qilmaydi — xavfsizlik darvozasi ularni
# avtomatik o'tkazib yuborishi mumkin.
READ_ONLY = ToolAnnotations(readOnlyHint=True)


def _ok(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _fail(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def build_server(memory: Memory) -> Any:
    """MCP serverini yaratadi. `memory` yopilish uchun tashqaridan beriladi."""

    # --- Xotira ---

    @tool(
        "remember",
        "Foydalanuvchi haqidagi barqaror faktni xotiraga saqlaydi. Keyingi suhbatlarda "
        "ham eslab qolinadi. Masalan: kalit='ish_vaqti', qiymat='9:00 dan 18:00 gacha'.",
        {"kalit": str, "qiymat": str, "toifa": str},
    )
    async def remember(args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("kalit", "")).strip()
        value = str(args.get("qiymat", "")).strip()
        if not key or not value:
            return _fail("`kalit` va `qiymat` bo'sh bo'lmasligi kerak")
        memory.remember(key, value, str(args.get("toifa") or "umumiy"))
        return _ok(f"Eslab qoldim: {key} = {value}")

    @tool(
        "recall",
        "Xotiradan faktni kalit bo'yicha o'qiydi.",
        {"kalit": str},
        annotations=READ_ONLY,
    )
    async def recall(args: dict[str, Any]) -> dict[str, Any]:
        value = memory.recall(str(args.get("kalit", "")))
        return _ok(value if value is not None else "Bunday fakt xotirada yo'q")

    @tool(
        "forget",
        "Faktni xotiradan o'chiradi.",
        {"kalit": str},
    )
    async def forget(args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("kalit", ""))
        return _ok(f"O'chirildi: {key}" if memory.forget(key) else "Bunday fakt topilmadi")

    @tool(
        "search_memory",
        "Xotiradagi faktlar va oldingi suhbatlar ichidan matn bo'yicha qidiradi. "
        "«kechagi hisobotni yana yubor» kabi so'rovlarda ishlating.",
        {"soz": str},
        annotations=READ_ONLY,
    )
    async def search_memory(args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("soz", "")).strip()
        if not query:
            return _fail("Qidiruv so'zi bo'sh")

        facts = memory.search(query, limit=15)
        turns = memory.search_turns(query, limit=10)
        payload = {
            "faktlar": [{"kalit": f.key, "qiymat": f.value} for f in facts],
            "suhbatlar": turns,
        }
        if not facts and not turns:
            return _ok("Hech narsa topilmadi")
        return _ok(json.dumps(payload, ensure_ascii=False, indent=2))

    # --- macOS ---

    @tool(
        "notify",
        "Ekranda macOS bildirishnomasini ko'rsatadi. Foydalanuvchi kompyuter oldida "
        "bo'lmasligi mumkin bo'lgan uzoq ishlarda foydali.",
        {"sarlavha": str, "matn": str},
    )
    async def notify(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await macos.notify(str(args.get("sarlavha", "Jarvis")), str(args.get("matn", "")))
            return _ok("Bildirishnoma ko'rsatildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "open_app",
        "Kompyuterda ilovani ochadi yoki oldinga chiqaradi. Masalan: 'Safari', 'Notes'.",
        {"nom": str},
    )
    async def open_app(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await macos.open_app(str(args.get("nom", "")))
            return _ok(f"{args.get('nom')} ochildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "open_url",
        "Havolani brauzerda ochadi.",
        {"havola": str},
    )
    async def open_url(args: dict[str, Any]) -> dict[str, Any]:
        try:
            await macos.open_url(str(args.get("havola", "")))
            return _ok("Havola ochildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "frontmost_app",
        "Hozir qaysi ilova faol ekanini aytadi.",
        {},
        annotations=READ_ONLY,
    )
    async def frontmost_app(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await macos.frontmost_app())
        except macos.MacOsError as exc:
            return _fail(str(exc))

    # --- Xabarlar va telefon ---

    @tool(
        "send_message",
        "Messages ilovasi orqali kimgadir xabar (iMessage yoki SMS) yuboradi. "
        "`kimga` — telefon raqami yoki Apple ID.",
        {"kimga": str, "matn": str},
    )
    async def send_message(args: dict[str, Any]) -> dict[str, Any]:
        recipient = str(args.get("kimga", "")).strip()
        text = str(args.get("matn", "")).strip()
        if not recipient or not text:
            return _fail("`kimga` va `matn` kerak")
        try:
            await macos.send_imessage(recipient, text)
            return _ok(f"{recipient} ga xabar yuborildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "list_shortcuts",
        "Mavjud macOS Shortcuts qisqa yo'llari ro'yxatini beradi. Telefonda amal "
        "bajarish uchun avval shu ro'yxatdan mos qisqa yo'lni toping.",
        {},
        annotations=READ_ONLY,
    )
    async def list_shortcuts(args: dict[str, Any]) -> dict[str, Any]:
        try:
            names = await macos.list_shortcuts()
            return _ok("\n".join(names) if names else "Qisqa yo'llar topilmadi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    @tool(
        "run_shortcut",
        "macOS Shortcuts qisqa yo'lini ishga tushiradi. iCloud orqali sinxronlangan "
        "qisqa yo'llar telefonda ham amal bajarishi mumkin (eslatma, xabar, joylashuv).",
        {"nom": str, "kirish": str},
    )
    async def run_shortcut(args: dict[str, Any]) -> dict[str, Any]:
        try:
            output = await macos.run_shortcut(
                str(args.get("nom", "")), str(args.get("kirish") or "")
            )
            return _ok(output or "Qisqa yo'l bajarildi")
        except macos.MacOsError as exc:
            return _fail(str(exc))

    # --- Kanallar ---

    @tool(
        "send_telegram",
        "Telegram orqali foydalanuvchiga xabar yuboradi. Uzoq davom etadigan ish "
        "tugaganda yoki kompyuter oldida bo'lmaganda xabar berish uchun.",
        {"matn": str},
    )
    async def send_telegram(args: dict[str, Any]) -> dict[str, Any]:
        try:
            return _ok(await channels.send_telegram(str(args.get("matn", ""))))
        except channels.ChannelError as exc:
            return _fail(str(exc))

    @tool(
        "call_n8n",
        "n8n webhook'ini chaqiradi va javobini qaytaradi — mavjud avtomatlashtirish "
        "jarayonlarini ishga tushirish uchun.",
        {"malumot": str},
    )
    async def call_n8n(args: dict[str, Any]) -> dict[str, Any]:
        raw = str(args.get("malumot", "{}"))
        try:
            payload = json.loads(raw) if raw.strip().startswith("{") else {"text": raw}
        except json.JSONDecodeError:
            payload = {"text": raw}
        try:
            return _ok(await channels.call_n8n(payload))
        except channels.ChannelError as exc:
            return _fail(str(exc))

    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version="0.1.0",
        tools=[
            remember, recall, forget, search_memory,
            notify, open_app, open_url, frontmost_app,
            send_message, list_shortcuts, run_shortcut,
            send_telegram, call_n8n,
        ],
    )


def tool_names() -> list[str]:
    """Barcha Jarvis asboblarining to'liq nomlari (`allowed_tools` uchun)."""
    names = [
        "remember", "recall", "forget", "search_memory",
        "notify", "open_app", "open_url", "frontmost_app",
        "send_message", "list_shortcuts", "run_shortcut",
        "send_telegram", "call_n8n",
    ]
    return [f"mcp__{SERVER_NAME}__{name}" for name in names]


def read_only_tool_names() -> list[str]:
    """Tasdiq so'ramasdan ishlatsa bo'ladigan asboblar."""
    names = ["recall", "search_memory", "frontmost_app", "list_shortcuts"]
    return [f"mcp__{SERVER_NAME}__{name}" for name in names]
