# Jarvis

Ovoz bilan boshqariladigan shaxsiy AI yordamchi — **o'zbek tilida**, macOS uchun.

«Hey Jarvis» deysiz yoki ikki marta qarsak chalasiz — ekranda HUD yonadi,
Jarvis sizni tinglaydi va kompyuterda ish bajaradi. Telegram bot emas, chat oynasi
emas — Siri kabi, lekin butunlay sizniki va kompyuteringizni haqiqatan boshqaradi.

```mermaid
flowchart TD
    A["🎙 Uyg'otish<br/>«Hey Jarvis» · 👏👏 qarsak · ⌘⇧J"] --> B
    P["📱 Telefon<br/>bosib-gapirish sahifasi"] --> B

    B["🔊 Ovoz quvuri<br/>VAD → STT (o'zbekcha) → … → TTS"] --> C

    C["🧠 Jarvis miyasi<br/>Claude Agent SDK"] --> D

    D{"🛡 Xavfsizlik darvozasi<br/>tasdiq · taqiq · audit"}

    D -->|ruxsat| E["💻 Kompyuter<br/>fayl · shell · ilovalar"]
    D -->|ruxsat| F["🌐 Internet<br/>qidiruv · sahifa o'qish"]
    D -->|ruxsat| G["📨 Kanallar<br/>iMessage · Telegram · Shortcuts · n8n"]

    M[("🗂 Xotira va agenda<br/>faktlar · loyihalar<br/>vazifalar · aloqalar")] <--> C
    S["⏰ Rejalashtiruvchi"] --> M
    S -.->|"vaqti kelganda<br/>o'zi gapiradi"| B

    C <--> H["◎ HUD<br/>doim ekran ustida"]
    D <--> H

    style C fill:#1a3a5c,stroke:#22e3ff,color:#ecfdff
    style D fill:#5c3a1a,stroke:#ffb545,color:#fff0d9
    style H fill:#1a3a5c,stroke:#22e3ff,color:#ecfdff
    style S fill:#1a3a5c,stroke:#22e3ff,color:#ecfdff
    style M fill:#14202c,stroke:#22e3ff,color:#ecfdff
```

## Nima qila oladi

- **Uch xil chaqiruv** — «Salom Jarvis», «Hi Jarvis», «Hey Jarvis». Yoki ikki
  marta qarsak, yoki `⌘⇧J`. Qarsak bilan chaqirsangiz «Buyrug'ingizni
  kutyapman» deydi.
- **Asosiy oyna chaqirilganda ochiladi** — qarsak yoki `⌘⇧J` bosilsa, to'liq
  ekranli HUD chiqadi. Lekin uyquda: ko'zlar o'chgan. **Gapirganingizda yonadi.**
- **Suhbatni davom ettiradi** — javobdan keyin tinglab turadi, har safar
  «Hey Jarvis» deyish shart emas.
- **Gapini bo'lish mumkin** — Jarvis gapirayotganda gapirsangiz, darhol jim
  bo'lib sizni tinglaydi. Uzun javobni oxirigacha kutish kerak emas.
- **O'zbekcha gapiradi va tushunadi** — savol ham, javob ham o'zbek tilida.
- **Kompyuterni boshqaradi** — fayl o'qiydi/yozadi, shell buyruqlarini bajaradi,
  ilovalarni ochadi, kod yozadi, loyihani davom ettiradi.
- **Loyihalaringizni yuritadi** — har bir loyihaning holati, keyingi qadami va
  muddati saqlanadi. «Loyihalarim qaysi bosqichda?» deb so'rasangiz, aytadi.
- **O'zi eslatadi** — «ertaga soat 10 da Alisher bilan uchrashuv» desangiz,
  ertaga soat 10 da **o'zi gapiradi**. So'rashingiz shart emas.
- **Ertalab kunni tushuntiradi** — belgilangan vaqtda bugungi ishlarni aytib beradi.
- **Sizning nomingizdan yozadi** — «Alisherga yoz, kechikaman de» desangiz,
  Telegram yoki SMS orqali yuboradi.
- **Telegram akkauntingizni boshqaradi** — kanal va guruh ochadi, odam
  qo'shadi, admin qiladi, chiqaradi, bloklaydi, papkalarga yig'adi, storiya
  qo'yadi, ovozli chat ochadi. Ellikdan ortiq amal — «Telegram» bo'limiga qarang.
- **O'zini o'zi tuzatadi** — «bu menga yoqmadi» desangiz, o'z kodini
  o'zgartiradi, testlardan o'tkazadi va qayta ishga tushadi. Bu paytda ekranda
  «o'z ustida ishlamoqda» yozuvi turadi.
- **Telefonda ham ishlaydi** — telefon brauzeridan bosib-gapirish sahifasi.
- **Har bir xavfli amal uchun so'raydi** — HUD'da ✅/❌ chiqadi, hammasi jurnalga yoziladi.

## Tez boshlash

```bash
git clone https://github.com/kamolbeek/jarvis-assistant.git
cd jarvis-assistant
./scripts/install.sh
```

Keyin `.env` faylini to'ldiring:

```bash
ANTHROPIC_API_KEY=sk-ant-...      # miya
ELEVENLABS_API_KEY=...            # ovoz (STT + TTS)
```

### Nega kalit kerak — va qachon kerak emas

**Miya (Claude)** Anthropic serverlarida ishlaydi, kompyuteringizda emas — model
o'nlab gigabayt va kuchli videokarta talab qiladi. Shuning uchun kirish kaliti
kerak. Ikki yo'l bor:

1. **Claude Pro/Max obunasi** — agar obunangiz bo'lsa, **API uchun alohida
   to'lash shart emas**. Mac'da `claude` o'rnatib kiring (`claude` deb yozing,
   brauzerda tasdiqlang) va `.env` da `ANTHROPIC_API_KEY` ni **qo'ymang**.
   Claude Agent SDK ichida aynan Claude Code'ni ishlatadi, u esa obunangiz
   bilan kiradi — Jarvis o'sha tarif ichida ishlaydi.
