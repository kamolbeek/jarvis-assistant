#!/usr/bin/env bash
# Jarvis nima uchun chaqiruvga javob bermayotganini bir buyruqda aniqlash.
#
#   ./scripts/diagnose.sh
#
# `doctor` dan farqi: `doctor` mikrofon va kalitlarni tekshiradi, ya'ni
# Jarvis ISHLAYOTGANDA foydali. Bu skript esa Jarvis umuman ko'tarilmagan
# holat uchun: launchd, jarayon, jurnal, Node va kalitlar — hammasi bir
# ekranda. "Nega yonmayapti?" degan savolning javobi shu ro'yxatning
# birinchi qizil qatorida bo'ladi.
#
# Natija ekranga chiqadi va ~/.jarvis/diagnose.txt ga yoziladi.
# MUHIM: hech qanday kalit qiymati chop etilmaydi — faqat "bor / yo'q".
set -uo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"

LABEL="com.jarvis.assistant"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/.jarvis/logs/jarvis.log"
OUT="$HOME/.jarvis/diagnose.txt"

RED=$'\033[31m'; GREEN=$'\033[32m'; AMBER=$'\033[33m'; DIM=$'\033[2m'; RESET=$'\033[0m'

mkdir -p "$HOME/.jarvis"
: > "$OUT"

# Ekranga ham, faylga ham. Faylga rangsiz — nusxa olganda chiroyli chiqsin.
say() {
  printf '%s\n' "$1"
  printf '%s\n' "$1" | sed 's/\x1b\[[0-9;]*m//g' >> "$OUT"
}
ok()   { say "  ${GREEN}[ha]${RESET}    $1"; }
bad()  { say "  ${RED}[YO'Q]${RESET}  $1"; }
warn() { say "  ${AMBER}[?]${RESET}     $1"; }
head_() { say ""; say "${DIM}--- $1 ---${RESET}"; }

say "Jarvis diagnostikasi — $(date '+%Y-%m-%d %H:%M')"
say "Repozitoriya: $REPO"

# --- 1. Tizim ---
head_ "1. Tizim"
if [ "$(uname)" = "Darwin" ]; then
  ok "macOS $(sw_vers -productVersion 2>/dev/null)"
else
  bad "macOS emas ($(uname)) — avtostart va Shortcuts ishlamaydi"
fi

# --- 2. Jarayon ---
# Eng muhim savol: Jarvis umuman ishlayaptimi? Qolgan hamma tekshiruv
# shundan keyin ma'no kasb etadi.
head_ "2. Yadro ishlayaptimi?"
if pgrep -f "python -m jarvis" >/dev/null 2>&1; then
  ok "Ishlayapti (PID: $(pgrep -f 'python -m jarvis' | tr '\n' ' '))"
  CORE_UP=1
else
  bad "ISHLAMAYAPTI — «Hey Jarvis» hech qanday holatda javob bermaydi"
  CORE_UP=0
fi

if pgrep -f "[E]lectron.*ui" >/dev/null 2>&1 || pgrep -f "[j]arvis-orb" >/dev/null 2>&1; then
  ok "Orb (Electron) ishlayapti"
else
  warn "Orb ko'rinmayapti — yadro ishlasa ham ekranda HUD chiqmaydi"
fi

# --- 3. Avtostart ---
head_ "3. Avtomatik ishga tushirish"
if [ -f "$PLIST" ]; then
  ok "Plist bor: $PLIST"
  if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    ok "launchd ga yuklangan"
    # Oxirgi chiqish kodi sababni to'g'ridan-to'g'ri aytadi.
    code=$(launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null \
           | awk '/last exit code/ {print $NF; exit}')
    [ -n "${code:-}" ] && say "          oxirgi chiqish kodi: $code"
  else
    bad "Plist bor, lekin yuklanmagan — ./scripts/autostart.sh"
  fi
else
  bad "O'rnatilmagan — kompyuter yoqilganda o'zi ishga tushmaydi"
  say "          Yoqish: ./scripts/autostart.sh"
fi

# --- 4. Muhit ---
head_ "4. Muhit"
[ -d .venv ] && ok "Python muhiti (.venv) bor" || bad "Muhit yo'q — ./scripts/install.sh"
if command -v npm >/dev/null 2>&1; then
  ok "npm: $(command -v npm)"
else
  bad "npm PATH da yo'q — orb ishga tushmaydi (yadro ishlaydi)"
