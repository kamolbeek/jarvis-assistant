#!/usr/bin/env bash
# Ikki marta bosib ishlatiladigan yangilagich — terminalga hech narsa
# yozish shart emas.
#
# Finder'da `scripts` papkasini oching va shu faylni ikki marta bosing.
# U eng oxirgi yangilanishni oladi va Jarvis'ni qaytadan ishga tushiradi.
#
# (Birinchi marta macOS "ochib bo'lmadi" desa: faylni o'ng tugma bilan
#  bosib "Open" ni tanlang va "Open" bilan tasdiqlang — bir martalik.)
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Yangilanish olinmoqda"
git pull --ff-only

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "==> Kutubxonalar tekshirilmoqda"
  pip install -q -e . 2>&1 | tail -3 || true
fi

echo "==> Jarvis qaytadan ishga tushirilmoqda"
./scripts/autostart.sh off >/dev/null 2>&1 || true
./scripts/autostart.sh

echo
echo "Tayyor. Bu oynani yopsangiz bo'ladi."
