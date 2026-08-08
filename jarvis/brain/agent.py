"""Jarvis miyasi — Claude Agent SDK ustidagi qatlam.

Bu yerdagi asosiy nozik nuqta — **kechikish**. Agar to'liq javob yozilib bo'lgunicha
kutib, keyin ovozga aylantirsak, foydalanuvchi bir necha soniya jimlikni eshitadi.
Shuning uchun javob gap-gap bo'lib chiqariladi: birinchi gap tayyor bo'lishi bilan
Jarvis gapira boshlaydi, qolgani orqada yozilishda davom etadi.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..bus import EventBus
from ..config import Config
from ..safety.gate import SafetyGate
from .agenda import Agenda
from .memory import Memory
from .prompts import build_system_prompt

log = logging.getLogger("jarvis.brain")

# Gap oxiri: nuqta/savol/undov + probel yoki satr oxiri.
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n{2,}")
# Juda qisqa bo'lakni alohida gapirmaymiz — bo'g'iq eshitiladi.
MIN_SENTENCE_CHARS = 12

# Ovozda ma'nosiz markdown belgilari.
_MARKDOWN_NOISE = re.compile(r"[*_`#]+")
_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)


WEEKDAYS_UZ = (
    "dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba",
)


def now_line() -> str:
    """Modelga joriy vaqtni bildiruvchi qator."""
    moment = datetime.now()
    return (
        f"hozir: {moment.strftime('%Y-%m-%d %H:%M')}, "
        f"{WEEKDAYS_UZ[moment.weekday()]}"
    )


def clean_for_speech(text: str) -> str:
    """Matnni ovozga chiqarishga tayyorlaydi: markdown va kod bloklarini olib tashlaydi."""
    text = _CODE_BLOCK.sub(" kod bloki ", text)
    text = _MARKDOWN_NOISE.sub("", text)
    # Ro'yxat belgilarini olib tashlaymiz
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    return " ".join(text.split())


@dataclass
class Brain:
    """Suhbat konteksti saqlanadigan agent seansi."""

    config: Config
    bus: EventBus
    memory: Memory
    agenda: Agenda
    gate: SafetyGate
    # Jarvis'ga darhol gapirish imkonini beruvchi qayta chaqiruv (yadro beradi).
    announce: Callable[[str], Awaitable[None]]

    _client: Any = None
    _mcp_server: Any = None
    _session_id: str = "jarvis"
    _last_reply: str = ""
    _system_prompt: str = field(default="", repr=False)

    # --- Hayot sikli ---

    async def start(self) -> None:
        # SDK importlari shu yerda: shunda `clean_for_speech` kabi sof
        # funksiyalarni SDK o'rnatmasdan ham ishlatish (va sinash) mumkin.
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

        from ..tools import server as tools_server

        self.config.ensure_dirs()
        self._mcp_server = tools_server.build_server(self.memory, self.agenda, self.announce)
        self._system_prompt = self._build_prompt()

        options = ClaudeAgentOptions(
            system_prompt=self._system_prompt,
            model=str(self.config.get("brain.model", "claude-opus-5")),
            cwd=str(self.config.workspace),
            mcp_servers={tools_server.SERVER_NAME: self._mcp_server},
            # Tasdiqni biz o'zimiz boshqaramiz — SDK terminalda so'ramasin.
            permission_mode="default",
            can_use_tool=self.gate.can_use_tool,
            allowed_tools=self._allowed_tools(),
            max_turns=int(self.config.get("brain.max_turns", 40)),
            max_budget_usd=self.config.get("brain.max_budget_usd"),
        )

        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()
        log.info("Miya ulandi (model: %s)", options.model)

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
            log.info("Miya uzildi")

    def _build_prompt(self) -> str:
        return build_system_prompt(
            name=str(self.config.get("identity.name", "Jarvis")),
            user_name=str(self.config.get("identity.user_name", "foydalanuvchi")),
            workspace=str(self.config.workspace),
            memory_context=self.memory.context_block(),
        )

    def _allowed_tools(self) -> list[str]:
        """`ask` talab qilmaydigan asboblar — ular darvozadan tez o'tadi."""
        from ..tools import server as tools_server

        allowed = ["Read", "Glob", "Grep", "WebSearch", "WebFetch"]
        allowed += tools_server.read_only_tool_names()
        return allowed

    # --- Suhbat ---

    async def ask(self, text: str) -> AsyncIterator[str]:
        """Savol beradi va javobni **gap-gap** qaytaradi (ovozga darhol berish uchun).

        To'liq javob `last_reply` xususiyatida saqlanadi.
        """
        if self._client is None:
            raise RuntimeError("Miya ishga tushirilmagan — avval `start()` chaqiring")

        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

        # Xotiraga foydalanuvchi aytgan matnni saqlaymiz, modelga esa vaqt bilan
        # birga yuboramiz. Vaqtsiz «ertaga soat 10 da» ni sanaga aylantirib
        # bo'lmaydi, tizim ko'rsatmasi esa seans davomida o'zgarmaydi — shuning
        # uchun uni har bir savolga qo'shib turamiz.
        self.memory.add_turn(self._session_id, "user", text)
        await self._client.query(f"[{now_line()}]\n{text}")

        buffer = ""
        full: list[str] = []

        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if not isinstance(block, TextBlock):
                        continue
                    chunk = block.text
                    full.append(chunk)
                    buffer += chunk

                    # To'liq gaplarni ajratib chiqaramiz
                    while True:
                        match = SENTENCE_END.search(buffer)
                        if match is None:
                            break
                        sentence = buffer[: match.start()].strip()
                        buffer = buffer[match.end() :]
                        spoken = clean_for_speech(sentence)
                        if len(spoken) >= MIN_SENTENCE_CHARS:
                            yield spoken
                        elif spoken:
                            # Juda qisqa — keyingisiga qo'shib yuboramiz
                            buffer = spoken + " " + buffer

            elif isinstance(message, ResultMessage):
                reason = getattr(message, "terminal_reason", "")
                if reason and reason not in ("end_turn", "success"):
                    log.warning("Javob tugash sababi: %s", reason)

        # Qolgan qismini chiqaramiz
        tail = clean_for_speech(buffer)
        if tail:
            yield tail

        self._last_reply = "".join(full).strip()
        if self._last_reply:
            self.memory.add_turn(self._session_id, "assistant", self._last_reply)

    @property
    def last_reply(self) -> str:
        return self._last_reply

    async def interrupt(self) -> None:
        """Joriy ishni to'xtatadi (foydalanuvchi «to'xta» desa)."""
        if self._client is not None:
            try:
                await self._client.interrupt()
                log.info("Ish to'xtatildi")
            except Exception:
                log.exception("To'xtatib bo'lmadi")

    async def refresh_memory_context(self) -> None:
        """Xotira o'zgargandan keyin tizim ko'rsatmasini yangilaydi.

        SDK tizim ko'rsatmasini seans o'rtasida almashtira olmaydi, shuning uchun
        yangi faktlarni oddiy xabar sifatida yuboramiz — bu keshni ham buzmaydi.
        """
        if self._client is None:
            return
        context = self.memory.context_block()
        if context:
            await self._client.query(
                "[tizim eslatmasi] Xotirangdagi faktlar yangilandi:\n" + context
            )
            async for _ in self._client.receive_response():
                pass
