// Ish stoli HUD sahnasi — butun ekranni egallaydigan chizuvchi.
//
// Havoladagi Rainmeter uslubida: markazda zirh chizmasi (SUIT), orqasida
// aylanuvchi halqalar, chetlarda shesternyalar, o'ngda sariq ovoz datchigi
// va tizim o'lchagichi, chap pastda dumaloq JARVIS emblemasi.
//
// Bu fayl faqat chizadi — ma'lumotni (holat, ovoz darajasi, CPU/RAM)
// chaqiruvchi beradi. DOM elementlari (ilova tugmalari, ob-havo, soat)
// sahifaning o'zida, bu yerda faqat grafika.

const DESK = (() => {
  const TAU = Math.PI * 2;

  // ------------------------------------------------------------- o'rnatilgan rasm
  //
  // ui/renderer/assets/markaz.jpg (1920x1080, SHIELD OS wallpaperi) uchun
  // oldindan o'lchangan nuqtalar — rasmga nisbatan 0..1 koordinatalar.
  // Foydalanuvchi boshqa rasm tashlasa, bu qiymatlar ishlatilmaydi —
  // uch bosishli kalibrlash ishga tushadi.
  const BUNDLED = {
    cal: {
      eyeL: [0.476, 0.262],
      eyeR: [0.532, 0.262],
      core: [0.501, 0.713],
    },
    // Rasmdagi JARVIS doirasi — bosilsa siferblat paneli ochiladi
    emblem: { c: [0.193, 0.731], r: 0.078 },
    // Rasmdagi statik elementlar ustidagi bosiladigan maydonlar.
    // rect: [x, y, w, h] rasmga nisbatan; action turlari sahifada bajariladi.
    hotspots: [
      { rect: [0.058, 0.100, 0.082, 0.036], app: "Safari",          title: "Safari" },
      { rect: [0.058, 0.145, 0.082, 0.036], app: "System Settings", title: "Sozlamalar" },
      { rect: [0.058, 0.191, 0.082, 0.036], app: "Music",           title: "Musiqa" },
      { rect: [0.058, 0.235, 0.082, 0.036], app: "Safari",          title: "Safari" },
      { rect: [0.058, 0.280, 0.082, 0.036], app: "Finder",          title: "Finder" },
      { rect: [0.058, 0.325, 0.082, 0.036], app: "Messages",        title: "Xabarlar" },

      { rect: [0.385, 0.134, 0.055, 0.018], url: "https://google.com",    title: "Google" },
      { rect: [0.385, 0.151, 0.055, 0.018], url: "https://gmail.com",     title: "Gmail" },
      { rect: [0.385, 0.168, 0.055, 0.018], url: "https://facebook.com",  title: "Facebook" },
      { rect: [0.385, 0.184, 0.055, 0.018], url: "https://youtube.com",   title: "YouTube" },
      { rect: [0.385, 0.201, 0.055, 0.018], url: "https://imdb.com",      title: "IMDB" },
      { rect: [0.385, 0.298, 0.055, 0.018], url: "https://yahoo.com",     title: "Yahoo" },
      { rect: [0.385, 0.331, 0.055, 0.018], url: "https://wikipedia.org", title: "Wikipedia" },

      { rect: [0.752, 0.764, 0.057, 0.026], folder: "downloads", title: "Yuklamalar" },
      { rect: [0.767, 0.796, 0.057, 0.026], folder: "documents", title: "Hujjatlar" },
      { rect: [0.786, 0.826, 0.057, 0.026], folder: "music",     title: "Musiqa" },
      { rect: [0.828, 0.839, 0.057, 0.026], folder: "desktop",   title: "Ish stoli" },
      { rect: [0.901, 0.764, 0.057, 0.026], folder: "documents", title: "Hujjatlar" },
      { rect: [0.887, 0.795, 0.057, 0.026], folder: "pictures",  title: "Rasmlar" },
      { rect: [0.868, 0.826, 0.057, 0.026], folder: "videos",    title: "Videolar" },

      // Reaktor — bosilsa Jarvis uyg'onadi
      { circle: [0.501, 0.713, 0.055], activate: true, title: "Jarvis'ni chaqirish" },
    ],
  };

  const METER_SLOTS = 18; // ovoz datchigi segmentlari

  // Suzuvchi zarrachalar — butun ekran bo'ylab siyrak
  const MOTES = Array.from({ length: 42 }, () => ({
    x: Math.random(),
    y: Math.random(),
    drift: 0.004 + Math.random() * 0.01,
    phase: Math.random() * TAU,
    size: 0.5 + Math.random() * 1.3,
  }));

  let peakHold = 0; // datchik cho'qqi chizig'i sekin tushadi

  // ------------------------------------------------------------- fon

  function drawGrid(ctx, W, H) {
    const step = 48;
    ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.035);
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = step; x < W; x += step) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
    for (let y = step; y < H; y += step) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
    ctx.stroke();

    // Har to'rtinchi kesishmada kichik xoch — chizma qog'ozi hissi
    ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.08);
    ctx.beginPath();
    for (let x = step * 4; x < W; x += step * 4) {
      for (let y = step * 4; y < H; y += step * 4) {
        ctx.moveTo(x - 4, y); ctx.lineTo(x + 4, y);
        ctx.moveTo(x, y - 4); ctx.lineTo(x, y + 4);
      }
    }
    ctx.stroke();
  }

  function drawMotes(ctx, W, H, t) {
    for (const m of MOTES) {
      const y = (m.y + t * m.drift) % 1;
      const tw = 0.3 + 0.7 * Math.abs(Math.sin(t * 0.9 + m.phase));
      ctx.beginPath();
      ctx.arc(m.x * W, y * H, m.size, 0, TAU);
      ctx.fillStyle = P.toCss(P.RGB.cyan, 0.10 * tw);
      ctx.fill();
    }
  }

  // ------------------------------------------------------------- halqalar

  // Zirh orqasidagi katta aylanuvchi chizma halqalari
  function drawRings(ctx, cx, cy, R, t, energy) {
    // Belgili halqa
    const spin = t * 0.06;
    ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.22);
    ctx.lineWidth = 1;
    for (let i = 0; i < 90; i++) {
      const a = spin + (i / 90) * TAU;
      const major = i % 15 === 0;
      const r0 = R * (major ? 0.955 : 0.975);
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
      ctx.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, TAU);
    ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.18);
    ctx.stroke();

    // Uzuq ichki halqa — teskari aylanadi
    ctx.setLineDash([3, 9]);
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.88, -t * 0.1, -t * 0.1 + TAU);
    ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.16);
    ctx.stroke();
    ctx.setLineDash([]);

    // Qisman yoylar — energiya bilan yorqinlashadi
    for (const [k, from, sweep, speed, w] of [
      [1.06, 0.4, 1.3, 0.22, 2], [1.06, 3.6, 0.6, 0.22, 2],
      [0.80, 2.0, 1.8, -0.15, 2.6], [0.72, 5.0, 0.9, 0.3, 1.4],
    ]) {
      const a = from + t * speed;
      ctx.beginPath();
      ctx.arc(cx, cy, R * k, a, a + sweep);
      ctx.strokeStyle = P.toCss(P.RGB.cyan, (0.25 + energy * 0.3));
      ctx.lineWidth = w;
      ctx.stroke();
    }
  }

  // ------------------------------------------------------------- shesternya

  function drawGear(ctx, cx, cy, r, teeth, rot, alpha) {
    const toothH = r * 0.16;
    ctx.strokeStyle = P.toCss(P.RGB.cyan, alpha);
    ctx.lineWidth = 1.2;

    // Tishli tashqi kontur
    ctx.beginPath();
    for (let i = 0; i < teeth; i++) {
      const a0 = rot + (i / teeth) * TAU;
      const a1 = rot + ((i + 0.38) / teeth) * TAU;
      const a2 = rot + ((i + 0.5) / teeth) * TAU;
      const a3 = rot + ((i + 0.88) / teeth) * TAU;
      const R1 = r + toothH;
      if (i === 0) ctx.moveTo(cx + Math.cos(a0) * R1, cy + Math.sin(a0) * R1);
      ctx.arc(cx, cy, R1, a0, a1);
      ctx.lineTo(cx + Math.cos(a2) * r, cy + Math.sin(a2) * r);
      ctx.arc(cx, cy, r, a2, a3);
      ctx.lineTo(cx + Math.cos(rot + ((i + 1) / teeth) * TAU) * R1,
                 cy + Math.sin(rot + ((i + 1) / teeth) * TAU) * R1);
    }
    ctx.closePath();
    ctx.stroke();

    // Ichki halqa va kesmalar
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.62, 0, TAU);
    ctx.stroke();
    for (let i = 0; i < 5; i++) {
      const a = rot + (i / 5) * TAU;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r * 0.2, cy + Math.sin(a) * r * 0.2);
      ctx.lineTo(cx + Math.cos(a) * r * 0.62, cy + Math.sin(a) * r * 0.62);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.2, 0, TAU);
    ctx.stroke();
  }

  // Bir-biriga "tishlashgan" shesternyalar guruhi
  function drawGearCluster(ctx, x, y, t, scale, alpha) {
    drawGear(ctx, x, y, 56 * scale, 14, t * 0.3, alpha);
    drawGear(ctx, x + 74 * scale, y + 48 * scale, 32 * scale, 10, -t * 0.3 * (56 / 32) + 0.16, alpha * 0.8);
    drawGear(ctx, x - 52 * scale, y + 66 * scale, 24 * scale, 8, -t * 0.3 * (56 / 24) + 0.3, alpha * 0.65);
  }

  // ------------------------------------------------------------- ovoz datchigi

  // Sariq (zargaldoq) vertikal ustun — ovoz darajasiga qarab ko'tarilib tushadi
  function drawVoiceMeter(ctx, x, yTop, height, level, active, t, barW = 36) {
    const slotH = height / METER_SLOTS;
    const lit = Math.round(level * METER_SLOTS);

    peakHold = Math.max(peakHold - 0.006, level);

    for (let i = 0; i < METER_SLOTS; i++) {
      const y = yTop + height - (i + 1) * slotH;
      const on = i < lit && active;
      // Yuqori segmentlar qizg'ishroq — klassik daraja o'lchagich
      const hot = i / METER_SLOTS;
      const color = hot > 0.82 ? P.RGB.red : P.RGB.amber;
      ctx.fillStyle = P.toCss(color, on ? 0.5 + hot * 0.5 : 0.07);
      ctx.fillRect(x, y + 2, barW, slotH - 4);
      if (on) {
        ctx.shadowColor = P.toCss(color, 0.8);
        ctx.shadowBlur = 8;
        ctx.fillRect(x, y + 2, barW, slotH - 4);
        ctx.shadowBlur = 0;
      }
    }

    // Cho'qqi chizig'i
    if (active && peakHold > 0.02) {
      const py = yTop + height - peakHold * height;
      ctx.fillStyle = P.toCss(P.RGB.white, 0.85);
      ctx.fillRect(x, py, barW, 2);
    }

    // Ramka burchaklari
    ctx.strokeStyle = P.toCss(P.RGB.amber, 0.5);
    ctx.lineWidth = 1.4;
    for (const [bx, by, dx, dy] of [
      [x - 5, yTop - 5, 10, 0], [x - 5, yTop - 5, 0, 10],
      [x + barW + 5, yTop - 5, -10, 0], [x + barW + 5, yTop - 5, 0, 10],
      [x - 5, yTop + height + 5, 10, 0], [x - 5, yTop + height + 5, 0, -10],
      [x + barW + 5, yTop + height + 5, -10, 0], [x + barW + 5, yTop + height + 5, 0, -10],
    ]) {
      ctx.beginPath();
      ctx.moveTo(bx, by);
      ctx.lineTo(bx + dx, by + dy);
      ctx.stroke();
    }

    // Yozuv
    ctx.font = "700 10px ui-monospace, Menlo, monospace";
    ctx.textAlign = "center";
    ctx.fillStyle = P.toCss(P.RGB.amber, active ? 0.9 : 0.4);
    ctx.fillText("OVOZ", x + barW / 2, yTop + height + 24);
  }

  // ------------------------------------------------------------- tizim o'lchagichi

  // Dumaloq o'lchagich: CPU / RAM / DISK — uch konsentrik yoy
  function drawSystemGauge(ctx, cx, cy, r, stats, t) {
    const rows = [
      { key: "cpu", label: "CPU", color: P.RGB.cyan, k: 1.0 },
      { key: "ram", label: "RAM", color: P.RGB.amber, k: 0.78 },
      { key: "disk", label: "DISK", color: P.RGB.cyan, k: 0.56 },
    ];

    // Fon bo'linmalari
    ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.15);
    ctx.lineWidth = 1;
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * TAU;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * r * 1.06, cy + Math.sin(a) * r * 1.06);
      ctx.lineTo(cx + Math.cos(a) * r * 1.12, cy + Math.sin(a) * r * 1.12);
      ctx.stroke();
    }

    for (const row of rows) {
      const value = Math.max(0, Math.min(1, (stats && stats[row.key] || 0) / 100));
      const rr = r * row.k;
      // Fon yoyi
      ctx.beginPath();
      ctx.arc(cx, cy, rr, -Math.PI / 2, -Math.PI / 2 + TAU);
      ctx.strokeStyle = P.toCss(row.color, 0.12);
      ctx.lineWidth = 5;
      ctx.stroke();
      // Qiymat yoyi
      ctx.beginPath();
      ctx.arc(cx, cy, rr, -Math.PI / 2, -Math.PI / 2 + TAU * value);
      ctx.strokeStyle = P.toCss(row.color, 0.85);
      ctx.stroke();
    }

    // Markazda CPU foizi
    ctx.textAlign = "center";
    ctx.font = `700 ${Math.round(r * 0.42)}px ui-monospace, Menlo, monospace`;
    ctx.fillStyle = P.toCss(P.RGB.white, 0.9);
    ctx.fillText(`${Math.round(stats && stats.cpu || 0)}%`, cx, cy + r * 0.14);

    // Pastda yozuvlar
    ctx.font = "600 9.5px ui-monospace, Menlo, monospace";
    let ly = cy + r * 1.34;
    for (const row of rows) {
      const value = Math.round(stats && stats[row.key] || 0);
      ctx.fillStyle = P.toCss(row.color, 0.8);
      ctx.fillText(`${row.label} ${value}%`, cx, ly);
      ly += 15;
    }
  }

  // ------------------------------------------------------------- emblema

  // Chap pastdagi dumaloq JARVIS — bosilsa siferblat paneli ochiladi
  function drawEmblem(ctx, cx, cy, r, t, mark, hover) {
    // Nur
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 1.5);
    g.addColorStop(0, P.toCss(P.RGB.cyan, 0.2 * mark));
    g.addColorStop(1, P.toCss(P.RGB.cyan, 0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, r * 1.5, 0, TAU);
    ctx.fill();

    // Halqalar
    for (const [k, w, a] of [[1, 2, 0.9], [0.8, 1.2, 0.5], [0.62, 1.6, 0.75]]) {
      ctx.beginPath();
      ctx.arc(cx, cy, r * k, 0, TAU);
      ctx.strokeStyle = P.toCss(P.RGB.cyan, a * (hover ? 1.2 : 1) * mark);
      ctx.lineWidth = w;
      ctx.stroke();
    }

    // Aylanuvchi segmentlar
    for (let i = 0; i < 3; i++) {
      const a = t * 0.8 + (i / 3) * TAU;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 0.9, a, a + 1.1);
      ctx.strokeStyle = P.toCss(P.RGB.white, 0.35 * mark);
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }

    // Yozuv
    ctx.font = `800 ${Math.round(r * 0.30)}px ui-sans-serif, -apple-system, system-ui, sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.shadowColor = P.toCss(P.RGB.cyan, 0.9);
    ctx.shadowBlur = 12 * mark;
    ctx.fillStyle = P.toCss(P.RGB.white, 0.7 + 0.3 * mark);
    ctx.fillText("JARVIS", cx, cy);
    ctx.shadowBlur = 0;
    ctx.textBaseline = "alphabetic";
  }

  // ------------------------------------------------------------- joylashuv

  function layout(W, H) {
    const suitH = Math.min(H * 0.80, W * 0.55);
    return {
      suit: { cx: W * 0.5, topY: H * 0.5 - suitH * 0.52, height: suitH },
      emblem: { x: 118, y: H - 128, r: 62 },
      meter: { x: W - 108, yTop: H * 0.16, height: Math.min(240, H * 0.30) },
      gauge: { x: W - 150, y: H * 0.66, r: 54 },
      gearsTL: { x: 265, y: 138 },
      gearsR: { x: W - 305, y: H * 0.38 },
    };
  }

  /**
   * Bir kadr. f = { width, height, t, state, level, flash, boot, stats:{cpu,ram,disk} }
   *
   * `boot` — sahna qanchalik "yoniq" (0..1). Oyna ochilganda past bo'ladi:
   * hammasi ko'rinadi, lekin ko'zlar o'chgan va yorug'lik pasaygan — Jarvis
   * hali uyquda. Foydalanuvchi gapirganda 1 ga ko'tariladi.
   */
  function draw(ctx, f) {
    const { width: W, height: H, t } = f;
    const L = layout(W, H);
    ctx.clearRect(0, 0, W, H);

    const boot = f.boot === undefined ? 1 : Math.max(0, Math.min(1, f.boot));
    const mood = P.STATE_MOOD[f.state] || P.STATE_MOOD.idle;
    const active = f.state === "listening" || f.state === "speaking";
    const energy = Math.min(1, mood.glow + f.flash * 0.5) * (0.28 + 0.72 * boot);

    // Ko'zlar: kutishda xira, uyg'onganda chaqnaydi, o'ylashda sekin pulsatsiya.
    // Uyqu holatida butunlay o'chadi — bu eng ko'zga tashlanadigan belgi.
    let eyes = 0.25 + mood.glow * 0.5 + f.flash * 0.6;
    if (f.state === "thinking") eyes = 0.45 + Math.abs(Math.sin(t * 2.2)) * 0.3;
    eyes = Math.min(1, eyes) * boot * boot;

    // Rasm rejimida to'r chizilmaydi — foydalanuvchi rasmi o'zi to'liq fon
    if (!f.figure) drawGrid(ctx, W, H);
    drawMotes(ctx, W, H, t);

    // Markaz: foydalanuvchi rasmi bo'lsa, vektor zirh chizilmaydi —
    // rasm DOM'da turadi, jonli effektlar esa fx qatlamida.
    if (!f.figure) {
      const anchor = SUIT.reactorAt(L.suit);
      drawRings(ctx, anchor.x, anchor.y, L.suit.height * 0.46, t, energy);
    }

    // Shesternyalar
    drawGearCluster(ctx, L.gearsTL.x, L.gearsTL.y, t, 0.8, 0.3);
    drawGearCluster(ctx, L.gearsR.x, L.gearsR.y, t, 1.0, 0.35);

    if (!f.figure) {
      SUIT.draw(ctx, {
        cx: L.suit.cx, topY: L.suit.topY, height: L.suit.height,
        t, eyes, surge: Math.min(1, mood.core * 0.6 + f.flash + f.level * 0.6),
      });

      // Zirh pastini fonga singdirish
      const fade = ctx.createLinearGradient(0, L.suit.topY + L.suit.height * 0.82, 0, L.suit.topY + L.suit.height);
      fade.addColorStop(0, "rgba(3, 8, 12, 0)");
      fade.addColorStop(1, "rgba(3, 8, 12, 0.95)");
      ctx.fillStyle = fade;
      ctx.fillRect(L.suit.cx - L.suit.height, L.suit.topY + L.suit.height * 0.8,
                   L.suit.height * 2, L.suit.height * 0.22);
    }

    if (f.figureRect && f.figure) {
      // Rasm rejimi: datchik rasm o'ng chetidagi shkala ustida
      const r = f.figureRect;
      drawVoiceMeter(ctx, r.x + r.w * 0.972, r.y + r.h * 0.50, r.h * 0.28,
                     f.level, active, t, Math.max(10, r.w * 0.014));
    } else {
      drawVoiceMeter(ctx, L.meter.x, L.meter.yTop, L.meter.height, f.level, active, t);
      drawSystemGauge(ctx, L.gauge.x, L.gauge.y, L.gauge.r, f.stats, t);
      drawEmblem(ctx, L.emblem.x, L.emblem.y, L.emblem.r, t,
                 0.55 + mood.mark * 0.45, f.emblemHover);
    }

    const surge = Math.min(1, mood.core * 0.6 + f.flash + f.level * 0.6) * boot;
    drawVeil(ctx, W, H, boot, t);
    return { eyes, surge };
  }

  // Uyqu pardasi. Canvas fon rasmining ustida turadi, shuning uchun bitta
  // to'rtburchak butun sahnani birdan xiralashtiradi — CSS filtri bilan har
  // kadrda qayta bo'yashdan ancha arzon.
  function drawVeil(ctx, W, H, boot, t) {
    if (boot > 0.995) return;
    const dark = (1 - boot) * 0.7;
    ctx.save();
    ctx.fillStyle = `rgba(2, 7, 11, ${dark.toFixed(3)})`;
    ctx.fillRect(0, 0, W, H);

    // Yoqilish chizig'i: boot ko'tarilayotganda ekran bo'ylab pastga yuguradi.
    // Faqat o'tish davrida ko'rinadi — uyquda ham, to'liq yoniqda ham yo'q.
    const wake = 1 - Math.abs(boot * 2 - 1);
    if (wake > 0.05) {
      const y = H * (0.5 - Math.cos(t * 1.6) * 0.5);
      const g = ctx.createLinearGradient(0, y - 60, 0, y + 60);
      g.addColorStop(0, P.toCss(P.RGB.cyan, 0));
      g.addColorStop(0.5, P.toCss(P.RGB.cyan, 0.10 * wake));
      g.addColorStop(1, P.toCss(P.RGB.cyan, 0));
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = g;
      ctx.fillRect(0, y - 60, W, 120);
    }
    ctx.restore();
  }

  // ------------------------------------------------------------- rasm effektlari

  // Foydalanuvchi rasmi ustidagi jonli qatlam: ko'zlar nuri va reaktor.
  // Nuqtalar kalibrlashda belgilanadi (rasmga nisbatan 0..1 koordinatalar).
  function drawFigureFx(ctx, rect, cal, t, eyes, surge, boot) {
    if (!cal) return;
    const px = (p) => [rect.x + p[0] * rect.w, rect.y + p[1] * rect.h];

    // Uyquda ko'zlar va reaktor O'CHGAN bo'lishi kerak. Muammo shundaki,
    // ular fon rasmining o'zida yoniq holda chizilgan — ustiga qorayituvchi
    // niqob qo'yamiz, keyin nurni qaytadan chizamiz. Natijada yonish
    // haqiqatan yonishga o'xshaydi, shunchaki yorqinlik oshishiga emas.
    const lit = boot === undefined ? 1 : Math.max(0, Math.min(1, boot));
    if (lit < 0.99) {
      // Ko'zlar butunlay o'chadi; reaktor esa faqat pasayadi — uni ham
      // to'liq bo'yasak, chizmadagi halqalar yo'qolib, dog' bo'lib qoladi.
      ctx.save();
      for (const [key, scale, strength] of
           [["eyeL", 1.6, 0.92], ["eyeR", 1.6, 0.92], ["core", 2.4, 0.6]]) {
        if (!cal[key]) continue;
        const mask = (1 - lit) * strength;
        const [x, y] = px(cal[key]);
        const r = rect.w * 0.030 * scale;
        const g = ctx.createRadialGradient(x, y, 0, x, y, r);
        g.addColorStop(0, `rgba(3, 8, 12, ${mask.toFixed(3)})`);
        g.addColorStop(0.6, `rgba(3, 8, 12, ${(mask * 0.75).toFixed(3)})`);
        g.addColorStop(1, "rgba(3, 8, 12, 0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, TAU);
        ctx.fill();
      }
      ctx.restore();
    }

    ctx.save();
    // Qo'shiluvchi aralashtirish — qora rasm ustida faqat nur ko'rinadi
    ctx.globalCompositeOperation = "lighter";

    // Ko'zlar: pulslanadigan nur
    const eyeR = rect.w * 0.030;
    for (const key of ["eyeL", "eyeR"]) {
      if (!cal[key]) continue;
      const [x, y] = px(cal[key]);
      const g = ctx.createRadialGradient(x, y, 0, x, y, eyeR * (1 + eyes));
      g.addColorStop(0, P.toCss(P.RGB.white, 0.55 * eyes + 0.1));
      g.addColorStop(0.4, P.toCss(P.RGB.cyan, 0.4 * eyes + 0.06));
      g.addColorStop(1, P.toCss(P.RGB.cyan, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, eyeR * (1 + eyes) + 1, 0, TAU);
      ctx.fill();
    }

    // Reaktor: nur + aylanuvchi segmentlar
    if (cal.core) {
      const [x, y] = px(cal.core);
      const r = rect.w * 0.055;
      const g = ctx.createRadialGradient(x, y, 0, x, y, r * 2);
      g.addColorStop(0, P.toCss(P.RGB.white, 0.35 + surge * 0.4));
      g.addColorStop(0.5, P.toCss(P.RGB.cyan, 0.15 + surge * 0.2));
      g.addColorStop(1, P.toCss(P.RGB.cyan, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, r * 2, 0, TAU);
      ctx.fill();

      const spin = t * (0.6 + surge * 1.8);
      ctx.lineWidth = 2.5;
      for (let i = 0; i < 8; i++) {
        const a = spin + (i / 8) * TAU;
        ctx.beginPath();
        ctx.arc(x, y, r, a, a + 0.45);
        ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.35 + surge * 0.45);
        ctx.stroke();
      }
      // Teskari aylanuvchi tashqi halqa
      ctx.lineWidth = 1.4;
      for (let i = 0; i < 4; i++) {
        const a = -spin * 0.6 + (i / 4) * TAU;
        ctx.beginPath();
        ctx.arc(x, y, r * 1.45, a, a + 0.7);
        ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.22 + surge * 0.3);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // Rasmdagi JARVIS doirasi ustiga jonli halqa — bosish mumkinligini bildiradi
  function drawEmblemPulse(ctx, rect, emblem, t, mark) {
    const x = rect.x + emblem.c[0] * rect.w;
    const y = rect.y + emblem.c[1] * rect.h;
    const r = emblem.r * rect.w * 0.5;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (let i = 0; i < 3; i++) {
      const a = t * 0.8 + (i / 3) * TAU;
      ctx.beginPath();
      ctx.arc(x, y, r, a, a + 1.0);
      ctx.strokeStyle = P.toCss(P.RGB.cyan, 0.25 + mark * 0.3);
      ctx.lineWidth = 2.2;
      ctx.stroke();
    }
    ctx.restore();
  }

  // Emblema ustiga bosilganini aniqlash
  function hit(W, H, x, y) {
    const L = layout(W, H);
    const dx = x - L.emblem.x;
    const dy = y - L.emblem.y;
    if (dx * dx + dy * dy <= (L.emblem.r * 1.15) ** 2) return "emblem";
    return null;
  }

  return { draw, hit, layout, drawFigureFx, drawEmblemPulse, BUNDLED };
})();

if (typeof module !== "undefined") module.exports = DESK;
