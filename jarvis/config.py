"""Konfiguratsiyani yuklash: config/jarvis.yaml + .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "jarvis.yaml"
EXAMPLE_CONFIG_PATH = REPO_ROOT / "config" / "jarvis.example.yaml"


def expand(path: str | Path) -> Path:
    """`~` va env o'zgaruvchilarini ochib, absolyut yo'l qaytaradi."""
    return Path(os.path.expandvars(str(path))).expanduser().resolve()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """`override` ni `base` ustiga rekursiv qo'yadi (lug'atlar birlashadi, qolgani almashadi)."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Config:
    """Butun konfiguratsiya. `cfg.get("audio.sample_rate")` ko'rinishida o'qiladi."""

    data: dict[str, Any] = field(default_factory=dict)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def section(self, dotted_key: str) -> dict[str, Any]:
        value = self.get(dotted_key, {})
        return value if isinstance(value, dict) else {}

    # --- Tez-tez kerak bo'ladiganlar ---

    @property
    def workspace(self) -> Path:
        return expand(self.get("brain.workspace", "~/jarvis-workspace"))

    @property
    def memory_path(self) -> Path:
        return expand(self.get("memory.path", "~/.jarvis/memory.db"))

    @property
    def audit_log(self) -> Path:
        return expand(self.get("safety.audit_log", "~/.jarvis/audit.log"))

    @property
    def sample_rate(self) -> int:
        return int(self.get("audio.sample_rate", 16000))

    @property
    def frame_samples(self) -> int:
        """Bitta audio kadridagi namunalar soni."""
        return self.sample_rate * int(self.get("audio.frame_ms", 20)) // 1000

    def writable_roots(self) -> list[Path]:
        roots = [self.workspace]
        for entry in self.get("safety.writable_roots", []) or []:
            roots.append(expand(entry))
        # Takrorlanmasin
        seen: dict[str, Path] = {}
        for root in roots:
            seen[str(root)] = root
        return list(seen.values())

    def ensure_dirs(self) -> None:
        """Kerakli papkalarni yaratadi."""
        for path in (self.workspace, self.memory_path.parent, self.audit_log.parent):
            path.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> Config:
    """Konfiguratsiyani yuklaydi.

    Tartib: example (asos) -> jarvis.yaml (ustidan) -> .env (maxfiy kalitlar).
    Shu sababli jarvis.yaml da faqat o'zgartirmoqchi bo'lgan qatorlarni yozish yetarli.
    """
    load_dotenv(REPO_ROOT / ".env")

    if not EXAMPLE_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Namuna konfiguratsiya topilmadi: {EXAMPLE_CONFIG_PATH}")

    with EXAMPLE_CONFIG_PATH.open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle) or {}

    user_path = path or CONFIG_PATH
    if user_path.exists():
        with user_path.open(encoding="utf-8") as handle:
            user_data = yaml.safe_load(handle) or {}
        data = _deep_merge(data, user_data)

    return Config(data=data)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def require_env(name: str, hint: str = "") -> str:
    """Kalit yo'q bo'lsa, tushunarli xato beradi."""
    value = os.environ.get(name)
    if not value:
        suffix = f" — {hint}" if hint else ""
        raise RuntimeError(f"`{name}` muhit o'zgaruvchisi o'rnatilmagan{suffix}. .env faylni to'ldiring.")
    return value
