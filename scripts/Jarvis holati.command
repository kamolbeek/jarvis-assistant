#!/usr/bin/env bash
# Ikki marta bosib ishlatiladigan tekshirgich: Jarvis ishlayaptimi,
# ishlamasa — sababi nimada.
#
# Terminalga hech narsa yozish shart emas: Finder'da shu faylni ikki
# marta bosing va chiqqan matnni o'qing (yoki rasmga oling).
set -uo pipefail

cd "$(dirname "$0")/.."

echo "════════════════════════════════════════════════"
echo "  Jarvis holati"
echo "════════════════════════════════════════════════"
echo

./scripts/autostart.sh status

echo
echo "── Mikrofon ──────────────────────────────────────"
# Eng ko'p uchraydigan sabab shu: macOS ruxsati yo'q va Jarvis faqat
# nol eshitadi. Jurnalda buning aniq izi qoladi.
if grep -q "MIKROFON OVOZ BERMAYAPTI" ~/.jarvis/logs/jarvis.log 2>/dev/null; then
  echo "MUAMMO: macOS mikrofonni bloklayapti."
  echo
  echo "Tuzatish: Tizim sozlamalari > Maxfiylik va xavfsizlik > Mikrofon"
  echo "ro'yxatiga Python qo'shing:"
  grep -m1 -A1 "Ro'yxatga Python" ~/.jarvis/logs/jarvis.log 2>/dev/null | tail -1
else
  echo "Jurnalda mikrofon shikoyati yo'q."
fi

echo
echo "── Jurnalning oxiri ──────────────────────────────"
tail -n 25 ~/.jarvis/logs/jarvis.log 2>/dev/null || echo "(jurnal topilmadi)"

echo
echo "── HUD (orb) jurnali ─────────────────────────────"
tail -n 8 ~/.jarvis/logs/orb.log 2>/dev/null || echo "(orb jurnali yo'q)"

echo
echo "Bu oynani yopsangiz bo'ladi."
