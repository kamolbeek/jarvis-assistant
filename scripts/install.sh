#!/usr/bin/env bash
# Jarvis'ni o'rnatish (macOS).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Talablar tekshirilmoqda"

command -v python3 >/dev/null || { echo "python3 topilmadi. `brew install python@3.11`"; exit 1; }

PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 11) else 0)')
if [ "$PY_OK" != "1" ]; then
  echo "Python 3.11+ kerak (hozir: $(python3 --version))"
  exit 1
fi

if ! command -v brew >/dev/null; then
  echo "Homebrew topilmadi — https://brew.sh dan o'rnating"
  exit 1
fi

echo "==> Tizim kutubxonalari (audio uchun)"
brew list portaudio >/dev/null 2>&1 || brew install portaudio

echo "==> Python muhiti"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
pip install --quiet -e .

# Apple Silicon'da lokal Whisper sezilarli tez ishlaydi.
if [ "$(uname -m)" = "arm64" ]; then
  echo "==> Apple Silicon aniqlandi — lokal STT qo'shilmoqda"
  pip install --quiet -e ".[local-stt]" || echo "   (o'tkazib yuborildi, majburiy emas)"
fi

echo "==> Orb interfeysi"
if command -v npm >/dev/null; then
  (cd ui && npm install --silent)
else
  echo "   npm topilmadi — orb'siz ishlaydi. `brew install node` bilan qo'shing."
fi

echo "==> Ma'lumotlar papkasi"

# Hamma narsa bitta ko'rinadigan joyda: xotira, jurnal, ish fayllari, sozlama.
# Repo o'chirilsa ham shu papka joyida qoladi — Jarvisning "esi" shu yerda.
JARVIS_HOME="${JARVIS_HOME:-$HOME/Documents/Jarvis}"
mkdir -p "$JARVIS_HOME"/{workspace,logs,wakewords,ui}
echo "   $JARVIS_HOME"

echo "==> Konfiguratsiya"
[ -f "$JARVIS_HOME/.env" ] || [ -f .env ] || {
  cp .env.example .env
  echo "   .env yaratildi — kalitlarni to'ldiring"
}
[ -f "$JARVIS_HOME/jarvis.yaml" ] || [ -f config/jarvis.yaml ] || {
  cp config/jarvis.example.yaml "$JARVIS_HOME/jarvis.yaml"
  echo "   $JARVIS_HOME/jarvis.yaml yaratildi"
}

cat <<EOF

O'rnatildi.

Barcha ma'lumot shu papkada saqlanadi:
  $JARVIS_HOME
    memory.db     xotira: faktlar, loyihalar, vazifalar, aloqalar
    audit.log     har bir amalning jurnali
    workspace/    Jarvis yozadigan yagona papka
    logs/         ishlash jurnali
    jarvis.yaml   sozlamangiz

Repo o'chirilsa ham bu papka joyida qoladi. Zaxira nusxa olsangiz — shuni oling.

Keyingi qadamlar:
  1. .env faylini to'ldiring — kamida ANTHROPIC_API_KEY va ELEVENLABS_API_KEY
  2. Tizim sozlamalari > Maxfiylik va xavfsizlik da ruxsat bering:
       - Mikrofon        -> Terminal (yoki iTerm)
       - Kirish imkoni   -> Terminal  (ilovalarni boshqarish uchun)
       - Avtomatlashtirish -> Terminal (Messages, System Events)
  3. Tekshiring:        python -m jarvis doctor
  4. Ishga tushiring:   ./scripts/run.sh

EOF