fi
[ -d ui/node_modules ] && ok "ui/node_modules bor" || bad "ui/node_modules yo'q — cd ui && npm install"

# --- 5. Kalitlar ---
# Faqat mavjudligi. Qiymat hech qachon chop etilmaydi — bu faylni
# boshqalarga yuborish xavfsiz bo'lishi kerak.
head_ "5. Kalitlar (.env)"
if [ -f .env ]; then
  for key in ANTHROPIC_API_KEY ELEVENLABS_API_KEY MOHIR_API_KEY \
             AZURE_SPEECH_KEY AZURE_SPEECH_REGION TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
    value=$(grep -E "^${key}=" .env 2>/dev/null | head -1 | cut -d= -f2-)
    value="${value%\"}"; value="${value#\"}"
    if [ -n "$value" ] && [ "${value#*...}" = "$value" ]; then
      ok "$key — bor (${#value} belgi)"
    else
      case "$key" in
        ANTHROPIC_API_KEY) bad "$key — bo'sh. Miya ishlamaydi, yadro darhol yiqiladi." ;;
        *)                 warn "$key — bo'sh" ;;
      esac
    fi
  done
else
  bad ".env fayli yo'q — cp .env.example .env"
fi

# --- 6. Sozlama ---
head_ "6. Chaqiruv sozlamasi"
if [ -f config/jarvis.yaml ]; then
  ok "config/jarvis.yaml bor (example ustidan qo'yiladi)"
else
  say "  ${DIM}[i]${RESET}     config/jarvis.yaml yo'q — example o'zi ishlatiladi (bu normal)"
fi
if [ -d .venv ]; then
  # Sozlamani YAML dan emas, dasturning o'zidan so'raymiz: example va
  # jarvis.yaml birlashgandan KEYINGI haqiqiy qiymat shu.
  .venv/bin/python - <<'PY' 2>/dev/null | tee -a "$OUT"
from jarvis.config import load_config
c = load_config()
w = c.section("activation.wake_word")
print(f"          wake_word.enabled:   {w.get('enabled')}")
print(f"          wake_word.threshold: {w.get('threshold')}")
print(f"          phrases:             {w.get('phrases')}")
print(f"          clap.enabled:        {c.section('activation.clap').get('enabled')}")
print(f"          stt / tts:           {c.get('voice.stt.provider')} / {c.get('voice.tts.provider')}")
print(f"          brain.model:         {c.get('brain.model')}")
PY
fi

# --- 7. Jurnal ---
# Yadro yiqilgan bo'lsa, sabab shu yerda. launchd har 15 soniyada qayta
# ko'taradi, shuning uchun bir xil xato takrorlanadi — birinchi nusxasi muhim.
head_ "7. Jurnalning oxiri"
if [ -f "$LOG" ]; then
  say "  $LOG ($(wc -l < "$LOG" | tr -d ' ') qator)"
  say ""
  tail -n 30 "$LOG" | sed 's/^/      /' | tee -a "$OUT"
  say ""
  errors=$(grep -c -iE "traceback|error|xato|failed" "$LOG" 2>/dev/null || true)
  errors=${errors:-0}
  [ "$errors" -gt 0 ] && warn "Jurnalda $errors ta xato satri bor"
else
  warn "Jurnal yo'q ($LOG) — Jarvis launchd orqali hech qachon ishga tushmagan"
fi

# --- Xulosa ---
head_ "Keyingi qadam"
if [ "$CORE_UP" = "0" ]; then
  say "  Yadro ishlamayapti. 7-bo'limdagi oxirgi xatoni o'qing."
  say "  Xato ko'rinmasa, qo'lda ishga tushirib ko'ring — sabab darhol chiqadi:"
  say "      ./scripts/run.sh"
else
  say "  Yadro ishlayapti, demak muammo mikrofon yoki chaqiruv balida."
  say "  Diqqat: quyidagilardan oldin Jarvisni to'xtating — ikki nusxa"
  say "  bitta mikrofonni talashadi va natija yolg'on chiqadi."
  say "      ./scripts/autostart.sh off"
  say "      source .venv/bin/activate"
  say "      python -m jarvis doctor      # mikrofon va kalitlar"
  say "      python -m jarvis wake-test   # chaqiruv bali va kerakli chegara"
fi

say ""
say "${DIM}Hammasi shu faylda ham: $OUT${RESET}"
say "${DIM}Kalit qiymatlari yozilmagan — faylni bemalol nusxalab yuborsangiz bo'ladi.${RESET}"
