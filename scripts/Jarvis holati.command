#!/usr/bin/env bash
# Ikki marta bosib ishlatiladigan tekshirgich: Jarvis ishlayaptimi,
# ishlamasa — sababi nimada.
#
# Terminalga hech narsa yozish shart emas: Finder'da shu faylni ikki
# marta bosing va chiqqan matnni o'qing (yoki rasmga oling).
set -uo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"
LOG="$HOME/.jarvis/logs/jarvis.log"
PLIST="$HOME/Library/LaunchAgents/com.jarvis.assistant.plist"

echo "════════════════════════════════════════════════"
echo "  Jarvis holati    $(date '+%H:%M:%S')"
echo "════════════════════════════════════════════════"

echo
echo "── Kod qaysi holatda ─────────────────────────────"
echo "Oxirgi o'zgarish: $(git log -1 --format='%h  %ad  %s' --date=format:'%d-%b %H:%M' 2>/dev/null)"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "DIQQAT: papkada saqlanmagan o'zgarishlar bor — yangilanish shu"
  echo "        sababdan o'tmagan bo'lishi mumkin:"
  git status --porcelain | head -5 | sed 's/^/        /'
fi

echo
echo "── Avtomatik ishga tushirish ─────────────────────"
if [ ! -f "$PLIST" ]; then
  echo "O'rnatilmagan. «Jarvis yangilash.command» ni ishga tushiring."
elif grep -q "/bin/bash" "$PLIST"; then
  echo "ESKI SOZLAMA: launchd bash orqali ishga tushiryapti."
  echo "Aynan shu sababdan macOS mikrofon so'ramaydi."
  echo "«Jarvis yangilash.command» ni ishga tushiring."
else
  echo "Yangi sozlama: launchd bevosita python'ni ko'taradi (to'g'ri)."
fi

# launchd nima deyapti: oxirgi chiqish kodi ko'pincha sababni aytadi.
launchctl print "gui/$(id -u)/com.jarvis.assistant" 2>/dev/null \
  | grep -E "state =|last exit code|program =|path =" | sed 's/^[[:space:]]*/  /'

echo
echo "── Yadro ishlayaptimi ────────────────────────────"
if pgrep -f "python -m jarvis" >/dev/null 2>&1; then
  echo "HA — ishlayapti."
else
  echo "YO'Q — yadro ishlamayapti."
fi

echo
echo "── Mikrofon ──────────────────────────────────────"
if [ -f "$LOG" ]; then
  echo "Jurnal oxirgi marta yozilgan: $(date -r "$LOG" '+%d-%b %H:%M:%S')"
fi
# Eng ko'p uchraydigan sabab: macOS ruxsati yo'q va Jarvis faqat nol
# eshitadi. Jurnalda buning aniq izi qoladi.
if tail -n 200 "$LOG" 2>/dev/null | grep -q "MIKROFON OVOZ BERMAYAPTI"; then
  echo "MUAMMO: macOS mikrofonni bloklayapti (oxirgi 200 qatorda)."
  echo "Tizim sozlamalari > Maxfiylik va xavfsizlik > Mikrofon ro'yxatida"
  echo "Python bo'lishi kerak."
else
  echo "Oxirgi 200 qatorda mikrofon shikoyati yo'q."
fi

echo
echo "── Jurnalning oxiri ──────────────────────────────"
tail -n 20 "$LOG" 2>/dev/null || echo "(jurnal topilmadi)"

echo
echo "── HUD (orb) jurnali ─────────────────────────────"
tail -n 6 ~/.jarvis/logs/orb.log 2>/dev/null || echo "(orb jurnali yo'q)"

echo
echo "Bu oynani yopsangiz bo'ladi."