2. **API kaliti** — obunangiz bo'lmasa, har so'rov uchun alohida to'lov
   ([console.anthropic.com](https://console.anthropic.com)).

> **Diqqat — ikki marta to'lash tuzog'i.** `.env` da kalit turgan bo'lsa, u
> obunadan **ustun** turadi: Jarvis obunani chetlab o'tib, API hisobidan
> pul yechadi. Obunangiz bor bo'lsa, kalit qatorini izohga aylantiring:
>
> ```bash
> sed -i '' 's|^ANTHROPIC_API_KEY=|# ANTHROPIC_API_KEY=|' .env
> ```
>
> `python -m jarvis doctor` qaysi yo'l ishlatilayotganini aytadi.

**Ovoz esa butunlay kompyuteringizda ishlashi mumkin** — kalitsiz, internetsiz,
bepul. `config/jarvis.yaml` da:

```yaml
voice:
  stt:
    provider: "whisper_local"     # Whisper Mac'ning o'zida ishlaydi
  tts:
    provider: "macos"             # macOS ning o'z ovozi
```

Kamchiligi — o'zbekcha aniqligi ElevenLabs'dan pastroq va birinchi ishga
tushirishda model yuklab olinadi (~1.5 GB). Lekin hech qanday to'lov yo'q.

**Eng yaxshi o'zbekcha — rubaiSTT (ham lokal, ham bepul).** Bu model aynan
o'zbek tiliga o'rgatilgan va whisper.cpp orqali ishlaydi:

```bash
brew install whisper-cpp
```

```yaml
voice:
  stt:
    provider: "rubai"             # = whisper_cpp
    # model ko'rsatilmasa, odatdagi joylardan o'zi qidiradi
    model: "~/Library/Application Support/uzbek-dictation/ggml-rubaistt_v2_medium-q8_0.bin"
```

Agar Mac'ingizda [RubaiSTT Dictation](https://github.com/MuhammadMirrr/uzbek-dictation)
ilovasi bo'lsa, model allaqachon yuklangan — Jarvis o'sha faylni ishlatadi,
ilovaning o'zini ochish shart emas. Modelni topish:

```bash
find ~ /Applications -iname "*.bin" -size +100M 2>/dev/null | head
```

macOS ruxsatlarini bering — **Tizim sozlamalari → Maxfiylik va xavfsizlik**:

| Ruxsat | Nima uchun |
| --- | --- |
| Mikrofon | uyg'otuvchi so'z va sizning gapingiz |
| Kirish imkoni (Accessibility) | global tugma, ilovalarni boshqarish |
| Avtomatlashtirish (Automation) | Messages, System Events |

**Ishga tushirishdan oldin — diagnostika.** Birinchi marta hamma narsa birdan
ishlashi kamdan-kam bo'ladi, shuning uchun har bir bo'g'inni alohida tekshiring:

```bash
source .venv/bin/activate
python -m jarvis doctor
```

Ketma-ket tekshiradi: kalitlar → audio qurilmalar → mikrofon (3 soniya gapirasiz,
darajani ko'rsatadi) → uyg'otuvchi so'z modeli → o'sha yozuvni matnga aylantirish →
ovoz chiqarish → Claude. Nima ishlamasa, aynan o'sha qatorda sababi yoziladi.

Hammasi yashil bo'lgach:

```bash
./scripts/run.sh
```

Kichik orb ekranning o'ng pastida paydo bo'ladi. «Hey Jarvis» deb ko'ring.

### Avtomatik ishga tushirish

Terminal ochib yurish shart bo'lmasin — bir marta yoqib qo'ying:

```bash
./scripts/autostart.sh
```

Shundan keyin Jarvis har safar kompyuterga kirganingizda **o'zi ishga
tushadi**: ertalab Mac'ni ochasiz, «Hey Jarvis» deysiz — ishlaydi. Yiqilib
qolsa, tizim o'zi qayta ko'taradi.

```bash
./scripts/autostart.sh status   # holati
./scripts/autostart.sh off      # o'chirish
tail -f ~/.jarvis/logs/jarvis.log   # nima bo'layotganini ko'rish
```

**Terminalga qaytmaslik uchun** `scripts` papkasida ikkita ikki marta
bosiladigan fayl bor:

| Fayl | Nima qiladi |
|---|---|
| **Jarvis yangilash.command** | yangilanishni oladi va Jarvis'ni qayta ko'taradi |
| **Jarvis holati.command** | ishlayaptimi, ishlamasa sababi nimada |
| **Jarvis ishga tushirish.command** | Terminal orqali ishga tushiradi (mikrofon ruxsati muammosida) |
| **Jarvis ishonch rejimi.command** | tasdiq so'rashni yoqadi/o'chiradi |

(Birinchi marta macOS ochishdan bosh tortsa: faylni o'ng tugma bilan bosib
«Open» ni tanlang — bir martalik tasdiq.)

Mikrofon bloklangan bo'lsa, orb **yashirilmaydi**: u ekranda qolib, qizil
siferblat bilan sababni ko'rsatadi. Ekranda hech narsa yo'q va sabab ham
yo'q degan holat bo'lmasligi kerak.

**Mikrofon ruxsati — bu yerda tuzoq bor.** macOS ruxsatni *javobgar jarayon*
bo'yicha beradi, ya'ni `launchd` ko'targan birinchi dastur bo'yicha.
Terminaldan ishga tushirsangiz javobgar Terminal bo'ladi va ruxsat ishlaydi.

Shu sababli LaunchAgent bevosita `\.venv/bin/python` ni ishga tushiradi,
oraliqda `bash` yo'q: aks holda ruxsat bashga tegishli bo'lib qolardi, tizim
binarysiga esa mikrofon berib bo'lmaydi va macOS **so'ramaydi ham, xato ham
bermaydi** — oqim ochiladi, ichida faqat nol keladi. Tashqaridan qaraganda
Jarvis ishlab turadi, lekin hech nima eshitmaydi.

Shu sababdan HUD ham alohida agent (`com.jarvis.orb`): uning yiqilishi
yadroni yiqitmasligi kerak.

Jarvis buni o'zi sezadi: ishga tushganda bir soniya tinglaydi va mutlaq nol
kelsa, HUD'da mikrofon siferblati qizarib, jurnalga sabab yoziladi (haqiqiy
jimlikda ham fon shovqini bo'ladi — mutlaq nol aynan bloklanganning
belgisi).

Tuzatish: **Tizim sozlamalari → Maxfiylik va xavfsizlik → Mikrofon**
ro'yxatida Python yoqilgan bo'lishi kerak.

Diqqat: bu ro'yxatga **qo'lda qo'shib bo'lmaydi** — unda `+` tugmasi yo'q.
Unda faqat mikrofonni haqiqatan **so'ragan** dasturlar paydo bo'ladi. Ya'ni
Python u yerda yo'q bo'lsa, demak yadro hali biror marta ham to'g'ri ishga
tushmagan (yoki eski, bash orqali ishlaydigan sozlama qolgan).

Ishonchli zaxira yo'l — **«Jarvis ishga tushirish.command»**: u Terminal
orqali ishga tushadi, Terminalda esa mikrofon ruxsati bor. Uni *Tizim
sozlamalari → Asosiy → Kirish elementlari* ga qo'shsangiz, kompyuter
yoqilganda o'zi ishga tushadi.

Vaqtinchalik yechim — terminaldan ishlatish (u ruxsatga ega):

```bash
./scripts/autostart.sh off
./scripts/run.sh
```

Avtomatik rejim yoqilganda `./scripts/run.sh` ni qo'lda ishga tushirish
kerak emas — ikkita nusxa bir-biriga xalaqit beradi (ikkalasi ham bitta
mikrofonni va 8765-portni talab qiladi).

### Orb: kichik, sudraladigan

Orb ataylab kichik — 150 piksel, ish stolining bir burchagida turadi va
ishga xalaqit bermaydi. Uni **sudrab istalgan joyga ko'chirish mumkin**:
bosib ushlab suring. Qo'yib yuborgan joyingiz eslab qolinadi va keyingi
ishga tushirishda o'sha yerda turadi.

Bosish va sudrash bir-biriga xalaqit bermaydi: 4 pikseldan kam siljish —
bu bosish (Jarvis chaqiriladi), ko'proq siljish — bu sudrash. Ko'chirilgan
joyda ham hammasi ishlayveradi: gapirganingizda to'lqin harakatlanadi,
siferblatlar aylanadi.

Orbdan tashqaridagi shaffof joy bosishlarni **o'tkazib yuboradi** — orb
ostidagi ilovaga bosa olasiz, u yo'lni to'smaydi.

O'lchamni o'zgartirish:

```bash
JARVIS_ORB_SIZE=110 ./scripts/run.sh    # 80 dan 320 gacha
```

Boshlang'ich burchak (birinchi marta, hali surilmagan bo'lsa):

```bash
JARVIS_ORB_POSITION=bottom-left ./scripts/run.sh
```

> HUD'ni Jarvis'ni o'rnatmasdan ham ko'rish mumkin: `docs/orb-demo.html` ni
> brauzerda oching — barcha holatlar, bo'g'inlarni «buzib» ko'rish va to'liq
> suhbat oqimi bor.

### Asosiy oyna: chaqirilganda ochiladi, gapirilganda yonadi

Ikki marta qarsak chalasiz yoki `⌘⇧J` bosasiz — to'liq ekranli HUD hammasining
ustida ochiladi. Lekin darhol ishga tushmaydi: **uyquda** turadi — ko'zlar
o'chgan, yorug'lik pasaygan, ovoz datchigi jim. Bu ataylab shunday: chaqirilgani
hali gapirilgani emas.

Gapirganingizda yonadi — ko'zlar chaqnaydi, reaktor kuchayadi, panellar
yorishadi. Jim qolsangiz, sekin qaytadan uyquga ketadi.

Ko'zlar bilan bitta nozik joy bor: ular fon rasmining **o'zida** yoniq holda
chizilgan. Shuning uchun uyquda ularning ustiga qorayituvchi niqob qo'yiladi va
nur qaytadan chiziladi — natijada yonish haqiqatan yonishga o'xshaydi,
shunchaki yorqinlik oshishiga emas.

### Oynadan chiqish — to'rt yo'l

Bu oyna butun ekranni egallaydi, shuning uchun undan chiqish yo'li **hech
qachon sahifaning JS'iga bog'liq bo'lmasligi kerak**. Sahifa buzilsa ham
foydalanuvchi qamalib qolmasligi shart. Shuning uchun to'rtta mustaqil yo'l bor:

| Yo'l | Qayerda ishlaydi |
|---|---|
| `Esc` | global tugma — Electron'ning asosiy jarayonida, sahifadan mustaqil |
| `⌘⇧J` ikkinchi marta | o'sha global tugma ochadi va yopadi |
| `⌘Tab` yoki boshqa oynaga bosish | fokus ketishi bilan HUD o'zi yashirinadi |
| `⌘W` | oyna fokusda bo'lganda |

Oyna **hamma narsa ustida turmaydi**: boshqa ilova oldinga chiqsa, HUD orqada
qoladi. Ekranning yuqori o'ng burchagida doim `ESC — YOPISH` yozuvi turadi.

Bir marta bu qoida buzilgan edi — oyna `screen-saver` darajasida ochilib,
menyu panelini ham bekitgan va chiqish faqat sahifaning JS'iga bog'liq
bo'lgan. Sahifa esa qora ekran bo'lib qolgan va foydalanuvchi kompyuterni
qayta yoqishga majbur bo'lgan.

**Ochilmayaptimi?** Avval oynaning o'zini tekshiring — u chaqiruv zanjiridan
(mikrofon → yadro → WebSocket) mustaqil ochiladi:

```bash
cd ui && npm start -- --desk    # HUD darhol ochiladi
```

Ochilsa, muammo chaqiruvda; ochilmasa — oynada. `⌘⇧J` ni boshqa ilova
egallab olgan bo'lishi mumkin: shu holda `⌘⌥J`, so'ng `⌘⇧F12` sinaladi va
ishlagan kombinatsiya ishga tushirish jurnaliga yoziladi. O'zingiznikini
tanlash: `JARVIS_HOTKEY="Control+Alt+J"`.

**Jonli fon rejimi.** Oyna emas, doimiy fon sifatida kerak bo'lsa (oynalar
ORQASIDA turadigan Rainmeter uslubi):

```bash
JARVIS_DESKTOP=ambient ./scripts/run.sh
```

Butunlay o'chirish: `JARVIS_DESKTOP=0`. Kichik burchak-vidjet har doim qoladi.

### Wallpaperning o'zi jonli

Ekranda o'sha SHIELD OS wallpaperi turadi — **dizayn bir zarra ham
o'zgarmagan**: o'sha panellar, o'sha yozuvlar, o'sha ranglar. Farqi shundaki,
rasmdagi raqamlar endi qotib qolgan emas.

Ishlashi oddiy (`ui/renderer/live.js`): eski qiymat rasmning **o'zidan**
olingan toza ustun bilan yopiladi — fon naqshi ham, gradienti ham aynan mos
tushadi — so'ng o'sha joyga, o'sha o'lchamda yangi qiymat chiziladi. Shrift
har kompyuterda turlicha bo'lgani uchun har bir yozuv rasmdagi harf
balandligiga moslab cho'ziladi.

Nimalar jonlandi:

