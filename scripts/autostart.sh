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
  echo "Hozir ishlab turgan Jarvis to'xtatilmadi — kerak bo'lsa terminalda Ctrl+C."
}

install() {
  if [ ! -d .venv ]; then
    echo "Muhit topilmadi. Avval ./scripts/install.sh ni ishga tushiring."
    exit 1
  fi

  mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

  # launchd'ning PATH'i juda qisqa, va `bash -l` zsh'ning .zprofile'ini
  # o'qimaydi — shuning uchun Homebrew/npm yo'llarini o'zimiz qo'shamiz.
  # Busiz orb (node) va Claude Code (`claude`) topilmay qolardi.
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
    <string>export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:\$PATH"; exec "$REPO/scripts/run.sh"</string>
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
  launchctl bootstrap "gui/$(id -u)" "$PLIST"

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
