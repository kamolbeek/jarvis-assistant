"""Konfiguratsiyani yuklash: jarvis.yaml + .env.

Bu yerda yana bitta muhim qaror bor — **ma'lumot qayerda yashaydi**.

Repo o'chirilishi, qaytadan klon qilinishi yoki boshqa papkaga ko'chirilishi
mumkin. Xotira, jurnal va ish fayllari esa yo'qolmasligi kerak. Shuning uchun
ular repodan tashqarida, bitta ko'rinadigan papkada turadi:

    ~/Documents/Jarvis/

Boshqa joy kerak bo'lsa — `JARVIS_HOME` muhit o'zgaruvchisi. Sozlama
faylidagi yo'llar `${JARVIS_HOME}/...` ko'rinishida yoziladi, ya'ni bitta
o'zgaruvchi butun tizimni ko'chiradi.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG_PATH = REPO_ROOT / "config" / "jarvis.example.yaml"
# Eski joy: sozlama repo ichida edi. Hali ham o'qiladi (quyida), lekin
# yangi o'rnatishlarda sozlama ham ma'lumotlar papkasida turadi.
REPO_CONFIG_PATH = REPO_ROOT / "config" / "jarvis.yaml"


def expand(path: str | Path) -> Path:
    """`~` va env o'zgaruvchilarini ochib, absolyut yo'l qaytaradi."""
    return Path(os.path.expandvars(str(path))).expanduser().resolve()


def jarvis_home() -> Path:
    """Barcha ma'lumot saqlanadigan papka.

    Standart: `~/Documents/Jarvis`. Ko'rinadigan joy ataylab tanlangan —
    yashirin `~/.jarvis` da nima yotganini foydalanuvchi bilmaydi, zaxira
    nusxa ham olmaydi.
    """
    raw = os.environ.get("JARVIS_HOME", "").strip()
    if raw:
        return expand(raw)
    return Path.home() / "Documents" / "Jarvis"


def user_config_path() -> Path:
    """Foydalanuvchi tahrirlaydigan sozlama fayli.

    Yangi joy ustun; eskisi (repo ichidagi) hali ham qo'llab-quvvatlanadi,
    shuning uchun mavjud o'rnatishlar buzilmaydi.
    """
    home_config = jarvis_home() / "jarvis.yaml"
    if home_config.exists():
        return home_config
    if REPO_CONFIG_PATH.exists():
        return REPO_CONFIG_PATH
    return home_config


def ensure_user_config() -> Path:
    """Sozlama faylini qaytaradi, yo'q bo'lsa namunadan yaratadi.

    `jarvis trust` va `jarvis wake-set` sozlamani tahrirlaydi. Fayl hali
    yo'q bo'lsa, «avval nusxa oling» deb xato berish o'rniga o'zimiz
    yaratganimiz to'g'riroq — foydalanuvchi buyruqni bejiz yozmagan.
    """
    path = user_config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXAMPLE_CONFIG_PATH, path)
    return path


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

    # --- Ma'lumot qayerda yotadi ---

    @property
    def home(self) -> Path:
        """Barcha ma'lumotning ildiz papkasi."""
        return jarvis_home()

    @property
    def workspace(self) -> Path:
        return expand(self.get("brain.workspace") or self.home / "workspace")

    @property
    def memory_path(self) -> Path:
        return expand(self.get("memory.path") or self.home / "memory.db")

    @property
    def audit_log(self) -> Path:
        return expand(self.get("safety.audit_log") or self.home / "audit.log")

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def wakewords_dir(self) -> Path:
        """O'zingiz o'rgatgan uyg'otuvchi so'z modellari."""
        return self.home / "wakewords"

    @property
    def ui_state_dir(self) -> Path:
        """Orbning joyi, HUD ustiga tashlangan rasm va shunga o'xshashlar."""
        return self.home / "ui"

    # --- Tez-tez kerak bo'ladiganlar ---

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
        for path in (
            self.home,
            self.workspace,
            self.logs_dir,
            self.wakewords_dir,
            self.ui_state_dir,
            self.memory_path.parent,
            self.audit_log.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_config(path: Path | None = None) -> Config:
    """Konfiguratsiyani yuklaydi.

    Tartib (keyingisi oldingisining ustiga qo'yiladi):

        1. `config/jarvis.example.yaml`   — asos, repo bilan keladi
        2. `config/jarvis.yaml`           — eski joy, bo'lsa o'qiladi
        3. `$JARVIS_HOME/jarvis.yaml`     — asosiy joy, eng ustun

    Shu sababli sozlamada faqat o'zgartirmoqchi bo'lgan qatorlarni yozish
    yetarli — qolgani asosdan olinadi.

    `.env` ham ikki joydan o'qiladi: repodagisi, so'ng ma'lumotlar
    papkasidagisi (u ustun). Kalitlaringiz repo bilan bog'liq bo'lmasligi
    uchun ularni `$JARVIS_HOME/.env` ga ko'chirish tavsiya etiladi.
    """
    load_dotenv(REPO_ROOT / ".env")

    # `${JARVIS_HOME}` sozlama faylidagi yo'llarda ishlashi uchun uni
    # muhitga qaytarib qo'yamiz — `expand()` o'shanda o'zi ochadi.
    home = jarvis_home()
    os.environ["JARVIS_HOME"] = str(home)
    load_dotenv(home / ".env", override=True)

    if not EXAMPLE_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Namuna konfiguratsiya topilmadi: {EXAMPLE_CONFIG_PATH}")

    data: dict[str, Any] = _read_yaml(EXAMPLE_CONFIG_PATH)

    if path is not None:
        sources = [path]
    else:
        sources = [REPO_CONFIG_PATH, home / "jarvis.yaml"]

    for source in sources:
        if source.exists():
            data = _deep_merge(data, _read_yaml(source))

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
