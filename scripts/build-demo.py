#!/usr/bin/env python3
"""Demo sahifasini yig'adi: docs/demo-shell.html + haqiqiy HUD kodi.

Demo HUD kodini qaytadan yozmaydi — `ui/renderer/` dan aynan o'zini oladi.
Shu tufayli demo hech qachon haqiqiy ko'rinishdan farq qilib qolmaydi.

    python scripts/build-demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "docs" / "demo-shell.html"
OUT = ROOT / "docs" / "orb-demo.html"
SOURCES = [
    ROOT / "ui" / "renderer" / "palette.js",
    ROOT / "ui" / "renderer" / "suit.js",
    ROOT / "ui" / "renderer" / "hud.js",
    ROOT / "ui" / "renderer" / "desktop.js",
    ROOT / "ui" / "renderer" / "live.js",
]

MARKER = "/*INJECT*/"
FIGURE = ROOT / "ui" / "renderer" / "assets" / "markaz.jpg"
FIGURE_MARKER = "/*FIGURE_B64*/"


def main() -> int:
    shell = SHELL.read_text(encoding="utf-8")
    if MARKER not in shell:
        print(f"Xato: {SHELL.name} ichida {MARKER} belgisi yo'q", file=sys.stderr)
        return 1

    parts = []
    for source in SOURCES:
        code = source.read_text(encoding="utf-8")
        # Brauzerda `module` yo'q — CommonJS eksportlari kerak emas.
        code = "\n".join(
            line for line in code.splitlines()
            if not line.startswith("if (typeof module")
        ).rstrip()
        parts.append(f"// ---- {source.name} ----\n{code}")

    html = shell.replace(MARKER, "\n\n".join(parts))
    if FIGURE.exists() and FIGURE_MARKER in html:
        import base64
        b64 = base64.b64encode(FIGURE.read_bytes()).decode("ascii")
        html = html.replace(FIGURE_MARKER, b64)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} yig'ildi ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
