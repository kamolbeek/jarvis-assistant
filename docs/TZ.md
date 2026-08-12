# Jarvis — texnik topshiriq

Nima qilingan, nima qolgan, va qanday tartibda qilinadi.

Bu hujjat ikki maqsad uchun: bir joyda butun manzarani ko'rish, va har bir
qadamning **nima uchun** shu tartibda ekanini yozib qo'yish. Tartib
tasodifiy emas — quyida har biriga sabab bor.

Holat belgilari: ✅ tayyor · ⏳ qisman · ❌ yo'q

---

## 0. Hozirgi holat

Postdagi 5 darajali o'lchov bo'yicha biz **L2.5** damiz: miya L3 darajasida
ishlaydi (o'zi reja tuzadi, asboblarni ishlatadi, 40 qadamgacha mustaqil
boradi), lekin uni faqat siz uyg'ota olasiz.

| Qism | Holat |
|---|---|
| Ovoz quvuri (uyg'otish → STT → miya → TTS) | ✅ |
| Uzluksiz suhbat, gapni bo'lish | ✅ |
| Ovozli tasdiq va ovozli buyruqlar | ✅ |
| Xotira, agenda, loyihalar | ✅ |
| Xavfsizlik darvozasi, audit | ✅ |
| HUD, orb, telefon sahifasi | ✅ |
| Telegram (chiqish), macOS, Shortcuts | ✅ |
| YouTube va media boshqaruvi | ✅ |
| Avtomatik ishga tushish | ✅ |
| Cron → **miya** | ❌ tayyor matnni aytadi, o'ylamaydi |
| Kiruvchi webhook | ❌ |
| Kalendar | ❌ |
| Telegram'dan **o'qish** | ❌ |
| Subagentlar, navbat | ❌ |

---

## 1-bosqich · O'zbek tili sifati

**Muammo.** Hozir ElevenLabs'ning inglizcha ovozi o'zbekcha matnni o'qiyapti —
model ko'p tilli, lekin ovoz ingliz talaffuziga o'rgatilgan. Natijada aksent.
Eshitishda ham ElevenLabs o'zbek tiliga ixtisoslashmagan.

**Yechim.** Eshitish va gapirishni alohida tanlaymiz:

| Qism | Provayder | Nega |
|---|---|---|
| Eshitish (STT) | **Mohir.ai** | o'zbek nutqiga ixtisoslashgan |
| Gapirish (TTS) | **Azure** `uz-UZ-MadinaNeural` | haqiqiy o'zbek neyron ovozi |

```yaml
voice:
  stt:
    provider: "mohir"
  tts:
    provider: "azure"
```

Kerak: `MOHIR_API_KEY`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`.
Azure'da bepul tarif bor (oyiga 500 ming belgi).

**Tekshirish.** Ikkalasini yonma-yon eshitib solishtirish kerak — qaysi biri
yaxshiroq bo'lsa, o'sha qoladi. Mohir TTS ham sinaladi.

**Ish hajmi.** Kod tayyor, faqat kalit va sozlama. ~1 soat, ko'p qismi
kalit olishga ketadi.

---

## 2-bosqich · Tezlik

**Muammo.** Eng katta kechikish miyada: `claude-opus-5` kuchli, lekin sekin.
«Musiqa qo'y» kabi oddiy buyruq uchun bu ortiqcha.

**Yechim.** Kundalik buyruqlar uchun Sonnet:

```yaml
brain:
  model: "claude-sonnet-5"
```

Keyinchalik: buyruq turiga qarab model tanlash (oddiy → Sonnet, murakkab →
Opus). Bu qo'shimcha mantiq talab qiladi, shuning uchun keyinroq.

**Ish hajmi.** Bir qator. Model tanlash mantig'i — ~60 qator.

---

## 3-bosqich · Kanallar va boshqaruv

Bularning har biri alohida asbob. Bir-biriga bog'liq emas, shuning uchun
istalgan tartibda qilinadi.

### 3.1 Telegram'ga ovoz bilan yozish ⏳

Hozir yozish bor, lekin faqat bitta manzilga (`TELEGRAM_CHAT_ID`).
Kerak: «Alisherga yoz, kechikaman de» — aloqalar bazasidan topib yuborish.

Aloqalar bazasi allaqachon bor (`save_contact`, `find_contact`), Telegram
uchun `chat_id` maydonini qo'shish kerak.

**Ish hajmi.** ~80 qator + testlar.

### 3.2 Telegram'dan o'qish ❌

«Guruhda nima gap?» — bu uchun bot xabarlarni o'qishi kerak.
`getUpdates` yoki webhook orqali.

**Ish hajmi.** ~120 qator. 4-bosqichdagi webhook bilan birga qilingani
ma'qul.

### 3.3 Brauzer boshqaruvi ⏳

YouTube tayyor. Kerak: umumiy brauzer boshqaruvi — sahifa ochish, matn
kiritish, tugma bosish. Playwright bilan.

**Ish hajmi.** ~150 qator. Ehtiyot bo'lish kerak: brauzerni boshqarish
xavfsizlik darvozasidan o'tishi shart.

### 3.4 Kalendar ❌

Google Calendar yoki Apple Calendar. Postdagi 6 tizimning 3 tasida
ishlatilgan va bizdagi eng katta bo'shliq.

**Ish hajmi.** ~200 qator + OAuth sozlash.

---

## 4-bosqich · Avtonomiya

Bu eng katta qism va **tartibi qat'iy**: xavfsizlik birinchi.

### 4.1 Avtonom xavfsizlik (C) — birinchi

**Nega birinchi.** Cron yoki webhook miyani uyg'otganda siz yoningizda
bo'lmasligingiz mumkin. Hozirgi `ask` qoidasi bunday holatda **osilib
qoladi**: tasdiq so'raladi, javob beradigan odam yo'q, 60 soniyadan keyin
rad etiladi. Ya'ni birinchi tungi vazifa jimgina muvaffaqiyatsiz tugaydi.

**Yechim.** `safety.autonomous` bo'limi:

```yaml
safety:
  autonomous:
    # Siz yo'q bo'lganingizda tasdiq kerak bo'lsa nima qilish kerak
    on_confirm: "telegram"     # telegram | deny | allow
    timeout_sec: 300
```

`telegram` — so'rov Telegram'ga yuboriladi, «ha» deb javob berilsa
bajariladi. Bu eng foydalisi: uydan tashqarida ham nazorat qoladi.

**Ish hajmi.** ~100 qator + testlar.

### 4.2 Cron → miya (A)

**Hozir:** rejalashtiruvchi tayyor matnni ovozga beradi, xolos.
**Kerak:** `Announcement` ga `prompt` maydoni; prompt bo'lsa, `_speak`
o'rniga `brain.ask()` chaqiriladi.

Shu bitta bog'lanish bilan «Kunlik puls» darhol ishlaydi — loyihalar
bazasi allaqachon bor.

**Ish hajmi.** ~50 qator.

### 4.3 Kiruvchi webhook (B)

`ui/server.py` ga `POST /hook`. Token allaqachon bor. Shundan keyin n8n,
Telegram va boshqa hamma narsa Jarvisni uyg'ota oladi.

**Ish hajmi.** ~60 qator.

---

## 5-bosqich · Uyg'otuvchi so'z modeli

«Salom Jarvis» hozir matn orqali tasdiqlanadi (STT chaqiruvi, ~0.5 s va
kichik to'lov). To'liq lokal qilish uchun o'z modelini o'rgatish kerak:
Colab'da bepul, ~30 daqiqa.

**Ish hajmi.** Foydalanuvchi ishtiroki kerak.

---

## Tavsiya etilgan tartib

1. **1-bosqich** (til) — har kuni sezasiz, eng kam ish
2. **2-bosqich** (tezlik) — bir qator
3. **3.1** (Telegram'ga yozish) — kundalik foyda
4. **4.1** (avtonom xavfsizlik) — poydevor
5. **4.2** (cron → miya) — eng katta foyda/kod nisbati
6. **3.4** (kalendar) — katta bo'shliq
7. **4.3** (webhook) va **3.2** (Telegram'dan o'qish)
8. **3.3** (brauzer), **5-bosqich**

**Qilinmaydi:** kontent konveyeri va lid yo'li — ular biznes
avtomatizatsiyasi tizimlari, shaxsiy yordamchining maqsadi emas.
