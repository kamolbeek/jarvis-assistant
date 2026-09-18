#!/usr/bin/env bash
# Ikki marta bosib ishlatiladi: tasdiq so'rashni yoqish/o'chirish.
#
# Ishonch rejimi yoqilganda Jarvis «ha yoki yo'q deb ayting» demaydi —
# aytilgan ishni darhol bajaradi.
set -uo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "Muhit (.venv) topilmadi. Avval ./scripts/install.sh"
  echo; read -r -p "Yopish uchun Enter bosing..." _; exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# Sozlama fayli bo'lmasa, ishonch rejimini yozadigan joy ham yo'q.
if [ ! -f config/jarvis.yaml ]; then
  echo "==> config/jarvis.yaml yaratilmoqda (namunadan)"
  cp config/jarvis.example.yaml config/jarvis.yaml
fi

echo "════════════════════════════════════════════════"
echo "  Jarvis — ishonch rejimi"
echo "════════════════════════════════════════════════"
echo
python -m jarvis trust status
echo
echo "  1  — YOQISH: hech narsa so'ramasin, aytganimni bajarsin"
echo "  2  — O'CHIRISH: fayl yozish va buyruqlar uchun tasdiq so'rasin"
echo "  Enter — o'zgartirmaslik"
echo
read -r -p "Tanlang [1/2]: " choice

case "$choice" in
  1) python -m jarvis trust on ;;
  2) python -m jarvis trust off ;;
  *) echo "O'zgartirilmadi."; echo; read -r -p "Yopish uchun Enter bosing..." _; exit 0 ;;
esac

echo
echo "==> Jarvis qaytadan ishga tushirilmoqda (sozlama ishga tushganda o'qiladi)"
# launchd nusxasi bo'lsa — uni qayta ko'taramiz. Qo'lda ishga tushirilgan
# bo'lsa, uni bu oynadan boshqarib bo'lmaydi: aniq aytamiz.
if [ -f "$HOME/Library/LaunchAgents/com.jarvis.assistant.plist" ]; then
  ./scripts/autostart.sh off >/dev/null 2>&1
  ./scripts/autostart.sh >/dev/null 2>&1 && echo "    Qayta ishga tushdi."
elif pgrep -f "python -m jarvis" >/dev/null 2>&1; then
  echo "    Jarvis qo'lda ishga tushirilgan — o'sha oynada Ctrl+C bosing va"
  echo "    «Jarvis ishga tushirish.command» ni qaytadan bosing."
else
  echo "    Jarvis hozir ishlamayapti — keyingi ishga tushishida kuchga kiradi."
fi

echo
echo "Bu oynani yopsangiz bo'ladi."
