#!/usr/bin/env bash
# Jarvis'ni ishga tushirish: yadro + orb interfeysi.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "Muhit topilmadi. Avval ./scripts/install.sh ni ishga tushiring."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Ma'lumotlar papkasi. Yadro ham, orb ham AYNAN shu qiymatga qarashi kerak —
# aks holda orbning holati bir joyda, xotira boshqa joyda bo'lib qolardi.
export JARVIS_HOME="${JARVIS_HOME:-$HOME/Documents/Jarvis}"
mkdir -p "$JARVIS_HOME"

# Yadroning manzilini interfeysga beramiz. Eng muhimi — TOKEN.
#
# `ui.token` qo'yilgan bo'lsa (telefonni ulash uchun kerak), yadro tokensiz
# WebSocket ulanishini rad etadi. Orb va HUD esa tokenni hech qayerdan
# olmasdi — natijada ekranda hech nima yonmasdi, garchi yadro chaqiruvni
# eshitib, holatini o'zgartirib turgan bo'lsa ham. Tokenni shu yerda,
# sozlamaning o'zidan o'qib beramiz.
JARVIS_WS_URL="$(python - <<'PY' 2>/dev/null || true
from jarvis.config import load_config

cfg = load_config()
port = int(cfg.get("ui.port", 8765))
token = str(cfg.get("ui.token") or "")
# Interfeys doim shu kompyuterda — `ui.host` 0.0.0.0 bo'lsa ham loopback.
print(f"ws://127.0.0.1:{port}" + (f"?t={token}" if token else ""))
PY
)"
if [ -n "$JARVIS_WS_URL" ]; then
  export JARVIS_WS_URL
else
  echo "==> DIQQAT: yadro manzilini sozlamadan o'qib bo'lmadi."
  echo "    Token qo'yilgan bo'lsa, orb va HUD yadroga ulana olmaydi."
fi

# Ikkita nusxa bitta mikrofon va bitta portni talashadi — ikkinchisi
# tushunarsiz xato bilan yiqiladi. Sababini oldindan aytamiz.
if pgrep -f "python -m jarvis" >/dev/null 2>&1; then
  echo "Jarvis allaqachon ishlayapti."
  echo
  echo "Avtomatik rejim yoqilgan bo'lsa, qo'lda ishga tushirish kerak emas —"
  echo "«Hey Jarvis» deb chaqiravering. Holatni ko'rish:"
  echo "  ./scripts/autostart.sh status"
  echo
  echo "Avtomatik rejimni to'xtatib, qo'lda ishlatmoqchi bo'lsangiz:"
  echo "  ./scripts/autostart.sh off"
  exit 1
fi

ORB_PID=""

# Yadro to'xtaganda orb ham yopilsin — osilib qolgan oyna qolmasin.
cleanup() {
  if [ -n "$ORB_PID" ] && kill -0 "$ORB_PID" 2>/dev/null; then
    kill "$ORB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Orbning yiqilishi jimgina o'tib ketmasligi kerak: chiqishi /dev/null ga
# ketsa, "ekranda hech nima yo'q" degan holatning sababi ko'rinmay qoladi.
# Aynan shunday bo'ldi — launchd ostida `node` PATH'da yo'q edi.
if [ ! -d ui/node_modules ]; then
  echo "==> Orb o'tkazib yuborildi (ui/node_modules yo'q — cd ui && npm install)"
elif ! command -v npm >/dev/null 2>&1; then
  echo "==> ORB ISHGA TUSHMADI: npm topilmadi (PATH: $PATH)"
  echo "    Yadro ishlaydi, lekin ekranda HUD ko'rinmaydi."
else
  echo "==> Orb ishga tushmoqda ($(command -v npm))"
  (cd ui && npm start 2>&1 | sed 's/^/    [orb] /') &
  ORB_PID=$!
fi

echo "==> Jarvis yadrosi"
exec python -m jarvis "$@"
