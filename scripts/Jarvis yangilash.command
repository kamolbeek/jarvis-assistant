#!/usr/bin/env bash
# Ikki marta bosib ishlatiladigan yangilagich — terminalga hech narsa
# yozish shart emas.
#
# Finder'da `scripts` papkasini oching va shu faylni ikki marta bosing.
#
# (Birinchi marta macOS "ochib bo'lmadi" desa: faylni o'ng tugma bilan
#  bosib "Open" ni tanlang va "Open" bilan tasdiqlang — bir martalik.)
#
# `set -e` ATAYLAB yo'q: bir qadam yiqilsa ham qolganlari bajarilsin va
# eng muhimi — sabab ekranda qolsin. Ilgari skript jimgina to'xtab
# qolardi va tashqaridan "bosdim, lekin hech nima o'zgarmadi" bo'lib
# ko'rinardi.
set -uo pipefail

cd "$(dirname "$0")/.."

fail() { echo; echo "!!! $1"; echo; }

echo "════════════════════════════════════════════════"
echo "  Jarvis yangilanmoqda"
echo "════════════════════════════════════════════════"
echo

echo "==> Yangilanish olinmoqda"
# Papkada saqlanmagan o'zgarish bo'lsa, `git pull` o'tmaydi. Ularni
# yo'qotmaymiz — chetga olib qo'yamiz va qayerdaligini aytamiz.
if [ -n "$(git status --porcelain)" ]; then
  echo "    Saqlanmagan o'zgarishlar chetga olib qo'yildi (git stash):"
  git status --porcelain | head -5 | sed 's/^/      /'
  git stash push -u -m "Jarvis yangilash $(date '+%d-%b %H:%M')" >/dev/null 2>&1 \
    && echo "    Qaytarish kerak bo'lsa: git stash pop"
fi

if git pull --ff-only; then
  echo "    Yangilandi: $(git log -1 --format='%h %s')"
else
  fail "Yangilanish olinmadi (internet yoki git muammosi)."
  echo "    Eski kod bilan davom etamiz."
fi

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo
  echo "==> Kutubxonalar tekshirilmoqda"
  # `setuptools` alohida aytilgan: u yo'q bo'lsa webrtcvad jimgina
  # ishlamay qoladi va gapni tugatganini aniqlash sezilarli yomonlashadi.
  pip install -q -e . setuptools 2>&1 | tail -3
else
  fail "Muhit (.venv) topilmadi — ./scripts/install.sh kerak."
fi

echo
echo "==> Jarvis qaytadan ishga tushirilmoqda"
./scripts/autostart.sh off >/dev/null 2>&1
./scripts/autostart.sh

echo
echo "==> Tekshiruv (5 soniya kutamiz)"
sleep 5
if pgrep -f "python -m jarvis" >/dev/null 2>&1; then
  echo "    Yadro ishlayapti."
else
  fail "Yadro ishga tushmadi. Sababi jurnalning oxirida:"
  tail -n 15 ~/.jarvis/logs/jarvis.log 2>/dev/null | sed 's/^/    /'
fi

echo
echo "Tayyor. Endi «Hey Jarvis» deb chaqirib ko'ring."
echo "macOS mikrofon so'rasa — «Ruxsat berish» ni bosing."
echo
echo "Bu oynani yopsangiz bo'ladi."
