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

if [ -d ui/node_modules ]; then
  echo "==> Orb ishga tushmoqda"
  (cd ui && npm start >/dev/null 2>&1) &
  ORB_PID=$!
else
  echo "==> Orb o'tkazib yuborildi (ui/node_modules yo'q)"
fi

echo "==> Jarvis yadrosi"
exec python -m jarvis "$@"
