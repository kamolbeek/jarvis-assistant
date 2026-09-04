"""Xavfsizlik darvozasi — "mensiz to'liq nazorat" g'oyasining eng xavfli qismini ushlab turadi.

Jarvis kompyuterni boshqara olishi kerak, lekin `rm -rf` yozib yuborishi kerak emas.
Shuning uchun har bir asbob chaqiruvi shu yerdan o'tadi va uch qarordan birini oladi:

    allow  — avtomatik bajariladi (o'qish, qidiruv kabi qaytarib bo'ladigan amallar)
    ask    — foydalanuvchidan tasdiq so'raladi (yozish, shell)
    deny   — umuman bajarilmaydi

Ishonch ortgan sari `config/jarvis.yaml` dagi qoidalarni yumshatib borish mumkin.
Boshidan hammasiga ruxsat bermang.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..bus import EventBus
from ..config import Config, expand

log = logging.getLogger("jarvis.safety")

# Fayl yo'lini o'z ichiga oluvchi asboblar va ularning parametr nomlari.
PATH_ARG_BY_TOOL = {
    "Write": "file_path",
    "Edit": "file_path",
    "NotebookEdit": "notebook_path",
    "Read": "file_path",
}

# Bu asboblar uchun tasdiq hech qachon "eslab qolinmaydi": har chaqiruv
# alohida so'raladi. Sabab — natija tashqariga chiqadi va qaytarib bo'lmaydi:
# boshqa odamga ketgan xabarni orqaga qaytarish imkoni yo'q.
ALWAYS_ASK_SUFFIXES = ("telegram_send",)

# Shell buyruqlaridagi yozish operatorlari — yo'lni tekshirish uchun belgi.
_REDIRECT_RE = re.compile(r"(?<![0-9<>])>{1,2}\s*(\S+)")


@dataclass
class Decision:
    """Bitta qaror natijasi."""

    allowed: bool
    reason: str = ""
    asked: bool = False


@dataclass
class SafetyGate:
    """Asbob chaqiruvlarini tekshiradi, kerak bo'lsa tasdiq so'raydi va jurnalga yozadi."""

    config: Config
    bus: EventBus

    _rules: dict[str, str] = field(default_factory=dict)
    _default: str = "ask"
    _forbidden: list[str] = field(default_factory=list)
    _writable: list[Path] = field(default_factory=list)
    _audit_path: Path | None = None
    # Bitta seansda tasdiqlangan amallar — qayta-qayta so'ramaslik uchun
    _session_grants: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._rules = {k: str(v).lower() for k, v in self.config.section("safety.rules").items()}
        self._default = str(self.config.get("safety.default", "ask")).lower()
        self._forbidden = [str(p) for p in (self.config.get("safety.forbidden_patterns") or [])]
        self._writable = self.config.writable_roots()
        self._audit_path = self.config.audit_log
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Claude Agent SDK ulanish nuqtasi ---

    async def can_use_tool(
        self, tool_name: str, input_data: dict[str, Any], context: Any = None
    ) -> Any:
        """Claude Agent SDK'ning `can_use_tool` qayta chaqiruvi."""
        from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

        decision = await self.evaluate(tool_name, input_data)
        self._audit(tool_name, input_data, decision)

        if decision.allowed:
            return PermissionResultAllow(updated_input=input_data)
        return PermissionResultDeny(message=decision.reason or "Foydalanuvchi rad etdi")

    # --- Qaror mantig'i ---

    async def evaluate(self, tool_name: str, input_data: dict[str, Any]) -> Decision:
        # 1. Mutlaq taqiqlar — tasdiq ham so'ralmaydi.
        blocked = self._check_forbidden(tool_name, input_data)
        if blocked:
            log.warning("Taqiqlangan amal to'xtatildi: %s", blocked)
            await self.bus.log_line(f"To'xtatildi: {blocked}", level="error")
            return Decision(False, f"Bu amal taqiqlangan: {blocked}")

        # 2. Yozish papkadan tashqarigami?
        outside = self._check_writable(tool_name, input_data)
        if outside:
            log.warning("Ruxsat etilmagan papkaga yozish: %s", outside)
            return Decision(
                False,
                f"`{outside}` ruxsat etilgan papkalardan tashqarida. "
                f"Kerak bo'lsa, uni `safety.writable_roots` ga qo'shing.",
            )

        # 3. Qoidalar jadvali.
        policy = self._rules.get(tool_name, self._default)
        # `trust on` (default: allow) ham buni yumshata olmaydi — qaytarib
        # bo'lmaydigan tashqi amal har safar tasdiq so'raydi.
        if policy != "deny" and tool_name.endswith(ALWAYS_ASK_SUFFIXES):
            policy = "ask"
        if policy == "allow":
            return Decision(True)
        if policy == "deny":
            return Decision(False, f"`{tool_name}` konfiguratsiyada taqiqlangan")

        # 4. Tasdiq so'rash — lekin bu seansda allaqachon tasdiqlangan bo'lsa, so'ramaymiz.
        once_only = tool_name.endswith(ALWAYS_ASK_SUFFIXES)
        signature = self._signature(tool_name, input_data)
        if not once_only and signature in self._session_grants:
            return Decision(True, "seansda allaqachon tasdiqlangan")

        action, detail = self._describe(tool_name, input_data)
        approved = await self.bus.request_confirm(action, detail)
        if approved and not once_only:
            self._session_grants.add(signature)
        return Decision(approved, "" if approved else "Foydalanuvchi rad etdi", asked=True)

    def _check_forbidden(self, tool_name: str, input_data: dict[str, Any]) -> str | None:
        """Taqiqlangan naqsh topilsa, uni qaytaradi."""
        haystacks: list[str] = []
        if tool_name == "Bash":
            haystacks.append(str(input_data.get("command", "")))
        else:
            haystacks.extend(str(v) for v in input_data.values() if isinstance(v, str))

        for text in haystacks:
            normalized = " ".join(text.split())
            for pattern in self._forbidden:
                if pattern in normalized:
                    return pattern
        return None

    def _check_writable(self, tool_name: str, input_data: dict[str, Any]) -> str | None:
        """Ruxsat etilmagan papkaga yozish bo'lsa, o'sha yo'lni qaytaradi."""
        targets: list[str] = []

        arg = PATH_ARG_BY_TOOL.get(tool_name)
        if arg and tool_name != "Read":  # O'qish har joydan mumkin
            value = input_data.get(arg)
            if isinstance(value, str) and value:
                targets.append(value)

        if tool_name == "Bash":
            targets.extend(self._redirect_targets(str(input_data.get("command", ""))))

        for target in targets:
            try:
                resolved = expand(target)
            except (OSError, ValueError):
                continue
            if not any(self._within(resolved, root) for root in self._writable):
                return str(resolved)
        return None

    @staticmethod
    def _redirect_targets(command: str) -> list[str]:
        """Shell buyrug'idagi `>` / `>>` yo'nalishlarini ajratib oladi."""
        try:
            # Tokenlash — qo'shtirnoq ichidagi `>` ni noto'g'ri o'qimaslik uchun.
            shlex.split(command)
        except ValueError:
            return []
        return [match.group(1).strip("\"'") for match in _REDIRECT_RE.finditer(command)]

    @staticmethod
    def _within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _signature(tool_name: str, input_data: dict[str, Any]) -> str:
        """Bir xil amalni qayta so'ramaslik uchun barqaror imzo."""
        if tool_name == "Bash":
            command = str(input_data.get("command", ""))
            # Faqat birinchi so'z — `git status` tasdiqlansa, `git log` ham o'tadi.
            head = command.strip().split()[:1]
            return f"Bash:{head[0] if head else ''}"
        arg = PATH_ARG_BY_TOOL.get(tool_name)
        if arg:
            return f"{tool_name}:{input_data.get(arg, '')}"
        return tool_name

    @staticmethod
    def _describe(tool_name: str, input_data: dict[str, Any]) -> tuple[str, str]:
        """Foydalanuvchiga ko'rsatiladigan tushunarli tavsif."""
        if tool_name == "Bash":
            command = str(input_data.get("command", "")).strip()
            return "Buyruq bajarilsinmi?", command[:400]
        if tool_name in ("Write", "Edit"):
            path = str(input_data.get("file_path", "?"))
            verb = "yaratilsinmi" if tool_name == "Write" else "o'zgartirilsinmi"
            return f"Fayl {verb}?", path
        if tool_name.endswith("telegram_send"):
            # Eng xavfli tasdiq — shuning uchun kimga va nima yozilishi to'liq
            # ko'rinadi, JSON ichida yashirinib qolmaydi.
            who = str(input_data.get("kimga", "?"))
            text = str(input_data.get("matn", ""))
            return (f"Telegramda {who} ga sizning nomingizdan yuborilsinmi?", text[:400])
        if tool_name.startswith("mcp__"):
            pretty = tool_name.split("__")[-1].replace("_", " ")
            return f"{pretty} bajarilsinmi?", json.dumps(input_data, ensure_ascii=False)[:400]
        return f"`{tool_name}` ishlatilsinmi?", json.dumps(input_data, ensure_ascii=False)[:400]

    # --- Jurnal ---

    def _audit(self, tool_name: str, input_data: dict[str, Any], decision: Decision) -> None:
        """Har bir qarorni faylga yozadi — keyin nima bo'lganini tekshirish uchun."""
        if self._audit_path is None:
            return
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": tool_name,
            "allowed": decision.allowed,
            "asked": decision.asked,
            "reason": decision.reason,
            "input": {k: str(v)[:500] for k, v in input_data.items()},
        }
        try:
            with self._audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            log.exception("Audit jurnaliga yozib bo'lmadi")
