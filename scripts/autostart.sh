#!/usr/bin/env bash
# Jarvis'ni kompyuter yoqilganda o'zi ishga tushadigan qilish (macOS).
#
#   ./scripts/autostart.sh          yoqish (yoki qayta o'rnatish)
#   ./scripts/autostart.sh off      o'chirish
#   ./scripts/autostart.sh status   holatini ko'rish
#
# Ikkita LaunchAgent yoziladi va bu ataylab shunday:
#
#   com.jarvis.assistant — yadro. Bevosita venv ichidagi `python` ishga
#       tushiriladi, oraliqda bash yo'q. Sababi macOS'ning mikrofon
#       ruxsatida: TCC ruxsatni "javobgar jarayon" bo'yicha beradi, ya'ni
#       launchd ko'targan birinchi dastur bo'yicha. Agar u `/bin/bash`
#       bo'lsa, ruxsat bashga tegishli bo'lib qoladi — tizim binarysiga esa
#       mikrofon berib bo'lmaydi va macOS so'ramaydi ham: oqim ochiladi,
#       ichida faqat nol keladi. Aynan shu sabab Jarvis "ishlab turib"
#       hech nima eshitmasligi mumkin edi.
#
#   com.jarvis.orb — HUD (Electron). U alohida, chunki uning yiqilishi
#       yadroni yiqitmasligi kerak: mikrofon va miya ishlayotgan bo'lsa,
#       ekranda oyna yo'qligi sababli hamma narsani to'xtatish yaramaydi.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"

LABEL="com.jarvis.assistant"
ORB_LABEL="com.jarvis.orb"
AGENTS="$HOME/Library/LaunchAgents"
PLIST="$AGENTS/$LABEL.plist"
ORB_PLIST="$AGENTS/$ORB_LABEL.plist"
LOG_DIR="$HOME/.jarvis/logs"
PYTHON="$REPO/.venv/bin/python"

if [ "$(uname)" != "Darwin" ]; then
  echo "Bu skript faqat macOS uchun."
  exit 1
fi

loaded() {
  launchctl print "gui/$(id -u)/$1" >/dev/null 2>&1
}

status() {
  if [ -f "$PLIST" ] && loaded "$LABEL"; then
    echo "Yoqilgan — Jarvis login paytida o'zi ishga tushadi."

    # Ro'yxatda turishi hali ishlayotganini bildirmaydi: yiqilib, qayta
    # ko'tarilib turgan bo'lishi mumkin. Haqiqiy holatni jarayon ko'rsatadi.
    if pgrep -f "$PYTHON -m jarvis" >/dev/null 2>&1; then
      echo "Yadro ishlayapti — «Hey Jarvis» deb chaqirsangiz bo'ladi."
    else
      echo "DIQQAT: yadro hozir ishlamayapti — yiqilgan bo'lishi mumkin."
    fi

    if [ -f "$ORB_PLIST" ]; then
      loaded "$ORB_LABEL" && echo "HUD (orb) ham yoqilgan." \
        || echo "DIQQAT: HUD yuklanmagan."
    else
      echo "HUD o'chirilgan (npm yoki ui/node_modules topilmagan)."
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
  launchctl bootout "gui/$(id -u)/$ORB_LABEL" 2>/dev/null || true
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST" "$ORB_PLIST"
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

# Eski jarayon to'liq yopilmaguncha launchd "Input/output error" beradi.
# Bir necha marta urinib ko'ramiz — bu kutilgan hol, xato emas.
load() {
  local label="$1" plist="$2"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  for attempt in 1 2 3 4 5; do
    if launchctl bootstrap "gui/$(id -u)" "$plist" 2>/dev/null; then
      return 0
    fi
    [ "$attempt" = 5 ] && return 1
    sleep 2
  done
}

install() {
  if [ ! -x "$PYTHON" ]; then
    echo "Muhit topilmadi ($PYTHON). Avval ./scripts/install.sh ni ishga tushiring."
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

  mkdir -p "$LOG_DIR" "$AGENTS"

  if ! command -v claude >/dev/null 2>&1; then
    echo 'Eslatma: claude topilmadi — miya API kaliti orqali ishlaydi.'
  fi

  # --- Yadro ---------------------------------------------------------------
  cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <!-- Bevosita venv python. Oraliqda bash bo'lsa, mikrofon ruxsati bashga
       tegishli bo'lib qoladi va macOS jimgina rad etadi. -->
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>-m</string>
    <string>jarvis</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$REPO</string>

  <!-- launchd'ning PATH'i juda qisqa. Hozirgi seansning PATH'ini yozamiz —
       u yerda hammasi ishlayotgani tekshirilgan. -->
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$PATH</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>

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

  # --- HUD (orb) -----------------------------------------------------------
  if command -v npm >/dev/null 2>&1 && [ -d "$REPO/ui/node_modules" ]; then
    cat > "$ORB_PLIST" <<ORB_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$ORB_LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd "$REPO/ui" &amp;&amp; exec npm start</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$REPO/ui</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$PATH</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>

  <key>ThrottleInterval</key>
  <integer>15</integer>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/orb.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/orb.log</string>
</dict>
</plist>
ORB_EOF
  else
    echo "Ogohlantirish: npm yoki ui/node_modules topilmadi — HUD ko'rinmaydi."
    echo "Yadro baribir ishlaydi (ovoz bilan)."
    rm -f "$ORB_PLIST"
    launchctl bootout "gui/$(id -u)/$ORB_LABEL" 2>/dev/null || true
  fi

  load "$LABEL" "$PLIST" || {
    echo "launchd yadroni yuklay olmadi. Qaytadan urinib ko'ring."
    exit 1
  }
  [ -f "$ORB_PLIST" ] && { load "$ORB_LABEL" "$ORB_PLIST" || echo "HUD yuklanmadi."; }

  echo "Tayyor. Jarvis hozir ishga tushdi va endi har login'da o'zi ko'tariladi."
  echo
  echo "  Holat:    ./scripts/autostart.sh status"
  echo "  O'chirish: ./scripts/autostart.sh off"
  echo "  Jurnal:   tail -f $LOG_DIR/jarvis.log"
  echo
  echo "DIQQAT: macOS hozir mikrofon uchun ruxsat so'rashi mumkin — so'rov"
  echo "«Python» nomidan keladi. «Ruxsat berish» ni bosing, bu bir martalik."
  echo "So'rov chiqmasa va Jarvis eshitmasa: Tizim sozlamalari > Maxfiylik va"
  echo "xavfsizlik > Mikrofon ro'yxatida Python yoqilganini tekshiring."
}

case "${1:-on}" in
  off|remove|uninstall) remove ;;
  status) status ;;
  on|install|*) install ;;
esac