| Rasmdagi joy | Endi nimani ko'rsatadi |
|---|---|
| Pastdagi katta soat (aksi bilan), o'ngdagi `23:52`, `TIME/DATE` paneli, radial menyu yonidagi soat | haqiqiy vaqt — soat, daqiqa; sekundlar alohida katakda |
| `21 AUGUST WEDNESDAY` bloki, `Tuesday / August 20, 2013`, `20-Aug., Tuesday` | bugungi sana va hafta kuni |
| Taqvim qatori (`Su Mo Tu …` va sonlar) | shu hafta; bugungi ustun rasmdagidek yoritiladi |
| `SYSTEM`: CPU / RAM / SWAP foizlari va zargaldoq chiziqlari | haqiqiy yuk, har 2 soniyada |
| `RAM USAGE 50%`, `Used:` / `Free:` | haqiqiy xotira, gigabaytda |
| `DISK` paneli (`C:\`, `D:\`), `FILESYSTEMS` qatorlari, `DRIVE` (HD C / HD D) | haqiqiy disklar: band/umumiy hajm va foiz |
| `Speed:` / `Total:`, `UPLOAD` / `DOWNLOAD`, chapdagi `653.5 GIB - 50.0 B/S` | tarmoq tezligi va umumiy hajm |
| `28°C` | ob-havo (open-meteo; `JARVIS_LAT`/`JARVIS_LON`) |
| `Recycle Bin` (`23 items 2.57 GB`) | axlat qutisidagi fayllar soni va hajmi |
| `BATTERY 100% / no battery` va `Currently power level is at 100 percent` | batareya zaryadi va quvvat holati |
| O'ng chetdagi zargaldoq ustun | tizim ovozi — bosgan joyingiz yangi daraja bo'ladi |
| Pleyer `0:00` va ijro chizig'i | ochiq Spotify/Music'dagi qo'shiq vaqti |
| Rasmdagi dumaloq siferblatlar | sekin aylanib turadi |
| Ko'zlar va reaktor | «Hey Jarvis» deganda yonadi |

Bosiladigan joylar ham rasmning o'zida:

- chapdagi Chrome / Control Panel / VLC / Firefox / uTorrent / Skype tugmalari
  va yuqoridagi dok — mos ilovalarni ochadi;
- `GOOGLE / GMAIL / FACEBOOK / YOUTUBE / IMDB / YAHOO / WIKIPEDIA` ro'yxati va
  o'ngdagi radial menyu (Mail, Google, Youtube, Twitter, Facebook) — brauzerda;
- `Downloads / Documents / Dropbox / Pictures / Music / Videos` — Finder'da;
- Recycle Bin — axlat qutisi; pleyer tugmalari — ochiq pleyerga;
- ko'kragidagi reaktor — Jarvis'ni chaqiradi; chap pastdagi JARVIS doirasi —
  bo'g'in siferblatlari paneli.

Sichqonchani olib borsangiz, bosiladigan joy siyon ramka bilan belgilanadi.

**O'z rasmingizni qo'yish.** Boshqa rasmni HUD ustiga sudrab tashlang —
saqlanadi va uch bosishda sozlanadi (chap ko'z, o'ng ko'z, reaktor). Shundan
keyin o'sha rasmning ko'zlari yonadi. `Backspace` — o'rnatilgan wallpaperga
qaytaradi.

### HUD nimani ko'rsatadi

Markazda JARVIS yozuvi — asosiy ikonka. «Hey Jarvis» deganingizda u yorqin
oq bo'lib chaqnaydi, yadro halqalari kengayadi.

Atrofida to'qqizta siferblat, har biri bitta bo'g'inga bog'langan: mikrofon,
uyg'otish, nutq, miya, ovoz, xotira, reja, asbob, tarmoq. Ular shunchaki
bezak emas:

| Ko'rinishi | Ma'nosi |
|---|---|
| Siyon, sekin aylanadi | tayyor, kutmoqda |
| Oq, tez aylanadi | ayni damda ish bajaryapti |
| Sariq | ishlaydi, lekin e'tibor talab qiladi |
| Qizil, X belgisi, to'xtagan | buzilgan |

Bitta bo'g'in buzilsa, HUD chekkasi ham qizg'ish tus oladi. Siferblat ustiga
sichqonchani olib borsangiz, sabab yoziladi — jurnal titkilash shart emas.

Butun ranglar tizimi bitta joyda: `ui/renderer/palette.js`.

## Ekranda nima ko'rinadi

Eng ko'p hafsalani buzadigan holat — Jarvis jim qolishi va nima
bo'layotgani bilinmasligi. Shuning uchun ekranda **doimiy holat qatori**
turadi, u hech qachon yo'qolmaydi:

```
ESHITYAPTI    · gapirishingizni kutyapti (6 s)
O'YLAYAPTI    · Telegram: papka
GAPIRYAPTI
KUTMOQDA
```

Chap tomoni — bosqich, o'ng tomoni — aynan nima qilinyapti. Har bir asbob
chaqiruvi shu yerga chiqadi: «Telegram: o'qiyapti», «buyruq bajaryapti»,
«internetdan qidiryapti», «o'z kodi: tekshiryapti». Ya'ni «uxlayaptimi yoki
ishlayaptimi» degan savol qolmaydi.

Nosozlik esa **qizil qatorda qoladi** — 9 soniyadan keyin so'nmaydi:

```
Nutqni matnga aylantirib bo'lmadi: RuntimeError: whisper-cli topilmadi
```

Ilgari bunday xato faqat jurnalga tushardi va tashqaridan Jarvis
shunchaki jim qolgandek ko'rinardi. Endi sabab ko'rinadi va u
kamchiliklar daftariga ham tushadi — ya'ni «o'zingni yaxshila»
deganingizda Jarvis o'sha xatoni ko'radi.

Qatorlar ikkala oynada ham bor: kichik orbda ham, to'liq ekranli HUD'da ham.

## Qotib qolmaslik

Bir marta shunday bo'ldi: tasdiq berildi, keyin javob kelmadi va ekranda
«O'YLAYAPTI» turib qoldi. Chaqiruv ham, tugma ham ishlamadi — Jarvisni
faqat terminaldan o'ldirish mumkin edi. Sababi arxitekturada edi: seans
tinglash siklining **ichida** kutilardi, ya'ni seans qotsa, uni
to'xtatadigan kod umuman ishga tushmasdi.

Endi seans alohida vazifada yuritiladi va uch xil chiqish yo'li bor:

1. **Qo'riqchi.** Hech qanday taraqqiyotsiz 90 soniya o'tsa, seans o'zi
   to'xtatiladi, ekranda sabab yoziladi va Jarvis «javob kelmadi, qaytadan
   ayting» deydi. Chegara: `conversation.stuck_after_sec`.
2. **Orbni bosish.** Seans ketayotganda bosilsa, u to'xtaydi. Bu qo'ldagi
   eng ishonchli tugma va u har doim ishlaydi.
3. **«To'xta»** buyrug'i (UI orqali) — xuddi shunday.

Qo'riqchi bosqichlarni bilmaydi, u faqat bitta savolga qaraydi: hodisa
kelyaptimi? Shuning uchun yangi imkoniyat qo'shilganda ham himoya
o'z-o'zidan ishlaydi — har bir bosqich uchun alohida chegara yozib,
bittasini unutib qo'yish xavfi yo'q.

Ikkita istisno bor va ular ataylab: **gapirish** (uzun javob normal) va
**tasdiq kutish** (siz o'ylab turgandirsiz). Lekin ularning ham chegarasi
bor — ovoz oqimi osilib qolsa 3 daqiqadan keyin, tasdiq esa
`safety.confirm_timeout_sec` (45 s) dan keyin uziladi.

Halol chegara: seans qotib qolganda **ovozli chaqiruv ishlamaydi** —
mikrofonni o'sha seans egallab turgan bo'ladi. Shuning uchun orbni bosish
va avtomatik qo'riqchi bor. Buni to'g'rilash uchun mikrofon oqimini
bir nechta o'quvchiga bo'lish kerak; u alohida ish va hozircha qilinmagan.

## Suhbat: uyg'otish bir marta

Javob berib bo'lgach Jarvis darhol jim bo'lib qolmaydi — bir necha soniya
tinglab turadi (HUD to'lqin holatida qoladi). Shu oynada gapirsangiz,
«Hey Jarvis» ni takrorlash shart emas:

> — Hey Jarvis, bugun nima ishlarim bor?
> — Uchta: iLevel deploy, Alisher bilan qo'ng'iroq, hisobot.
> — Hisobotni ertaga surib qo'y. ← uyg'otish kerak emas
> — Bo'ldi, ertaga soat 10 ga surdim.

Jim bo'lsangiz, o'zi kutish holatiga qaytadi.

**Gapini bo'lish.** Jarvis gapirayotganda gapirsangiz, o'rtasida to'xtaydi va
sizni tinglaydi. Aytib bo'lgan qismi xotirada qoladi, qolgani aytilmaydi.

Bu yerdagi asosiy qiyinchilik — dinamikdan qaytgan Jarvisning **o'z ovozi**:
mikrofon uni ham eshitadi va VAD uni ham "nutq" deb belgilaydi. Shuning uchun
chegara qattiq yozilmagan, o'zi moslashadi: har kadrda "hozir eshitilib turgan
fon" o'rtalanadi va sizning ovozingiz undan `barge_in_margin` baravar baland
bo'lishi talab qilinadi. Quloqchinda fon deyarli nol — sezgirlik yuqori;
baland dinamikda fon o'z-o'zidan ko'tariladi — yolg'on bo'linish bo'lmaydi.

```yaml
# config/jarvis.yaml
conversation:
  follow_up: true
  follow_up_sec: 8                 # javobdan keyingi tinglash oynasi
  max_turns: 12
  barge_in: true
  barge_in_min_speech_ms: 350      # shuncha uzluksiz nutqdan keyin to'xtaydi
  barge_in_margin: 2.0             # foniga nisbatan shuncha baland bo'lishi kerak
```

Agar Jarvis o'z ovozidan bo'linib ketsa (dinamik juda baland), `barge_in_margin`
ni 3.0 ga ko'taring. Aksincha, sizni eshitmasa — 1.5 ga tushiring yoki
quloqchin ishlating.

### Sukut holati: ekranda hech narsa, lekin eshitib turadi

Kompyuterni yoqasiz — ekranda **hech narsa yo'q**. Orb ham, sahna ham
ko'rinmaydi. Lekin Jarvis ishlab turadi va sizni eshitadi. «Hey Jarvis»
deysiz — o'sha zahoti paydo bo'ladi.

Xuddi shu holatga uch yo'l bilan qaytiladi:

| | |
|---|---|
| **O'zi** | muloqotsiz 5 daqiqa o'tsa |
| **Ovoz bilan** | «bekor qil», «cancel», «bo'ldi bas», «keyin gaplashamiz» |
| **Tugma bilan** | `Esc` · `⌘M` · `⌘W` · `⌘⇧J` |

Bu **o'chish emas**. Mikrofon ishlashda davom etadi, chaqiruv eshitilaveradi —
«Hey Jarvis» (yoki «Jarvis», «Salom Jarvis», qarsak, `⌘⇧J`) bilan hammasi
qaytadi.

`⌘M` ataylab faqat sahna ochiq turganda ushlanadi: u macOS'ning «oynani
yig'ish» tugmasi va uni doimiy egallab olish butun tizimda o'sha tugmani
buzardi.

```yaml
# config/jarvis.yaml
conversation:
  standby_after_sec: 300   # 5 daqiqa. 0 — hech qachon so'nmasin
```

Har qanday muloqot hisobni qaytadan boshlaydi: ovozli chaqiruv, qarsak,
tugma, telefondan yozilgan matn.

Boshqa ilovaga o'tganingizda (⌘Tab) oyna shunchaki yashirinadi — bu sukut
emas, suhbat davom etishi mumkin. Sukutga faqat **ataylab yopganingizda**
o'tadi.

Orb doim ko'rinib tursin desangiz: `standby_after_sec: 0`.

### Salomlashuv: bir so'z

Chaqirilganda aytiladigan javob — bu javob emas, «eshitdim» degan belgi.
Kuniga o'nlab marta eshitiladi, shuning uchun u ataylab bir so'z: **«Aha»**,
«Labbay», «Ha». O'zgartirmoqchi bo'lsangiz:

```yaml
conversation:
  greetings: ["Aha.", "Labbay.", "Ha."]
```

## Telefonda ishlatish

Boshidan aniq aytish kerak: **iPhone'da fon rejimida «Hey Jarvis» deb uyg'otish
mumkin emas.** Apple doim tinglash imkonini faqat Siri'ga bergan — hech qanday
uchinchi tomon ilovasi buni qila olmaydi. Bu Jarvis'ning kamchiligi emas,
iOS'ning chegarasi.

Shuning uchun telefonda uchta haqiqiy yo'l bor, va ular birga yaxshi ishlaydi:

**1. Bosib-gapirish sahifasi (asosiy yo'l).** Yadro telefon uchun sahifani o'zi
tarqatadi. Telefon brauzerida ochasiz, orbni bosasiz, gapirasiz — javob o'sha
telefonga ovoz bilan qaytadi. Ilova o'rnatish shart emas; sahifani "Home Screen"
ga qo'shsangiz, oddiy ilovadek ko'rinadi.

```yaml
# config/jarvis.yaml
ui:
  host: "0.0.0.0"                 # tarmoqdagi qurilmalar uchun
  token: "bu-yerga-tasodifiy-satr"  # openssl rand -hex 16
```

Jarvis ishga tushganda terminalda manzilni yozadi — telefonda o'shani oching.

> **Nega token majburiy?** `0.0.0.0` — bu "bir WiFi'dagi hamma ulanishi mumkin"
> degani. Tokensiz qo'shni ham sizning kompyuteringizda buyruq bajarardi.
> Token bo'lmasa Jarvis ishga tushmaydi va buni aytadi.

Uydan tashqarida ishlatish uchun **Tailscale** qo'ying (bepul) — telefoningiz
va kompyuteringiz qayerda bo'lsa ham bitta xususiy tarmoqda bo'ladi.
Portni internetga to'g'ridan-to'g'ri ochmang.

**2. Siri qisqa yo'li.** Shortcuts'da "Jarvis" nomli qisqa yo'l yarating,
u sahifani ochsin. Shunda «Hey Siri, Jarvis» deysiz — bir so'z ko'p, lekin
telefonni qo'lga olmasdan ishlaydi.

**3. Telegram ovozli xabar.** Kompyuter o'chiq bo'lsa ham ishlaydigan yagona
yo'l — Jarvis keyin o'qiydi va bajaradi.

## Uch xil chaqiruv: «Salom Jarvis», «Hi Jarvis», «Hey Jarvis»

Uchtasi ham ishlaydi, lekin ular bir xil yo'ldan bormaydi — va buni bilib
qo'yish kerak, chunki xarajat va tezlik farq qiladi.

Tayyor model (openWakeWord) faqat **«hey jarvis»** ga o'rgatilgan. Uni aytsangiz,
ball chegaradan (0.5) o'tadi va Jarvis darhol uyg'onadi — tarmoq kerak emas,
kechikish yo'q, hech qanday to'lov yo'q.

«Salom Jarvis» va «Hi Jarvis» esa o'sha modelga faqat qismincha o'xshaydi:
«jarvis» qismi tanilib, ball ko'tariladi, lekin chegaraga yetmaydi. Chegaraning
o'zini pasaytirish yaramaydi — u holda televizor ovozi ham uyg'otib yuboradi.
Shuning uchun **ikkinchi bosqich** bor:

1. ball `candidate_threshold` (0.18) dan o'tadi → bu "shubhali chaqiruv";
2. oxirgi 2 soniya matnga aylantiriladi (STT);
3. matnda «jarvis»ga o'xshash so'z va salomlashuv bo'lsa → uyg'onadi.

Taqqoslash qat'iy emas, chunki STT hech qachon aynan yozmaydi — sizning
mikrofoningizda «hey jarvis» **«Hai, Jervis»** deb chiqqan. Har bir so'z
o'xshashlik darajasi bilan solishtiriladi (`phrase_ratio`).

**Halol narxi:** ikkinchi bosqich — STT chaqiruvi. Ya'ni «salom jarvis» deb
chaqirish ~0.5 soniya sekinroq va pul turadi (juda kichik, lekin bepul emas).
«hey jarvis» bunga tushmaydi. Xarajatni cheklash uchun `verify_cooldown_sec`
bor — Jarvis undan tez-tez tekshirmaydi.

```yaml
activation:
  wake_word:
    threshold: 0.5              # bu balldan o'tsa — darhol
    candidate_threshold: 0.30   # bundan o'tsa — matn bilan tekshiriladi
    phrases: ["hey jarvis", "hi jarvis", "salom jarvis"]
    phrase_ratio: 0.7           # so'z o'xshashligi
    verify_cooldown_sec: 3.0
```

`candidate_threshold` ni juda pastga qo'yish yaramaydi. O'lchab ko'rilganda
**oq shovqinning o'zi 0.10–0.13 ball oladi** — ya'ni 0.15 dan past chegara
xonadagi shitirlashdan ham STT chaqiruvini keltirib chiqaradi. Ball shovqin
darajasidan yuqori bo'lishi shart, aks holda "chaqiruv" tushunchasi ma'nosini
yo'qotadi.

Yangi ibora qo'shish uchun ro'yxatga yozib qo'yish yetarli — kod tegmaydi.
Ikkinchi bosqichni butunlay o'chirish: `phrases: []`.

**Chegarani taxmin bilan emas, o'lchov bilan sozlang.** Yuqoridagi raqamlar
(0.5 / 0.18) — boshlang'ich nuqta, haqiqat emas. Model har bir ovoz, mikrofon
va xonada boshqacha ball beradi:

```bash
python -m jarvis wake-test
```

Har bir iborani bir necha marta aytasiz, ekranda ball jonli ko'rinadi:
yashil = darhol uyg'onadi, sariq = matn bilan tekshiriladi, xira = sezilmadi.
Oxirida har bir ibora uchun eng yuqori ball va tavsiya qilingan chegara
chiqadi.

`python -m jarvis doctor` ham «Hey Jarvis» dagi ballni ko'rsatadi — u modelning
o'zi biladigan ibora, shuning uchun past ball chiqsa, muammo iborada emas,
mikrofonda yoki modelda ekani aniq bo'ladi.

**Halol ogohlantirish.** Tayyor model chetdagi iboralarga juda past ball
berishi mumkin — masalan bir sinovda «Salom Jarvis» **0.017** chiqdi, ya'ni
shovqin darajasida. Bunday holatda chegarani pasaytirish yechim emas: u
holda har qanday shitirlash STT chaqiruvini keltirib chiqaradi. To'g'ri
yechim — o'sha ibora uchun model o'rgatish (pastda).

### To'liq lokal yechim: o'z modelingizni o'rgatish

Ikkinchi bosqichning STT chaqiruvi ham kerak bo'lmasin desangiz, «salom jarvis»
uchun o'z modelingizni o'rgatasiz. Bu bir martalik ish va bepul:

1. openWakeWord'ning tayyor daftarida (`automatic_model_training.ipynb`,
   Google Colab'da bepul ishlaydi) iborani kiriting: `salom jarvis`.
2. U sintetik ovozlar bilan ma'lumot yaratib, `.onnx` model chiqaradi.
3. Modelni `~/.jarvis/wakewords/` ga qo'ying va konfiguratsiyada ko'rsating:

```yaml
activation:
  wake_word:
    model: "salom_jarvis"
    threshold: 0.45
```

Ancha tezroq muqobil: **Picovoice Porcupine** — veb-interfeysida istalgan
iborani yozib, bir necha daqiqada model olasiz. Bepul tier shaxsiy foydalanish
uchun yetarli. `backend: "porcupine"` qiling va `PICOVOICE_ACCESS_KEY` qo'ying.

## Uzoq masofadan chaqirish

Xonaning narigi burchagidan chaqirmoqchi bo'lsangiz:

```yaml
audio:
  input_gain: 3.0        # kirish signalini kuchaytirish
activation:
  wake_word:
    threshold: 0.35      # sezgirroq (standart 0.5)
```

Kuchaytirish shovqinni ham kuchaytiradi — yolg'on ishga tushish ko'paysa,
qiymatlarni qaytaring. Rostini aytganda, eng katta farqni yaxshi mikrofon
beradi: MacBook'ning ichki mikrofoni 1–2 metrgacha yaxshi ishlaydi, undan
narisiga tashqi mikrofon kerak.

### Eshitishni almashtirish

Qaysi provayder to'g'ri kelishini faqat o'z ovozingiz, o'z mikrofoningiz va
o'z internetingiz bilan sinab bilasiz. Shuning uchun YAML faylni qo'lda
ochish shart emas:

```bash
python -m jarvis stt                # hozir qaysi biri
python -m jarvis stt whisper_local  # almashtirish
```

| Provayder | Qanday |
|---|---|
| `elevenlabs` | eng aniq va tez; internet va kalit kerak, har so'rov pullik |
| `mohir` | o'zbek tiliga ixtisoslashgan; internet va kalit kerak |
| `whisper_local` | oflayn va bepul; M-seriyali Mac'da tez |
| `whisper_cpp` (`rubai`) | oflayn va bepul; aniq, lekin sezilarli kechikish beradi |

Kechikish sezilsa birinchi navbatda shu qatorni almashtiring: oflayn model
avval butun audioni matnga aylantiradi, ya'ni javob boshlanishidan oldin
qo'shimcha vaqt ketadi.

### Qachon javob berishni boshlaydi

Jimlik taymeri bitta savolga ikki xil javob bera olmaydi: «bir soniya
jimlik» — bu gap tugagani ham, odam o'ylanib qolgani ham bo'lishi mumkin.
Qisqa kutsa gapni bo'ladi, uzoq kutsa har bir javob kechikadi.

Shuning uchun qaror **aytilgan gap bo'yicha** qabul qilinadi:

| Gap qanday tugadi | Nima bo'ladi |
|---|---|
| «…Instagramga kir» | 1 soniyadan keyin javob beradi |
| «…kir va» · «…keyin» · «…chunki» | davomini kutadi |
| «aaa» · «mmm» | davomini kutadi |
| «…aytib ber.» (nuqta bilan) | darhol javob beradi |

```yaml
audio:
  endpointing:
    silence_ms: 1000       # gap tugagach shuncha kutadi
conversation:
  continue_wait_sec: 2.0   # tugamagan gapning davomini shuncha kutadi
  continue_tries: 2        # shuncha marta
```

Ya'ni tez javob uchun `silence_ms` ni pasaytiring; o'ylanib gapiradigan
bo'lsangiz `continue_wait_sec` ni ko'taring. Ikkalasi bir-biriga xalaqit
bermaydi.

### Gapni bo'lganda boshi yo'qolmasin

«To'xta, Instagramga kirib buni qil» — odam Jarvisning gapini bo'lib,
darhol buyruqni aytadi. Bu yerda ikkita tuzoq bor edi.

**Birinchisi:** «to'xta» so'zi gapning boshida turgani uchun butun gap
«gapirishni to'xtat» deb o'qilib, tashlab yuborilardi. Endi faqat
**yolg'iz** «to'xta» shunday o'qiladi; orqasidan buyruq kelsa — bu buyruq.

**Ikkinchisi:** bo'lish qarori ~350 ms nutqdan keyin qabul qilinadi va
undan keyin ham ijroni to'xtatishga vaqt ketadi. 300 ms lik preroll bunga
yetmasdi — Jarvis gapni o'rtasidan eshitardi. Endi orqaga qarash oynasi
alohida sozlanadi:

```yaml
conversation:
  interrupt_lookback_ms: 1200
```

### Mikrofon o'lib qolsa — o'zi tiklanadi

macOS audio qurilmani almashtirganda (quloqchin ulandi, boshqa ilova
chiqishni o'zgartirdi) PortAudio oqimi **jimgina** to'xtaydi: na xato, na
kadr keladi. Tashqaridan bu «Jarvis to'satdan kar bo'lib qoldi» bo'lib
ko'rinadi — chaqiruv ham, orbni bosish ham, `⌘⇧J` ham ishlamaydi.

Ikkita himoya bor:

* kadr kelmasa, oqim jim kadr beradi — asosiy sikl qotib qolmaydi va
  tugmalar ishlashda davom etadi;
* qo'riqchi 6 soniya kadr kelmaganini sezsa, mikrofonni **o'zi qaytadan
  ochadi** va jurnalga yozadi.

Shu paytda HUD'dagi mikrofon siferblati qizaradi — ya'ni nima
bo'layotgani ko'rinib turadi.

### Musiqa chalinib turganda

Siz gapira boshlaganingizda musiqa **butunlay jim bo'ladi** — pasaymaydi,
o'chadi. Sababi oddiy: pasaytirilgan musiqani ham mikrofon eshitadi va u
sizning gapingiz bilan aralashib, matnga aylantirishni buzadi.

Gapirib bo'lganingizdan keyin avvalgi daraja qaytariladi — ya'ni Jarvis
ishni bajarayotganda musiqa chalinaveradi.

```yaml
audio:
  duck_while_listening: true
  duck_volume: 0        # 0 — butunlay jim; 20 — pasaytirish
```

Quloqchin taqsangiz bu umuman kerak emas: `duck_while_listening: false`.

### Ovozni sinash

Almashtirgandan keyin darhol eshitib ko'rish uchun:

```bash
python -m jarvis say
python -m jarvis say "Salom, bu sinov"
```

U avval **nima ishlatilayotganini yozadi** (provayder, ovoz, kalitlar
joyidami), keyin o'sha bilan gapiradi. «Sozlamani o'zgartirdim, lekin ovoz
o'sha-o'sha» degan holatda birinchi navbatda shu buyruqni bering: u
sozlama haqiqatan o'zgarganini yoki eski nusxa ishlab turganini ajratib
beradi.

### Gapirishni almashtirish — aksent shu yerda hal bo'ladi

```bash
python -m jarvis tts              # hozir qaysi ovoz
python -m jarvis tts azure        # haqiqiy o'zbek ovozi
python -m jarvis tts azure uz-UZ-MadinaNeural
```

macOS'ning o'z ovozlari orasida o'zbekchasi **yo'q** — ular o'zbek matnini
ingliz talaffuzi bilan o'qiydi. ElevenLabs tabiiyroq, lekin uning ham
o'zbekchasi begona aksent bilan chiqadi. Yagona haqiqiy o'zbek ovozi —
Azure'ning `uz-UZ-SardorNeural` va `uz-UZ-MadinaNeural` ovozlari.

Kerak: `.env` da `AZURE_SPEECH_KEY` va `AZURE_SPEECH_REGION`.

## O'zbek tili uchun ovoz: qaysi provayderni tanlash

Bu loyihaning eng nozik qismi — o'zbekcha sifat provayderdan provayderga
sezilarli farq qiladi. Shuning uchun provayderlar almashtiriladigan qilingan:
`config/jarvis.yaml` da bir qator o'zgartirsangiz kifoya.

| Provayder | STT | TTS | Izoh |
| --- | :---: | :---: | --- |
| **ElevenLabs** | ✅ Scribe | ✅ multilingual v2 | Standart tanlov. Bitta kalit bilan ikkalasi ham ishlaydi. |
| **Mohir.ai** (UzbekVoice) | ✅ | ✅ | Aynan o'zbek tiliga o'rgatilgan, mahalliy. Aksentda aniqroq bo'lishi mumkin. |
| **Azure Speech** | — | ✅ `uz-UZ-SardorNeural`, `uz-UZ-MadinaNeural` | Haqiqiy o'zbekcha neyron ovozlar. |
| **Whisper (lokal)** | ✅ | — | Internetsiz ishlaydi. Apple Silicon'da MLX orqali tez. |

**Tavsiya:** ElevenLabs bilan boshlang, keyin o'z ovozingizda uch variantni
solishtiring. Ovoz sifati — bu tizimda foydalanish tajribasini eng ko'p
belgilaydigan omil.

```yaml
# config/jarvis.yaml
voice:
  stt:
    provider: "mohir"          # elevenlabs | mohir | whisper_local
  tts:
    provider: "azure"          # elevenlabs | azure | mohir | macos
    voice: "uz-UZ-SardorNeural"
```

## Telegram: o'z akkauntingiz bilan

Ikki xil Telegram ulanishi bor va ular chalkashtirilmasligi kerak.

| | Bot (`@sizning_botingiz`) | **Shaxsiy akkaunt** |
|---|---|---|
| Kim nomidan yozadi | botning nomidan | **sizning nomingizdan** |
| Kimga yoza oladi | faqat botga /start yozgan odamga | istalgan tanishingizga |
| Chatlaringizni ko'radimi | yo'q | **ha** |
| Nima uchun kerak | «ish tugadi» deb sizga xabar berish | «Ibrat nima yozdi?», «Ibratga yoz: juma muborak» |
| Sozlash | `.env` da `TELEGRAM_BOT_TOKEN` | `python -m jarvis telegram-login` |

Ya'ni «Jarvis, Ibratga yoz» degan gap faqat shaxsiy akkaunt orqali ishlaydi —
bot buni qila olmaydi, chunki bot boshqa shaxs.

### Ulash (bir marta, qo'lda)

```bash
pip install -e '.[telegram]'          # Telethon (MTProto kutubxonasi)
python -m jarvis telegram-login
```

Buyruq ketma-ket so'raydi: **api_id**, **api_hash** (ikkalasi
[my.telegram.org](https://my.telegram.org) → *API development tools* dan),
telefon raqamingiz, Telegramdan kelgan **kod** va ikki bosqichli **parol**
(agar yoqilgan bo'lsa).

`api_id` va `api_hash` bir marta kiritilgach darhol saqlanadi — keyingi
qadamlardan biri to'xtab qolsa ham (raqam xato, kod kelmadi) ularni qaytadan
yozib o'tirmaysiz.

Ikki joyda ko'p adashiladi, shuning uchun buyruq ularni o'zi to'g'rilaydi:

* **Raqam mamlakat kodi bilan bo'lishi kerak** — `+998935991333`. `935991333`,
  `998935991333` yoki `93-599-13-33` deb yozsangiz ham to'g'ri ko'rinishga
  keltiriladi va qanday o'qilgani ko'rsatiladi.
* **Kod SMS bilan kelmaydi** — u Telegram ilovasidagi rasmiy «Telegram»
  chatiga keladi va har urinishda yangilanadi. Xato kiritsangiz qaytadan
  so'raydi, muddati o'tgan bo'lsa yangi kod yubortiradi.

Bularning hammasini siz terminalga o'zingiz kiritasiz. Ular modelga
ko'rsatilmaydi, jurnalga yozilmaydi va repozitoriyga tushmaydi: api_id/api_hash
`~/.jarvis/telegram.json` (faqat siz o'qiy olasiz), seansning o'zi esa
`~/.jarvis/telegram.session` da saqlanadi. **Seans fayli parolga teng** — uni
hech kimga bermang.

Tekshirish: `python -m jarvis doctor` → «Telegram (shaxsiy akkaunt)» qatorida
kirilgan akkaunt ismi chiqadi.

Bekor qilish: `python -m jarvis telegram-logout` — seans Telegram tomonida ham
bekor qilinadi va fayl o'chiriladi.

### Nima deyish mumkin

| Gap | Nima bo'ladi |
|---|---|
| «Telegramda nima yangilik?» | o'qilmagan chatlarni sanab beradi |
| «Ibrat nima yozdi?» | o'sha chatning oxirgi xabarlarini o'qib beradi |
| «Ibratga yoz: juma muborak» | Telegramni o'sha chatda ochadi va yuboradi |
| «Unday emas, "Bayramingiz bilan" deb yoz» | oxirgi xabarni tuzatadi |
| «O'chir» / «bekor qil» | oxirgi xabarni olib tashlaydi — u yerda ham yo'qoladi |
| «Ish guruhiga o'sha shartnomani tashla» | faylni kompyuterdan topib yuboradi |
| «Buni dumaloq video qilib yubor» | video note sifatida yuboradi |
| «Guruhga so'rovnoma tashla: qachon uchrashamiz — ertaga, indinga» | poll yaratadi |
| «Loyiha guruhini och, Ibrat bilan Asadni qo'sh» | guruh yaratadi va odam qo'shadi |
| «Telegramni analiz qilib ber» | nechta chat, nima o'qilmagan, qaysi kanallar jim |
| «Bu kanaldan chiqib ket» | guruh yoki kanaldan chiqadi |

### «Bir vaqtlar tashlagan edim…»

Eng ko'p kerak bo'ladigan narsa — qachonligi esdan chiqqan xabar.
`telegram_search` butun akkaunt bo'ylab qidiradi: qaysi chat ekanini
bilish shart emas.

> — Jarvis, bir vaqtlar kimgadir shartnoma shablonini tashlagan edim, topib ber.
>
> — 23-fevralda Asad bilan yozishganingizda tashlagansiz. Men uni
>   saqlangan xabarlaringizga ko'chirib qo'ydim — tez topib olasiz.

Saqlangan xabarlar oddiy chat sifatida ishlaydi: `kim: men` deb qidirish
yoki o'sha yerga yozish mumkin.

### Tasdiq o'rniga — ko'rib turish

Har bir xabar uchun «ha yoki yo'q deb ayting» deb turish ish jarayonini
buzadi: aytdingiz, javob kutdingiz, keyin yuborildi. Shuning uchun boshqa
yo'l tanlangan:

1. Yuborishdan **oldin** Telegram ilovasi o'sha chatda ochiladi;
2. xabar ko'z oldingizda paydo bo'ladi — kimga va nima ketganini ko'rasiz;
3. xato ketsa **«tahrirla»** yoki **«o'chir»** deysiz. O'chirilgan xabar
   qabul qiluvchining ekranidan ham yo'qoladi (`revoke`).

Telegram tahrirlash va o'chirishga 48 soat beradi — undan keyin xabar
o'zgarmas bo'lib qoladi.

Eski xatti-harakat (har safar tasdiq) kerak bo'lsa, `config/jarvis.yaml` ga:

```yaml
safety:
  rules:
    mcp__jarvis__telegram_send: "ask"
```

### Papkalar, adminlik va guruhni boshqarish

Papkalar (Telegram atamasida «folders») bot API'da umuman yo'q — bu mijoz
xususiyati. Akkaunt ulangani uchun Jarvis ularni ham yig'a oladi:

> — Jarvis, «Ish» degan papka och, ichiga Click Jobs, UzDev Jobs va
>   Freelancer Uzni sol.
>
> — «Ish» papkasi yaratildi, uchta kanal qo'shildi.

Bir gapda o'nlab kanalni sanab ketsangiz ham bo'ladi. Papka bo'lmasa
yaratiladi, bo'lsa ustiga qo'shiladi; bir xil kanal ikki marta tushmaydi.
Kanal chatlaringiz orasida bo'lishi kerak — bo'lmasa «qo'shil» deng,
`telegram_join` uni @username yoki `t.me/+...` havolasi bilan topadi.

Guruh boshqaruvi ham o'sha joyda:

| Siz aytasiz | Asbob |
| --- | --- |
| «Alisherni Dev guruhiga qo'sh va admin qil» | `telegram_add_members` → `telegram_promote` |
| «Uni adminlikdan ol» | `telegram_demote` |
| «Falonchini guruhdan chiqar» | `telegram_kick` (tasdiq so'raydi) |
| «Guruh nomini o'zgartir» | `telegram_rename` |
| «Bu xabarni qadab qo'y» | `telegram_pin` |
| «Bu chatni arxivga sol / ovozini o'chir» | `telegram_archive` / `telegram_mute` |
| «Kim bor guruhda?» | `telegram_members` |
| «Havolasini ber» | `telegram_link` |

Odam qo'shilmasligi mumkin — ko'pchilikda Telegram maxfiyligi buni to'sadi.
Bu xato emas: Jarvis sababini aytadi va taklifnoma havolasini beradi.

### Akkauntning qolgan qismi

Telegramda o'zingiz qila oladigan ishlarning ko'pi asbob sifatida bor:

| Nima | Asbob |
| --- | --- |
| Odamni bloklash / blokdan chiqarish | `telegram_block`, `telegram_blocked` |
| Telegram kontaktlari | `telegram_contacts`, `telegram_contact_add`, `telegram_contact_delete` |
| Xabarga reaksiya | `telegram_react` |
| GIF qidirib yuborish | `telegram_gif` |
| Belgilangan vaqtda yuborish (Telegram o'zi jo'natadi) | `telegram_send_later`, `telegram_scheduled` |
| Storiya qo'yish va o'chirish | `telegram_story`, `telegram_stories`, `telegram_story_delete` |
| Ovozli chat / jonli efir ochish | `telegram_voice_chat`, `telegram_live_url` |
| Profil, bio, @username, rasm | `telegram_profile`, `telegram_username`, `telegram_photo` |
| Kirgan qurilmalar va seansni uzish | `telegram_sessions`, `telegram_session_kill` |
| Maxfiylik sozlamalari | `telegram_privacy` |
| Sekin rejim, a'zolar huquqlari, admin jurnali | `telegram_slow_mode`, `telegram_permissions`, `telegram_admin_log` |
| Sovg'alar va NFT o'tkazish | `telegram_gifts`, `telegram_gift_transfer` |

Misollar:

> — Falonchini blokla.
>
> — Ertaga soat to'qqizda Asadga «yig'ilish boshlandi» deb yubor.
>   *(Telegram o'zi jo'natadi — kompyuter o'chiq bo'lsa ham.)*
>
> — Shu rasmni storiyaga qo'y, faqat kontaktlarga ko'rinsin.
>
> — Dev guruhida ovozli chat och.
>
> — Bio'mni «Ishga ochiq» deb o'zgartir.

### Nima qila olmaydi — halol ro'yxat

Bularni ochiq aytish kerak, aks holda «ishlamadi» degan hafsala qoladi:

- **Jonli efirda o'zi gapirmaydi va video uzatmaydi.** Ovozli chatni ochadi va
  RTMP havolasi bilan kalitini beradi — efirni OBS yoki shunga o'xshash dastur
  uzatadi. Ovoz oqimini Jarvisning o'zidan chiqarish alohida katta ish
  (WebRTC) va u ovozli yordamchining mikrofoni bilan to'qnashadi.
- **Bir kishilik qo'ng'iroq qilmaydi** (audio/video call) — xuddi shu sabab.
- **Sovg'a sotib olmaydi.** Faqat boringini ko'radi va NFT'sini o'tkazadi.
  Sotib olish hisobdan to'g'ridan-to'g'ri pul yechadi — uni sinovdan
  o'tkazmasdan qo'yish noto'g'ri bo'lardi.
- **Forum mavzularini (topics) yaratmaydi** — Telethon'ning joriy versiyasida
  bu so'rov yo'q. Kutubxona yangilanganda qo'shiladi.
- **Ommaviy yuborish yo'q.** Bitta odamga qayta-qayta yozish yoki bir xil
  xabarni ko'pchilikka ketma-ket jo'natish uchun asbob yozilmagan: bu
  odamlarni bezovta qilish va akkaunt cheklanishining eng tez yo'li.
  Kanalga bitta e'lon yoki rejalashtirilgan xabar — bemalol.

### Ovozli xabarlar ichidan qidirish

Telegram qidiruvi ovozli xabarni **topa olmaydi** — uning ichida matn yo'q,
faqat audio. Shuning uchun alohida yo'l bor:

| Nima | Asbob |
| --- | --- |
| Ovozlilar ichidan so'z qidirish | `telegram_voice_search` |
| Ovozlilarni matnga aylantirib o'qish | `telegram_voice_read` |
| Butun suhbatni faylga yozish (ovozlilar bilan) | `telegram_export` |

Aylantirish ikki yo'l bilan bo'ladi, shu tartibda:

1. **Telegramning o'zi** (Premium xususiyati) — tez, fayl yuklab olinmaydi.
2. **O'zimizniki** — fayl yuklab olinadi, `ffmpeg` bilan o'giriladi va
   sozlamadagi STT provayderiga beriladi. Buning uchun `brew install ffmpeg`
   kerak.

Bir marta aylantirilgan yozuv `~/.jarvis/telegram_transcripts.json` da
saqlanadi: birinchi qidiruv sekin, keyingilari darhol.

**Kelishmovchilikda** («men aytganman, u aytmagan deydi») bitta xabarni
topish yetarli emas — `telegram_export` butun yozishmani matn faylga
yozadi, ovozlilarni ham o'z o'rniga qo'yadi:

```
[2026-03-01 12:04] Asad: qachon berasiz?
[2026-03-01 12:07] Siz: [ovozli] kecha besh ming berib yubordim
```

Fayl `~/jarvis-workspace/` ga tushadi — uni saqlash va kerak bo'lsa
ko'rsatish mumkin.

**Halol ogohlantirish.** Ovozdan aylantirilgan matn — taxminiy. O'zbek
tili uchun xato ehtimoli bor, ayniqsa ism va raqamlarda. Shuning uchun
muhim joy topilganda Jarvis xabarning **sanasi va raqamini** aytadi:
asl yozuvni o'zingiz eshitib tekshiring. Rasmiy dalil sifatida
ishlatmoqchi bo'lsangiz, asl audio bilan birga ishlating.

### Nima har safar so'raladi

Kundalik ishlar so'ramasdan bajariladi. Qaytarib bo'lmaydiganlari esa **har
safar alohida** so'raydi — bir marta «ha» degan javob keyingisiga o'tmaydi,
va `jarvis trust on` ham buni yumshata olmaydi:

- chat yoki kanalni o'chirish
- xabarlarni o'chirish
- odamni chiqarib yuborish / bloklash
- kanaldan chiqish
- papkani o'chirish

Ro'yxat `config/jarvis.yaml` dagi `safety.always_ask` da — o'zgartirish mumkin.

Pul bilan bog'liq asboblar (sovg'a, Stars, Premium) umuman yozilmagan: Jarvis
xato bilan ham pul sarflay olmaydi.

Diqqat: shaxsiy akkauntni avtomatlashtirish Telegram qoidalari bo'yicha ehtiyot
talab qiladi. Ommaviy tarqatma yubormang — akkaunt cheklanishi mumkin.

## Daftarlar — Jarvis o'zi yozib boradigan xotira

`~/.jarvis/` ichida to'rtta oddiy Markdown fayl bor. Ularni Jarvis o'zi
to'ldiradi, siz esa istalgan paytda ochib o'qishingiz, tuzatishingiz yoki
o'chirishingiz mumkin:

| Fayl | Nima uchun |
| --- | --- |
| `men.md` | Siz haqingizda: ishingiz, odatlaringiz, nimani yoqtirmasligingiz, qanday gapirishingiz |
| `qoidalar.md` | «Bundan keyin shunday qil» / «bunday qilma» — doimiy ko'rsatmalar |
| `xatolar.md` | Qilgan xatolari va ularni takrorlamaslik uchun xulosa |
| `lugat.md` | Siz tushunmagan so'zlar va ularning ma'nosi |

Har bir suhbat boshida to'rttasi ham tizim ko'rsatmasiga qo'shiladi —
ya'ni bu Jarvisning haqiqiy xotirasi, uni «o'qishni unutmaydi».

Ovoz bilan shunday to'ldiriladi:

> — Jarvis, buni eslab qol: menga «albatta» deb gapirma, jonimga tegadi.
>
> — Yozib qo'ydim.

Endi bu `qoidalar.md` da turadi va har suhbatda amal qiladi. Xuddi shunday:

- «Bu so'zni tushunmadim, karnaval nima degani?» → javob beradi va
  `lugat.md` ga yozadi. Keyingi safar o'sha so'zni ishlatishdan oldin
  izohlab o'tadi.
- «Bu xato bo'ldi» → `xatolar.md` ga nima qilgani va keyingi safar nima
  qilish kerakligini yozadi.
- Suhbat davomida siz haqingizda bilib olgan barqaror narsalarni
  `men.md` ga o'zi yozib boradi — shu jumladan gapirish uslubingizni.

Eskirgan yozuvni «buni o'chir» yoki «endi bunday emas» deb olib
tashlatasiz. Fayllarni qo'lda tahrirlash ham mumkin: keyingi suhbatda
yangi holat kuchga kiradi.

Nima uchun `memory.db` dan tashqari yana shu kerak: baza kalit/qiymat
juftliklari — mashina uchun qulay, odam uchun yopiq. Daftar esa ochib
ko'radigan, tuzatadigan va ishonadigan narsa.

## O'zini o'zi yaxshilash

Odatiy javob — «xo'p, keyingi versiyada tuzatamiz». Bu yerda boshqacha:
Jarvisning kodi shu kompyuterda turibdi, u esa kod yoza oladi.

«Bu menga yoqmadi», «juda sekin javob beryapsan», «bunday emas, anaqa qil» —
bularning hammasi topshiriq:

1. Kamchilikni daftarga yozadi (`~/.jarvis/improvements.jsonl`).
2. Ekranda **«O'Z USTIDA ISHLAMOQDA»** yozuvi paydo bo'ladi — orbda ham,
   to'liq ekranli HUD'da ham. Bu yozuv turganida buyruq bermang: u kod
   ustida, gapingiz behuda ketadi.
3. Git'da orqaga qaytish nuqtasi saqlanadi.
4. Kodni o'zgartiradi, so'ng testlar va linterni ishga tushiradi.
5. Yozuv o'chadi va nima o'zgarganini aytadi. Yangi kod kuchga kirishi uchun
   qayta ishga tushishni taklif qiladi — «ha» desangiz o'zini o'zi qayta
   ishga tushiradi (orb yopilmaydi, bir-ikki soniyada qaytadi).

Yoqmasa: **«orqaga qaytar»** — oxirgi o'zgarishlar bekor qilinadi.

Jarvis o'z xatolarini ham ko'radi: javob berishda yuz bergan har bir xato
o'sha daftarga tushadi va takrorlangani sanaladi. «O'zingni yaxshila»
desangiz, ro'yxatdan eng ko'p takrorlanganini oladi.

Ruxsat `config/jarvis.yaml` da yoqiladi:

```yaml
safety:
  self_edit: true        # repo papkasi yoziladigan joylar ro'yxatiga qo'shiladi
```

`false` qilsangiz, Jarvis o'z kodiga umuman tegolmaydi va tizim
ko'rsatmasidan ham bu bo'lim olib tashlanadi.

Uni xavfsiz qiladigan uchta narsa:

- har o'zgarishdan oldin git'da surat olinadi;
- qayta ishga tushirishdan oldin testlar va linter ishlaydi — yiqilsa,
  qayta ishga tushirish taklif qilinmaydi;
- «orqaga qaytar» bitta gap.

Halol cheklov: Jarvis o'zining **ishlayotgan** kodini o'zgartiradi. Ya'ni
noto'g'ri o'zgarish uni ishlamaydigan qilib qo'yishi mumkin. Shuning uchun
git tarixi va `self_revert` bor — lekin baribir bu ruxsatni ishonch
ortgan sari beriladigan narsa deb qarang.

## Xavfsizlik — eng muhim qism

«Mensiz to'liq nazorat» — bu tizimning eng xavfli tomoni. Agent `rm -rf` yozsa
yoki ma'lumotlar bazasida noto'g'ri `UPDATE` bajarsa, uni kim to'xtatadi?

Shuning uchun har bir asbob chaqiruvi xavfsizlik darvozasidan o'tadi:

### Tasdiq — ovoz bilan

Tasdiq so'ralganda Jarvis savolni **ovozda beradi** va javobni ovozdan
o'qiydi: «ha», «mayli, bajar», «ruxsat beraman» — rozilik; «yo'q»,
«to'xta», «kerak emas» — rad. Tugma bosish shart emas — kompyuter
qo'lingizda bo'lmasa ham jarayon kutib qolmaydi. Tugmalar ishlashda davom
etadi: qaysi biri oldin javob bersa, o'sha hal qiladi.

Qoida xavfsizlik tomonga og'gan: «ruxsat bermayman» ichida «ruxsat» so'zi
bor, lekin bu RAD deb o'qiladi — rad so'zi topilgan har qanday javob rad.
Noaniq javob hech qachon roziliqqa aylanmaydi: Jarvis «Ha yoki yo'q deb
ayting» deb qayta so'raydi, javob bo'lmasa muddat tugashi rad hisoblanadi.

```yaml
safety:
  voice_confirm:
    enabled: true
    listen_sec: 8      # har urinishda shuncha soniya tinglaydi
    attempts: 2        # noaniq javobda necha marta qayta so'raydi
```

```yaml
safety:
  default: "ask"
  rules:
    Read: "allow"       # o'qish — qaytarib bo'ladi, so'ralmaydi
    Bash: "ask"         # shell — har safar tasdiq
    Write: "ask"        # fayl yozish — tasdiq
  forbidden_patterns:   # bular umuman bajarilmaydi
    - "rm -rf /"
    - "sudo rm"
  writable_roots:       # bulardan tashqariga yozib bo'lmaydi
    - "~/jarvis-workspace"
```

Uch qatlam:

1. **Taqiqlangan naqshlar** — tasdiq ham so'ralmaydi, shunchaki bajarilmaydi.
2. **Papka chegarasi** — ruxsat etilgan papkalardan tashqariga yozish bloklanadi
   (shell `>` yo'naltirishlari ham tekshiriladi).
3. **Tasdiq** — qolgan xavfli amallar HUD'da ✅/❌ bo'lib chiqadi.

Hammasi `~/.jarvis/audit.log` ga yoziladi. **Boshidan to'liq erkinlik bermang** —
ishonch ortgan sari qoidalarni yumshating.

### Tasdiq so'rashni butunlay o'chirish

Har bir amal uchun «ha yoki yo'q» deb turish halaqit bera boshlasa:

```bash
python -m jarvis trust on      # holatni ko'rish: trust status
```

Terminalsiz: `scripts/**Jarvis ishonch rejimi.command**` ni ikki marta bosing.

Shundan keyin «qil» deganingizda darhol bajaradi. Lekin bu «hamma narsaga
ruxsat» degani emas — ikki qatlam ataylab qoladi:

* `forbidden_patterns` — `rm -rf /`, `mkfs`, `sudo rm` hech qachon bajarilmaydi;
* `writable_roots` — yozish faqat ruxsat etilgan papkalarda.

Telegramda sizning nomingizdan yozish ham tasdiq so'ramaydi. Uning himoyasi
boshqacha: chat ko'z oldingizda ochiladi va xato ketgan xabarni «tahrirla»
yoki «o'chir» deb tuzatasiz.

## Halol cheklovlar

Buni oldindan bilib qo'ying, keyin ko'ngil qolmasin:

**Telefonda «Hey Jarvis» deb fon rejimida uyg'otib bo'lmaydi.** Apple buni faqat
Siri'ga ruxsat bergan. Yuqoridagi uchta yo'l — sahifa, Siri qisqa yo'li, Telegram —
mavjud eng yaxshi variantlar.

**iPhone'ni to'liq boshqarib bo'lmaydi.** Shortcuts orqali cheklangan ishlar mumkin
(eslatma, xabar, joylashuv), lekin «telefonimni to'liq boshqar» degani iOS'da yo'q.
Android'da ADB va Tasker bilan ancha ko'p narsa mumkin.

**Kompyuter yoqiq bo'lishi kerak.** Jarvis lokal ishlaydi — uxlab qolgan mashinada
ishlamaydi, eslatmalar ham aytilmaydi (uyg'onganda aytiladi). Uxlashini
to'xtatish uchun: Tizim sozlamalari → Batareya → "Prevent automatic sleeping".
Doimiy ishlashi kerak bo'lgan ishlarni VPS'dagi n8n'ga o'tkazing va `call_n8n`
orqali ulang.

**Ovoz kechikishi bor.** Uyg'onishdan javobgacha odatda 2–4 soniya: gapirish
tugashini kutish, STT, model, TTS. Javob gap-gap chiqariladi, shuning uchun
birinchi so'z tezroq eshitiladi — lekin bu Siri emas.

**O'zbekcha STT mukammal emas.** Texnik atamalar, ingliz so'zlari va tez gapirish
xatolarga olib keladi. Muhim buyruqlarni sekinroq va aniq ayting.

**Xarajat.** Claude API ishlatilishiga qarab ~$20–60/oy, ElevenLabs alohida.
`brain.max_budget_usd` bilan har bir suhbatga chegara qo'ying.

## Loyiha tuzilishi

```
jarvis/
├── audio/          mikrofon, uyg'otuvchi so'z, qarsak, VAD, gapni bo'lish
├── voice/          STT va TTS provayderlari + ijro
├── brain/
│   ├── agent.py    Claude Agent SDK ustidagi qatlam
│   ├── agenda.py   loyihalar, vazifalar, aloqalar
│   ├── memory.py   barqaror faktlar va suhbatlar
│   └── prompts.py  o'zbekcha tizim ko'rsatmasi
├── safety/         xavfsizlik darvozasi va audit
├── tools/          xotira, agenda, macOS, Telegram, Shortcuts asboblari
│   └── telegram_user.py  shaxsiy Telegram akkaunt (MTProto)
├── ui/             orb va telefon uchun HTTP + WebSocket server
├── notebook.py     daftarlar: men, qoidalar, xatolar, lug'at (~/.jarvis/*.md)
├── selfwork.py     o'z kodini o'zgartirish: daftar, git, tekshiruv, restart
├── scheduler.py    vaqti kelgan ishlarni o'zi aytadi
├── idle.py         sukut holati taymeri
├── bus.py          hodisa shinasi
├── health.py       bo'g'inlar tirikligi — HUD siferblatlari shundan
├── doctor.py       diagnostika (`jarvis doctor`)
└── __main__.py     asosiy sikl

ui/
├── main.js         Electron oynalari + tizim ko'rsatkichlari (CPU, disk, batareya…)
└── renderer/
    ├── palette.js  ranglar — yagona manba
    ├── hud.js      bo'g'in siferblatlari
    ├── suit.js     zirh chizmasi (ko'zlar, reaktor)
    ├── desktop.js  ish stoli sahnasi va rasm ustidagi nur effektlari
    ├── live.js     wallpaperdagi raqamlarni jonlantiruvchi qatlam
    ├── orb.js      yadro bilan aloqa va kadrlar sikli
    └── phone.html  telefon sahifasi (bitta faylda)
```

Buyruqlar:

```bash
python -m jarvis                     # ishga tushirish
python -m jarvis doctor              # har bir qismni alohida tekshirish
python -m jarvis wake-test           # chaqiruv ballini o'lchash
python -m jarvis wake-set 0.33 0.25  # chegarani sozlamaga yozish
```

`wake-set` sozlama faylini o'zi tahrirlaydi va izohlarni saqlaydi. Qo'lda
tahrirlashdan ko'ra shu ishonchli: YAML bo'sh joyga sezgir va bitta ortiqcha
probel Jarvisni butunlay ishga tushmaydigan qiladi. Eski nusxa `.bak` bo'lib
qoladi.

Testlar API kaliti va mikrofon talab qilmaydi:

```bash
python -m pytest tests/ -q
```

## Misollar

Ovoz bilan aytishingiz mumkin:

| Siz aytasiz | Jarvis nima qiladi |
| --- | --- |
| «Ertaga soat 10 da Alisher bilan uchrashuv» | vazifa yozadi va **ertaga soat 10 da o'zi eslatadi** |
| «Har kuni ertalab 9 da iLevel hisobotini tekshir» | takrorlanuvchi vazifa yaratadi |
| «Loyihalarim qaysi bosqichda?» | har birining holati va keyingi qadamini aytadi |
| «iLevel loyihasi test bosqichida, keyingi qadam — deploy» | loyiha holatini yangilaydi |
| «Alisherga yoz, kechikaman de» | aloqani topib, Telegram/SMS yuboradi (tasdiqdan keyin) |
| «Telegramda nima yangilik?» | o'qilmagan chatlarni o'qib beradi |
| «Bugun nima ishlarim bor?» | kunlik ro'yxatni aytadi |
| «Shu papkadagi kodni ko'r va testlarni ishga tushir» | o'qiydi, bajaradi, natijani aytadi |
| «Roshkaning Ishondingmi qo'shig'ini qo'y» | YouTube'dan topib, brauzerda qo'yadi |
| «Yigirmanchi sekunddan qo'y» | o'sha joydan boshlaydi |
| «YouTube sahifasini yop» | varaqni yopadi |
| «Bo'ldi, suhbatni yakunla» | xayrlashadi va HUD'ni yopadi |

## Keyingi bosqichlar

- [x] Uzluksiz suhbat rejimi — har safar «Hey Jarvis» demasdan davom ettirish
- [x] Jarvis gapirayotganda uni bo'lish (barge-in)
- [x] «Salom Jarvis» va «Hi Jarvis» bilan chaqirish (matn bilan tasdiqlash orqali)
- [ ] Tayyor o'zbekcha uyg'otuvchi so'z **modeli** repoda — tasdiqlash uchun
      STT chaqiruvi ham kerak bo'lmasin
- [ ] Brauzer boshqaruvi (Playwright)
- [ ] Kalendar integratsiyasi (Google Calendar / Apple Calendar)
- [ ] Supabase orqali xotirani qurilmalar o'rtasida sinxronlash
