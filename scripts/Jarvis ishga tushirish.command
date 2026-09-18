#!/usr/bin/env bash
# Jarvis'ni Terminal orqali ishga tushiradi — va aynan shu muhim.
#
# macOS mikrofon ruxsatini "javobgar jarayon" bo'yicha beradi. Bu fayl
# ikki marta bosilganda (yoki Login Items orqali ochilganda) javobgar
# TERMINAL bo'ladi, Terminalda esa mikrofon ruxsati bor. Shuning uchun
# launchd yo'li ishlamagan holatda ham bu yo'l ishlaydi.
#
# Kompyuter yoqilganda o'zi ishga tushishi uchun:
#   Tizim sozlamalari > Asosiy > Kirish elementlari (Login Items)
#   > "+" > shu faylni tanlang.
#
# Oynani yopmang — Jarvis shu oyna ichida ishlaydi. Oynani kichraytirib
# qo'ying yoki Terminal sozlamalarida "yashirish" ni yoqing.
set -uo pipefail

cd "$(dirname "$0")/.."

# Avtomatik (launchd) nusxa turgan bo'lsa, ikkalasi bitta mikrofon va
# bitta portni talashadi — avval uni to'xtatamiz.
if [ -f "$HOME/Library/LaunchAgents/com.jarvis.assistant.plist" ]; then
  echo "==> Avtomatik nusxa to'xtatilmoqda (ikkitasi bir vaqtda ishlay olmaydi)"
  ./scripts/autostart.sh off >/dev/null 2>&1 || true
  sleep 1
fi

echo "==> Jarvis ishga tushmoqda. Bu oynani ochiq qoldiring."
echo "    To'xtatish: Ctrl+C"
echo
exec ./scripts/run.sh
