#!/usr/bin/env bash
# Jarvis'ni kompyuter yoqilganda o'zi ishga tushadigan qilish (macOS).
#
#   ./scripts/autostart.sh          yoqish (yoki qayta o'rnatish)
#   ./scripts/autostart.sh off      o'chirish
#   ./scripts/autostart.sh status   holatini ko'rish
#
# macOS'da bu LaunchAgent orqali qilinadi: tizim login paytida bizning
# plist'imizni o'qib, run.sh ni ishga tushiradi. Jarvis yiqilsa, launchd
# uni o'zi qayta ko'taradi (KeepAlive).
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"

LABEL="com.jarvis.assistant"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/.jarvis/logs"

if [ "$(uname)" != "Darwin" ]; then
  echo "Bu skript faqat macOS uchun."
  exit 1
fi

status() {
  if [ -f "$PLIST" ] && launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    echo "Yoqilgan — Jarvis login paytida o'zi ishga tushadi."

    # Ro'yxatda turishi hali ishlayotganini bildirmaydi: yiqilib, qayta
    # ko'tarilib turgan bo'lishi mumkin. Haqiqiy holatni jarayon ko'rsatadi.
    if pgrep -f "python -m jarvis" >/dev/null 2>&1; then
      echo "Yadro ishlayapti — «Hey Jarvis» deb chaqirsangiz bo'ladi."
    else
      echo "DIQQAT: yadro hozir ishlamayapti — yiqilgan bo'lishi mumkin."
    fi

    echo
    echo "Jurnalning oxiri ($LOG_DIR/jarvis.log):"
    tail -n 15 "$LOG_DIR/jarvis.log" 2>/dev/null | sed 's/^/  /' || echo "  (jurnal bo'sh)"
  elif [ -f "$PLIST" ]; then
    echo "Plist bor, lekin yuklanmagan. Qaytadan yoqish: ./scripts/autostart.sh"
  else
    echo "O'chirilgan — Jarvis faqat qo'lda (./scripts/run.sh) ishga tushadi."
  fi
}

remove() {
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Avtomatik ishga tushirish o'chirildi."

  # `bootout` launchd ko'targan nusxani to'xtatadi, lekin qo'lda ishga
  # tushirilgani qolaveradi. "To'xtatdim" deb aytib, aslida ishlab turishi
  # eng yomon variant — shuning uchun haqiqiy holatni tekshiramiz.
  sleep 1
  if pgrep -f "python -m jarvis" >/dev/null 2>&1; then
    echo
    echo "DIQQAT: yadro hali ishlayapti — u qo'lda ishga tushirilgan."
    echo "To'xtatish: o'sha terminalda Ctrl+C, yoki:"
    echo "  pkill -f 'python -m jarvis'"
  else
    echo "Jarvis to'xtatildi."
  fi
}

install() {
  if [ ! -d .venv ]; then
    echo "Muhit topilmadi. Avval ./scripts/install.sh ni ishga tushiring."
    exit 1
  fi

  # Terminalda qo'lda ishga tushirilgan nusxa turgan bo'lsa, avtomatik nusxa
  # mikrofon va 8765-portni undan tortib ololmaydi: run.sh xato bilan
  # chiqadi, launchd esa KeepAlive tufayli uni har 15 soniyada qayta
  # ko'taraveradi. Tashqaridan bu "yoqdim, lekin ishlamayapti" bo'lib
  # ko'rinadi — shuning uchun sababini oldindan aytamiz.
  if pgrep -f "python -m jarvis" >/dev/null 2>&1; then
    echo "Jarvis hozir qo'lda ishga tushirilgan (terminalda ishlayapti)."
    echo
    echo "Avval o'sha oynada Ctrl+C bosib to'xtating, keyin shu buyruqni"
    echo "qaytadan bering:"
    echo "  ./scripts/autostart.sh"
    exit 1
  fi

  mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

  # launchd'ning PATH'i juda qisqa va `bash -l` zsh'ning .zprofile'ini
  # o'qimaydi. Taxmin qilingan yo'llar ham yetarli emas: node nvm yoki
  # boshqa joyda bo'lishi mumkin. Shuning uchun HOZIRGI seansning PATH'ini
  # o'zini yozib qo'yamiz — u yerda hammasi ishlayotgani tekshirilgan.
  if ! command -v npm >/dev/null 2>&1; then
    echo 'Ogohlantirish: npm shu seansda ham topilmadi — orb (HUD) ko'\''rinmaydi.'
    echo "Yadro baribir ishlaydi. Node.js o'rnatsangiz, shu skriptni qayta ishga tushiring."
  fi
  if ! command -v claude >/dev/null 2>&1; then
    echo 'Eslatma: claude topilmadi — miya API kaliti orqali ishlaydi.'
  fi
  cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>export PATH="$PATH"; exec "$REPO/scripts/run.sh"</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$REPO</string>

  <key>RunAtLoad</key>
  <true/>

  <!-- Yiqilsa qayta ko'tariladi; qo'lda to'xtatilsa (bootout) — yo'q. -->
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>

  <!-- Tez-tez yiqilsa, launchd urinishlar orasida shuncha kutadi. -->
  <key>ThrottleInterval</key>
  <integer>15</integer>

  <!-- Ikkalasi bitta faylga: Python jurnali stderr'ga yozadi, shuning uchun
       ularni ajratsak, "jurnalga qara" degan maslahat bo'sh faylga olib
       borardi — sabab esa ikkinchi faylda qolib ketardi. -->
  <key>StandardOutPath</key>
  <string>$LOG_DIR/jarvis.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/jarvis.log</string>
</dict>
</plist>
PLIST_EOF

  # Eski nusxasi yuklangan bo'lsa, avval chiqarib tashlaymiz — aks holda
  # bootstrap "allaqachon yuklangan" deb xato beradi.
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

  # Eski jarayon to'liq yopilmaguncha launchd "Input/output error" beradi.
  # Bir necha marta urinib ko'ramiz — bu kutilgan hol, xato emas.
  for attempt in 1 2 3 4 5; do
    if launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null; then
      break
    fi
    if [ "$attempt" = 5 ]; then
      echo "launchd yuklay olmadi. Qaytadan urinib ko'ring: ./scripts/autostart.sh"
      exit 1
    fi
    sleep 2
  done

  echo "Tayyor. Jarvis hozir ishga tushdi va endi har login'da o'zi ko'tariladi."
  echo
  echo "  Holat:    ./scripts/autostart.sh status"
  echo "  O'chirish: ./scripts/autostart.sh off"
  echo "  Jurnal:   tail -f $LOG_DIR/jarvis.log"
  echo
  echo "Diqqat: birinchi avtomatik ishga tushishda macOS mikrofon uchun"
  echo "qaytadan ruxsat so'rashi mumkin — bu safar so'rov python nomidan"
  echo "keladi (terminal emas). «OK» deng, bir martalik."
}

case "${1:-on}" in
  off|remove|uninstall) remove ;;
  status) status ;;
  on|install|*) install ;;
esac
