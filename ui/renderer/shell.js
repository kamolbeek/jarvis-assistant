// SHIELD OS — butun ish stolining JONLI chizmasi.
//
// Havoladagi Rainmeter wallpaperi rasm edi: chiroyli, lekin o'lik. Bu fayl
// o'sha kompozitsiyani qaytadan chizadi — endi har bir detal haqiqiy:
// soat haqiqiy vaqtni, CPU/RAM/SWAP haqiqiy yukni, disk panellari haqiqiy
// hajmni, batareya haqiqiy zaryadni ko'rsatadi; tugmalar bosiladi, halqalar
// aylanadi, ovoz darajasi mikrofondan keladi.
//
// Chizma 1920x1080 "virtual" maydonda ishlaydi va ekranga proporsional
// joylashtiriladi — shu tufayli joylashuv har qanday o'lchamda bir xil.
// Bosiladigan maydonlar har kadrda `zones` ro'yxatiga yig'iladi, `hit()`
// esa ekran koordinatasini virtualga o'girib, o'sha ro'yxatdan qidiradi.
//
// Bu fayl faqat CHIZADI va nima bosilganini aytadi. Ilova ochish, ovozni
// o'zgartirish kabi ishlarni chaqiruvchi bajaradi.

const SHELL = (() => {
  const VW = 1920;
  const VH = 1080;
  const TAU = Math.PI * 2;
  const MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, monospace';

  const cy = (a) => P.toCss(P.RGB.cyan, a);
  const wh = (a) => P.toCss(P.RGB.white, a);
  const am = (a) => P.toCss(P.RGB.amber, a);
  const rd = (a) => P.toCss(P.RGB.red, a);

  // ---------------------------------------------------------------- holat
  //
  // Grafiklar uchun tarix shu yerda saqlanadi: chaqiruvchi faqat yangi
  // o'lchovni uzatadi, egri chiziqni biz eslab qolamiz.
  const HISTORY = 90;
  const history = { cpu: [], ram: [], net: [] };

  function pushStats(s) {
    const add = (key, value) => {
      const arr = history[key];
      arr.push(Math.max(0, Math.min(1, value || 0)));
      if (arr.length > HISTORY) arr.shift();
    };
    add("cpu", (s.cpu || 0) / 100);
    add("ram", (s.ram || 0) / 100);
    // Tarmoq — 5 MB/s ni to'liq shkala deb olamiz, aks holda grafik ko'rinmaydi
    add("net", Math.min(1, ((s.net && s.net.down) || 0) / 5e6));
  }

  // Har kadrda qaytadan yig'iladigan bosiladigan maydonlar
  let zones = [];
  let view = { s: 1, dx: 0, dy: 0 };

  function zoneRect(kind, id, x, y, w, h, title) {
    zones.push({ kind, id, title, x, y, w, h });
  }

  function zoneCircle(kind, id, x, y, r, title) {
    zones.push({ kind, id, title, cx: x, cy: y, r });
  }

  // ---------------------------------------------------------------- asboblar

  function text(ctx, str, x, y, o = {}) {
    const size = o.size || 12;
    const weight = o.weight || 600;
    ctx.font = `${weight} ${size}px ${o.font || MONO}`;
    ctx.textAlign = o.align || "left";
    ctx.textBaseline = o.baseline || "alphabetic";
    if ("letterSpacing" in ctx) ctx.letterSpacing = `${o.spacing || 0}px`;
    if (o.glow) {
      ctx.shadowColor = o.color || cy(1);
      ctx.shadowBlur = o.glow;
    }
    ctx.fillStyle = o.color || cy(0.8);
    ctx.fillText(str, x, y);
    ctx.shadowBlur = 0;
    if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";
  }

  function measure(ctx, str, size, weight = 600, spacing = 0) {
    ctx.font = `${weight} ${size}px ${MONO}`;
    if ("letterSpacing" in ctx) ctx.letterSpacing = `${spacing}px`;
    const w = ctx.measureText(str).width;
    if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";
    return w;
  }

  // Burchagi kesilgan panel — HUD'ning asosiy "quti" shakli
  function panel(ctx, x, y, w, h, o = {}) {
    const c = o.cut === undefined ? 12 : o.cut;
    ctx.beginPath();
    ctx.moveTo(x + c, y);
    ctx.lineTo(x + w, y);
    ctx.lineTo(x + w, y + h - c);
    ctx.lineTo(x + w - c, y + h);
    ctx.lineTo(x, y + h);
    ctx.lineTo(x, y + c);
    ctx.closePath();
    ctx.fillStyle = o.fill || "rgba(4, 12, 18, 0.72)";
    ctx.fill();
    ctx.strokeStyle = o.stroke || cy(0.22);
    ctx.lineWidth = o.width || 1;
    ctx.stroke();
    if (o.title) {
      text(ctx, o.title, x + 10, y + 15, { size: 10, spacing: 2.2, color: cy(0.65) });
      ctx.beginPath();
      ctx.moveTo(x + 8, y + 22);
      ctx.lineTo(x + w - 8, y + 22);
      ctx.strokeStyle = cy(0.16);
      ctx.stroke();
    }
  }

  // Gorizontal ko'rsatkich chizig'i
  function bar(ctx, x, y, w, h, value, color, o = {}) {
    const v = Math.max(0, Math.min(1, value || 0));
    ctx.fillStyle = P.toCss(color, 0.12);
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = P.toCss(color, 0.85);
    ctx.fillRect(x, y, w * v, h);
    if (!o.flat) {
      ctx.shadowColor = P.toCss(color, 0.8);
      ctx.shadowBlur = 6;
      ctx.fillRect(x, y, w * v, h);
      ctx.shadowBlur = 0;
    }
    // Bo'linmalar — o'lchagich hissi
    ctx.strokeStyle = "rgba(3, 10, 15, 0.9)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 1; i < (o.ticks || 12); i++) {
      const tx = Math.round(x + (w / (o.ticks || 12)) * i) + 0.5;
      ctx.moveTo(tx, y);
      ctx.lineTo(tx, y + h);
    }
    ctx.stroke();
  }

  // Nomi + foizi bo'lgan qator (SYSTEM panelidagi kabi)
  function meterRow(ctx, x, y, w, label, value, color, right) {
    text(ctx, label, x, y, { size: 11, color: wh(0.72) });
    text(ctx, right, x + w, y, { size: 11, align: "right", color: P.toCss(color, 0.95) });
    bar(ctx, x, y + 5, w, 4, value, color);
  }

  // Aylanuvchi texnik siferblat — chizmadagi "dumaloq narsalar"
  function dial(ctx, cx, cyy, r, t, o = {}) {
    const spin = t * (o.speed || 0.25);
    const a = o.alpha === undefined ? 1 : o.alpha;

    ctx.strokeStyle = cy(0.30 * a);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cyy, r, 0, TAU);
    ctx.stroke();

    // Tashqi bo'linmalar
    ctx.strokeStyle = cy(0.22 * a);
    ctx.beginPath();
    for (let i = 0; i < 72; i++) {
      const ang = spin + (i / 72) * TAU;
      const long = i % 6 === 0;
      const r0 = r * (long ? 0.88 : 0.94);
      ctx.moveTo(cx + Math.cos(ang) * r0, cyy + Math.sin(ang) * r0);
      ctx.lineTo(cx + Math.cos(ang) * r, cyy + Math.sin(ang) * r);
    }
    ctx.stroke();

    // Teskari aylanuvchi uzuq halqa
    ctx.setLineDash([4, 10]);
    ctx.beginPath();
    ctx.arc(cx, cyy, r * 0.78, -spin * 1.6, -spin * 1.6 + TAU);
    ctx.strokeStyle = cy(0.26 * a);
    ctx.stroke();
    ctx.setLineDash([]);

    // Qiymat yoyi — o'lchov (0..1) bo'lsa, uni ko'rsatadi
    if (o.value !== undefined) {
      ctx.beginPath();
      ctx.arc(cx, cyy, r * 0.64, -Math.PI / 2, -Math.PI / 2 + TAU * Math.max(0, Math.min(1, o.value)));
      ctx.strokeStyle = P.toCss(o.color || P.RGB.cyan, 0.9 * a);
      ctx.lineWidth = 4;
      ctx.stroke();
      ctx.lineWidth = 1;
    }

    // Ichki yoylar
    for (const [k, from, sweep, sp] of [[0.52, 0.4, 1.6, 0.9], [0.52, 3.4, 1.1, 0.9], [0.38, 2.0, 2.4, -1.3]]) {
      const ang = from + t * sp * (o.speed === undefined ? 1 : o.speed * 4);
      ctx.beginPath();
      ctx.arc(cx, cyy, r * k, ang, ang + sweep);
      ctx.strokeStyle = cy(0.4 * a);
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.lineWidth = 1;

    // Markaziy yozuv
    if (o.label) {
      text(ctx, o.label, cx, cyy + 4, { size: r * 0.30, align: "center", color: wh(0.9 * a), glow: 8 });
    }
    if (o.sub) {
      text(ctx, o.sub, cx, cyy + r * 0.42, { size: r * 0.16, align: "center", color: cy(0.7 * a), spacing: 1.5 });
    }
  }

  function gear(ctx, cx, cyy, r, teeth, rot, alpha) {
    const th = r * 0.18;
    ctx.strokeStyle = cy(alpha);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < teeth; i++) {
      const a0 = rot + (i / teeth) * TAU;
      const a1 = rot + ((i + 0.4) / teeth) * TAU;
      const a2 = rot + ((i + 0.5) / teeth) * TAU;
      const a3 = rot + ((i + 0.9) / teeth) * TAU;
      const R1 = r + th;
      if (i === 0) ctx.moveTo(cx + Math.cos(a0) * R1, cyy + Math.sin(a0) * R1);
      ctx.arc(cx, cyy, R1, a0, a1);
      ctx.lineTo(cx + Math.cos(a2) * r, cyy + Math.sin(a2) * r);
      ctx.arc(cx, cyy, r, a2, a3);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cyy, r * 0.55, 0, TAU);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cyy, r * 0.18, 0, TAU);
    ctx.stroke();
  }

  // Olti burchakli katak to'ri (chap pastdagi kabi)
  function hexField(ctx, x, y, cols, rows, size, t) {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const hx = x + c * size * 1.74 + (r % 2 ? size * 0.87 : 0);
        const hy = y + r * size * 1.5;
        const pulse = 0.10 + 0.16 * Math.abs(Math.sin(t * 0.8 + c * 0.7 + r * 1.3));
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const a = (i / 6) * TAU + Math.PI / 6;
          const px = hx + Math.cos(a) * size;
          const py = hy + Math.sin(a) * size;
          if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.strokeStyle = cy(pulse);
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
  }

  // Burchagi qiyshaygan tugma — chap paneldagi ilova tugmalari
  function chip(ctx, x, y, w, h, label, hot, color) {
    const c = P.RGB[color || "amber"];
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + w - h * 0.45, y);
    ctx.lineTo(x + w, y + h / 2);
    ctx.lineTo(x + w - h * 0.45, y + h);
    ctx.lineTo(x, y + h);
    ctx.closePath();
    const g = ctx.createLinearGradient(x, y, x + w, y);
    g.addColorStop(0, hot ? cy(0.35) : "rgba(42, 53, 64, 0.85)");
    g.addColorStop(1, "rgba(42, 53, 64, 0.20)");
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = hot ? cy(0.9) : cy(0.20);
    ctx.lineWidth = 1;
    ctx.stroke();
    // Chap chekkadagi rangli chiziq
    ctx.fillStyle = P.toCss(hot ? P.RGB.cyan : c, 0.95);
    ctx.fillRect(x, y, 3, h);
    text(ctx, label, x + 14, y + h / 2 + 4, {
      size: 12, color: hot ? wh(1) : wh(0.78), spacing: 1.2,
    });
  }

  // Kichik "+" belgili burchak ramkasi
  function corners(ctx, x, y, w, h, len, color) {
    ctx.strokeStyle = color || cy(0.5);
    ctx.lineWidth = 1.4;
    const seg = [
      [x, y, len, 0], [x, y, 0, len],
      [x + w, y, -len, 0], [x + w, y, 0, len],
      [x, y + h, len, 0], [x, y + h, 0, -len],
      [x + w, y + h, -len, 0], [x + w, y + h, 0, -len],
    ];
    ctx.beginPath();
    for (const [sx, sy, dx, dy] of seg) {
      ctx.moveTo(sx, sy);
      ctx.lineTo(sx + dx, sy + dy);
    }
    ctx.stroke();
  }

  // Grafik (tarix egri chizig'i)
  function graph(ctx, x, y, w, h, data, color) {
    ctx.strokeStyle = P.toCss(color, 0.18);
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 4; i++) {
      const gy = y + (h / 4) * i;
      ctx.moveTo(x, gy);
      ctx.lineTo(x + w, gy);
    }
    ctx.stroke();
    if (!data.length) return;
    // Yangi o'lchov o'ng chetda: grafik jonli monitor kabi chapga suriladi
    const stepX = w / Math.max(1, HISTORY - 1);
    const first = x + w - (data.length - 1) * stepX;
    ctx.beginPath();
    data.forEach((v, i) => {
      const px = first + i * stepX;
      const py = y + h - v * h;
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.strokeStyle = P.toCss(color, 0.9);
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.lineTo(x + w, y + h);
    ctx.lineTo(first, y + h);
    ctx.closePath();
    ctx.fillStyle = P.toCss(color, 0.12);
    ctx.fill();
  }

  const GB = (n) => (n === null || n === undefined ? "—" : `${n >= 100 ? Math.round(n) : n.toFixed(1)} GB`);
  const RATE = (bps) => {
    if (!bps) return "0 B/s";
    if (bps > 1e6) return `${(bps / 1e6).toFixed(1)} MB/s`;
    if (bps > 1e3) return `${Math.round(bps / 1e3)} KB/s`;
    return `${Math.round(bps)} B/s`;
  };
  const pad = (n) => String(n).padStart(2, "0");

  const WEEK_UZ = ["YAKSHANBA", "DUSHANBA", "SESHANBA", "CHORSHANBA", "PAYSHANBA", "JUMA", "SHANBA"];
  const WEEK_SHORT = ["Ya", "Du", "Se", "Ch", "Pa", "Ju", "Sh"];
  const MONTH_UZ = ["YANVAR", "FEVRAL", "MART", "APREL", "MAY", "IYUN",
                    "IYUL", "AVGUST", "SENTABR", "OKTABR", "NOYABR", "DEKABR"];

  // ============================================================== vidjetlar
  //
  // Har biri virtual (1920x1080) koordinatalarda chizadi. Bosiladiganlari
  // o'zi `zoneRect`/`zoneCircle` bilan maydonini e'lon qiladi.

  // ---------------------------------------------------------- SHIELD emblemasi
  function drawShield(ctx, x, y, r, t) {
    ctx.save();
    ctx.translate(x, y);
    // Sariq halqa
    const g = ctx.createRadialGradient(0, 0, r * 0.2, 0, 0, r);
    g.addColorStop(0, "rgba(255, 178, 62, 0.20)");
    g.addColorStop(1, "rgba(255, 178, 62, 0.02)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, TAU);
    ctx.fill();

    ctx.strokeStyle = am(0.75);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, TAU);
    ctx.stroke();
    ctx.strokeStyle = am(0.4);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.82, 0, TAU);
    ctx.stroke();

    // Sekin aylanuvchi bo'linmalar
    ctx.rotate(t * 0.12);
    ctx.strokeStyle = am(0.5);
    ctx.beginPath();
    for (let i = 0; i < 16; i++) {
      const a = (i / 16) * TAU;
      ctx.moveTo(Math.cos(a) * r * 0.84, Math.sin(a) * r * 0.84);
      ctx.lineTo(Math.cos(a) * r * 0.94, Math.sin(a) * r * 0.94);
    }
    ctx.stroke();
    ctx.rotate(-t * 0.12);

    // Burgut silueti — soddalashtirilgan belgi
    ctx.fillStyle = am(0.85);
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.46);
    ctx.lineTo(r * 0.30, -r * 0.16);
    ctx.lineTo(r * 0.14, -r * 0.16);
    ctx.lineTo(r * 0.40, r * 0.16);
    ctx.lineTo(0, r * 0.50);
    ctx.lineTo(-r * 0.40, r * 0.16);
    ctx.lineTo(-r * 0.14, -r * 0.16);
    ctx.lineTo(-r * 0.30, -r * 0.16);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  // ---------------------------------------------------------- shaxsiy kartochka
  function drawIdentity(ctx, x, y, w, h, sys, t) {
    panel(ctx, x, y, w, h, { cut: 10 });
    text(ctx, "SHIELD OS", x + 12, y + 20, { size: 13, color: cy(0.9), spacing: 3, glow: 8 });
    text(ctx, (sys.user || "operator").toUpperCase(), x + 12, y + 40, { size: 11, color: wh(0.8), spacing: 1.4 });
    text(ctx, (sys.host || "localhost").toUpperCase(), x + 12, y + 56, { size: 10, color: cy(0.55), spacing: 1.2 });

    // Ish vaqti
    const up = sys.uptimeSec || 0;
    const days = Math.floor(up / 86400);
    const hrs = Math.floor((up % 86400) / 3600);
    const mins = Math.floor((up % 3600) / 60);
    text(ctx, `UPTIME ${days ? days + "k " : ""}${pad(hrs)}:${pad(mins)}`,
         x + w - 12, y + 56, { size: 10, align: "right", color: wh(0.45), spacing: 1 });

    // Jonli nuqta — tizim ishlayotganini bildiradi
    const blink = 0.4 + 0.6 * Math.abs(Math.sin(t * 2));
    ctx.fillStyle = cy(blink);
    ctx.beginPath();
    ctx.arc(x + w - 16, y + 18, 4, 0, TAU);
    ctx.fill();
  }

  // ---------------------------------------------------------- chapdagi ilovalar
  const APPS = [
    { app: "Safari", label: "SAFARI" },
    { app: "Finder", label: "FINDER" },
    { app: "Terminal", label: "TERMINAL" },
    { app: "Music", label: "MUSIQA" },
    { app: "Messages", label: "XABARLAR" },
    { app: "System Settings", label: "SOZLAMALAR" },
  ];

  function drawAppRail(ctx, x, y, hover) {
    text(ctx, "ILOVALAR", x, y - 10, { size: 10, color: cy(0.5), spacing: 3 });
    APPS.forEach((a, i) => {
      const cyPos = y + i * 46;
      const hot = hover && hover.kind === "app" && hover.id === a.app;
      chip(ctx, x, cyPos, 186, 36, a.label, hot);
      zoneRect("app", a.app, x, cyPos, 186, 36, a.label);
    });
  }

  // ---------------------------------------------------------- tizim panellari
  function drawSystemPanel(ctx, x, y, w, sys) {
    const h = 150;
    panel(ctx, x, y, w, h, { title: "SYSTEM" });
    const ix = x + 12;
    const iw = w - 24;
    meterRow(ctx, ix, y + 46, iw, "CPU", (sys.cpu || 0) / 100,
             P.RGB.cyan, `${Math.round(sys.cpu || 0)}%`);
    meterRow(ctx, ix, y + 82, iw, "RAM", (sys.ram || 0) / 100,
             P.RGB.amber, `${Math.round(sys.ram || 0)}%`);
    meterRow(ctx, ix, y + 118, iw, "SWAP", (sys.swap || 0) / 100,
             (sys.swap || 0) > 70 ? P.RGB.red : P.RGB.cyan, `${Math.round(sys.swap || 0)}%`);
  }

  function drawRamGauge(ctx, x, y, sys, t) {
    text(ctx, "RAM USAGE", x, y, { size: 11, color: cy(0.6), spacing: 3 });
    text(ctx, `${Math.round(sys.ram || 0)}%`, x, y + 42,
         { size: 40, weight: 700, color: wh(0.92), glow: 12 });
    const used = sys.ramUsedGb;
    const total = sys.ramTotalGb;
    text(ctx, `BAND ${GB(used)}`, x, y + 62, { size: 10, color: cy(0.6), spacing: 1 });
    text(ctx, `BO'SH ${GB(total !== undefined && used !== undefined ? total - used : undefined)}`,
         x, y + 78, { size: 10, color: cy(0.45), spacing: 1 });
    // Ikkita kichik aylanuvchi disk
    dial(ctx, x + 128, y + 26, 15, t, { speed: 0.7, alpha: 0.7 });
    dial(ctx, x + 162, y + 26, 15, -t, { speed: 0.5, alpha: 0.5 });
  }

  function drawDrivePanel(ctx, x, y, w, sys) {
    const disks = (sys.disks || []).slice(0, 3);
    const h = 34 + Math.max(1, disks.length) * 28;
    panel(ctx, x, y, w, h, { title: "DRIVE" });
    if (!disks.length) {
      text(ctx, "o'lchanmoqda…", x + 12, y + 48, { size: 10, color: wh(0.35) });
      return;
    }
    disks.forEach((d, i) => {
      const ry = y + 44 + i * 28;
      text(ctx, d.name, x + 12, ry, { size: 10, color: wh(0.7) });
      text(ctx, `${Math.round(d.percent)}%`, x + w - 12, ry,
           { size: 10, align: "right", color: d.percent > 90 ? rd(0.9) : cy(0.85) });
      bar(ctx, x + 12, ry + 5, w - 24, 4, d.percent / 100,
          d.percent > 90 ? P.RGB.red : P.RGB.cyan, { ticks: 20 });
    });
  }

  // ---------------------------------------------------------- JARVIS emblemasi
  //
  // Chap pastdagi katta doira. Ovoz darajasi halqani "nafas oldiradi",
  // bosilsa — bo'g'inlar paneli ochiladi.
  function drawJarvisEmblem(ctx, x, y, r, t, level, mood, hover) {
    const glow = 0.35 + mood.glow * 0.5;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r * 1.6);
    g.addColorStop(0, cy(0.16 * glow));
    g.addColorStop(1, cy(0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, r * 1.6, 0, TAU);
    ctx.fill();

    // Ovoz darajasiga qarab kengayadigan halqa
    const pulse = r * (0.92 + level * 0.10);
    for (const [k, w, a] of [[1, 2.4, 0.85], [0.86, 1.2, 0.4], [0.66, 1.8, 0.6]]) {
      ctx.beginPath();
      ctx.arc(x, y, r * k, 0, TAU);
      ctx.strokeStyle = cy(a * glow * (hover ? 1.35 : 1));
      ctx.lineWidth = w;
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(x, y, pulse, 0, TAU);
    ctx.strokeStyle = wh(0.25 + level * 0.5);
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Aylanuvchi segmentlar
    for (let i = 0; i < 3; i++) {
      const a = t * (0.5 + mood.spin * 0.5) + (i / 3) * TAU;
      ctx.beginPath();
      ctx.arc(x, y, r * 0.98, a, a + 0.9);
      ctx.strokeStyle = wh(0.35 * glow);
      ctx.lineWidth = 3;
      ctx.stroke();
    }

    // Ovoz spektri — doira ichida
    const bars = 32;
    for (let i = 0; i < bars; i++) {
      const a = (i / bars) * TAU - Math.PI / 2;
      const seed = Math.abs(Math.sin(i * 12.9898 + t * 3));
      const amp = level * seed * r * 0.28;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * r * 0.36, y + Math.sin(a) * r * 0.36);
      ctx.lineTo(x + Math.cos(a) * (r * 0.36 + amp), y + Math.sin(a) * (r * 0.36 + amp));
      ctx.strokeStyle = cy(0.3 + level * 0.5);
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    text(ctx, "JARVIS", x, y + 6, {
      size: r * 0.32, weight: 800, align: "center",
      color: wh(0.7 + mood.mark * 0.3), glow: 14, font: 'ui-sans-serif, system-ui, sans-serif',
    });
    zoneCircle("dials", "dials", x, y, r, "Bo'g'inlar paneli");
  }

  // Chapdagi vertikal shkala — mikrofon darajasi
  function drawVuColumn(ctx, x, yTop, h, level, active) {
    const slots = 20;
    const slotH = h / slots;
    const lit = Math.round(level * slots);
    for (let i = 0; i < slots; i++) {
      const yy = yTop + h - (i + 1) * slotH;
      const hot = i / slots;
      const color = hot > 0.85 ? P.RGB.red : hot > 0.6 ? P.RGB.amber : P.RGB.cyan;
      const on = active && i < lit;
      ctx.fillStyle = P.toCss(color, on ? 0.9 : 0.10);
      ctx.fillRect(x, yy + 1.5, 16, slotH - 3);
      if (i % 4 === 0) {
        text(ctx, String(Math.round((i / slots) * 100)), x - 6, yy + slotH - 2,
             { size: 9, align: "right", color: am(0.55) });
      }
    }
    text(ctx, "MIC", x + 8, yTop + h + 16, { size: 9, align: "center", color: am(0.7), spacing: 1.6 });
  }

  // ---------------------------------------------------------- taqvim / batareya
  function drawCalendar(ctx, x, y) {
    const today = new Date();
    const dow = today.getDay();
    text(ctx, `${MONTH_UZ[today.getMonth()]} ${today.getFullYear()}`, x, y - 12,
         { size: 10, color: cy(0.55), spacing: 2.4 });
    for (let i = 0; i < 7; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() - dow + i);
      const cx0 = x + i * 34;
      const isToday = i === dow;
      if (isToday) {
        ctx.fillStyle = cy(0.18);
        ctx.fillRect(cx0 - 3, y - 2, 30, 34);
        ctx.strokeStyle = cy(0.7);
        ctx.lineWidth = 1;
        ctx.strokeRect(cx0 - 3, y - 2, 30, 34);
      }
      text(ctx, WEEK_SHORT[i], cx0 + 12, y + 10,
           { size: 9, align: "center", color: isToday ? cy(0.95) : wh(0.35) });
      text(ctx, String(d.getDate()), cx0 + 12, y + 27, {
        size: 13, align: "center", weight: 700,
        color: isToday ? wh(1) : wh(0.55), glow: isToday ? 10 : 0,
      });
    }
  }

  function drawBattery(ctx, x, y, battery) {
    const has = battery && battery.percent !== null && battery.percent !== undefined;
    const pct = has ? battery.percent : 100;
    const color = pct < 20 ? P.RGB.red : pct < 40 ? P.RGB.amber : P.RGB.cyan;
    // Batareya korpusi
    ctx.strokeStyle = P.toCss(color, 0.7);
    ctx.lineWidth = 1.4;
    ctx.strokeRect(x, y, 46, 16);
    ctx.fillStyle = P.toCss(color, 0.7);
    ctx.fillRect(x + 46, y + 5, 3, 6);
    ctx.fillStyle = P.toCss(color, 0.85);
    ctx.fillRect(x + 2, y + 2, 42 * (pct / 100), 12);
    text(ctx, `${Math.round(pct)}%`, x + 58, y + 13, { size: 12, color: wh(0.85) });
    text(ctx, battery && battery.charging ? "AC LINE" : has ? "BATTERY" : "AC LINE",
         x, y + 30, { size: 9, color: cy(0.5), spacing: 1.8 });
  }

  // ---------------------------------------------------------- pastdagi katta soat
  function drawBigClock(ctx, x, y, t) {
    const d = new Date();
    const hh = pad(d.getHours());
    const mm = pad(d.getMinutes());
    const ss = pad(d.getSeconds());
    // Ikki nuqta miltillaydi, lekin joyidan qimirlamaydi — raqamlar sakramasin
    const hw = measure(ctx, hh, 92, 700);
    const cw = measure(ctx, ":", 92, 700);
    text(ctx, hh, x, y, { size: 92, weight: 700, color: wh(0.95), glow: 18 });
    text(ctx, ":", x + hw, y, {
      size: 92, weight: 700, color: wh(d.getMilliseconds() < 500 ? 0.95 : 0.25),
    });
    text(ctx, mm, x + hw + cw, y, { size: 92, weight: 700, color: wh(0.95), glow: 18 });
    const w = hw + cw + measure(ctx, mm, 92, 700);
    // Sekundlar raqamlar ustida — yonidagi panelga tegib ketmasin
    text(ctx, ss, x + w, y - 66, { size: 24, weight: 700, align: "right", color: cy(0.75) });
    text(ctx, `${d.getDate()}-${MONTH_UZ[d.getMonth()].slice(0, 3).toLowerCase()}., ${WEEK_UZ[d.getDay()].toLowerCase()}`,
         x + 4, y - 78, { size: 15, color: cy(0.65), spacing: 2.2 });
    // Ostidagi jonli chiziq
    ctx.strokeStyle = cy(0.35);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y + 12);
    ctx.lineTo(x + w + 60, y + 12);
    ctx.stroke();
    const run = ((t * 40) % (w + 60));
    ctx.fillStyle = cy(0.9);
    ctx.fillRect(x + run, y + 10, 24, 3);
  }

  // ---------------------------------------------------------- tezkor havolalar
  const LINKS = [
    ["GOOGLE", "https://google.com"],
    ["GMAIL", "https://gmail.com"],
    ["FACEBOOK", "https://facebook.com"],
    ["YOUTUBE", "https://youtube.com"],
    ["IMDB", "https://imdb.com"],
    ["GITHUB", "https://github.com"],
    ["TELEGRAM", "https://t.me"],
    ["CLAUDE", "https://claude.ai"],
    ["WIKIPEDIA", "https://wikipedia.org"],
    ["YAHOO", "https://yahoo.com"],
  ];

  function drawLinks(ctx, x, y, hover) {
    text(ctx, "WEB", x, y - 22, { size: 15, weight: 700, align: "right", color: wh(0.75), spacing: 3 });
    LINKS.forEach(([label, url], i) => {
      const ly = y + i * 24;
      const hot = hover && hover.kind === "url" && hover.id === url;
      text(ctx, label, x, ly, {
        size: 12, align: "right", spacing: 2,
        color: hot ? cy(1) : wh(0.62), glow: hot ? 12 : 0,
      });
      const w = measure(ctx, label, 12, 600, 2);
      zoneRect("url", url, x - w - 6, ly - 13, w + 12, 20, label);
    });
  }

  // ---------------------------------------------------------- yuqoridagi dok
  const DOCK = [
    { app: "Finder", label: "FINDER" },
    { app: "Safari", label: "SAFARI" },
    { app: "Mail", label: "POCHTA" },
    { app: "Calendar", label: "TAQVIM" },
    { app: "Notes", label: "ESLATMA" },
    { app: "Terminal", label: "TERMINAL" },
  ];

  function drawDock(ctx, x, y, hover) {
    DOCK.forEach((d, i) => {
      const bx = x + i * 118;
      const hot = hover && hover.kind === "app" && hover.id === d.app;
      chip(ctx, bx, y, 108, 30, d.label, hot, "cyan");
      zoneRect("app", d.app, bx, y, 108, 30, d.label);
    });
  }

  // ---------------------------------------------------------- sana bloki
  function drawDateBlock(ctx, x, y) {
    const d = new Date();
    text(ctx, String(d.getDate()), x, y, {
      size: 62, weight: 700, align: "right", color: wh(0.95), glow: 14,
    });
    ctx.fillStyle = am(0.85);
    ctx.fillRect(x - 92, y + 8, 92, 20);
    text(ctx, MONTH_UZ[d.getMonth()], x - 46, y + 23,
         { size: 12, align: "center", color: "rgba(6, 14, 20, 0.95)", spacing: 1.6, weight: 700 });
    text(ctx, WEEK_UZ[d.getDay()], x, y + 42,
         { size: 10, align: "right", color: cy(0.6), spacing: 2.4 });
  }

  // ---------------------------------------------------------- ob-havo
  function drawWeather(ctx, x, y, weather, t) {
    panel(ctx, x, y, 150, 74, { cut: 8 });
    if (!weather) {
      text(ctx, "OB-HAVO", x + 10, y + 20, { size: 10, color: cy(0.5), spacing: 2 });
      text(ctx, "—", x + 10, y + 46, { size: 24, color: wh(0.5) });
      return;
    }
    text(ctx, "BUGUN", x + 10, y + 18, { size: 10, color: cy(0.6), spacing: 2 });
    text(ctx, `${weather.today.max}°`, x + 10, y + 52, { size: 30, weight: 700, color: wh(0.92), glow: 10 });
    text(ctx, `${weather.today.min}°`, x + 62, y + 52, { size: 15, color: cy(0.6) });
    if (weather.tomorrow) {
      text(ctx, `ERTAGA ${weather.tomorrow.max}°/${weather.tomorrow.min}°`, x + 10, y + 66,
           { size: 9, color: wh(0.45), spacing: 0.8 });
    }
    // Kichik aylanuvchi belgi
    dial(ctx, x + 122, y + 34, 18, t, { speed: 0.4, alpha: 0.6 });
  }

  // ---------------------------------------------------------- globus va tarmoq
  function drawGlobe(ctx, x, y, r, t, sys) {
    ctx.save();
    ctx.strokeStyle = cy(0.35);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, TAU);
    ctx.stroke();

    // Meridianlar — aylanadi
    const spin = t * 0.4;
    for (let i = 0; i < 6; i++) {
      const phase = spin + (i / 6) * Math.PI;
      const rx = Math.abs(Math.cos(phase)) * r;
      ctx.beginPath();
      ctx.ellipse(x, y, Math.max(1, rx), r, 0, 0, TAU);
      ctx.strokeStyle = cy(0.10 + 0.18 * Math.abs(Math.sin(phase)));
      ctx.stroke();
    }
    // Parallellar
    for (let i = 1; i < 4; i++) {
      const yy = (i / 4) * r;
      const rr = Math.sqrt(Math.max(0, r * r - yy * yy));
      for (const sign of [1, -1]) {
        ctx.beginPath();
        ctx.ellipse(x, y + yy * sign, rr, rr * 0.22, 0, 0, TAU);
        ctx.strokeStyle = cy(0.13);
        ctx.stroke();
      }
    }
    // Ulanish nuqtasi — pulslanadi
    const blip = 0.4 + 0.6 * Math.abs(Math.sin(t * 1.6));
    const bx = x + Math.cos(spin * 1.4) * r * 0.5;
    const by = y - r * 0.2;
    ctx.fillStyle = cy(blip);
    ctx.beginPath();
    ctx.arc(bx, by, 3.5, 0, TAU);
    ctx.fill();
    ctx.strokeStyle = cy(0.5 * blip);
    ctx.beginPath();
    ctx.arc(bx, by, 3.5 + blip * 9, 0, TAU);
    ctx.stroke();
    // Chiziq va yozuv
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(x + r + 26, y - r * 0.5);
    ctx.strokeStyle = cy(0.4);
    ctx.stroke();
    ctx.restore();
    text(ctx, sys.city || "TOSHKENT", x + r + 30, y - r * 0.5 - 4, { size: 11, color: wh(0.8), spacing: 1.6 });
    text(ctx, sys.ip || "—", x + r + 30, y - r * 0.5 + 12, { size: 11, color: cy(0.7), spacing: 1 });
  }

  function drawNetPanel(ctx, x, y, w, sys) {
    const net = sys.net || {};
    panel(ctx, x, y, w, 86, { title: "TARMOQ" });
    text(ctx, "DWN", x + 12, y + 44, { size: 10, color: cy(0.6), spacing: 1.6 });
    text(ctx, RATE(net.down), x + w - 12, y + 44, { size: 13, align: "right", color: wh(0.9) });
    text(ctx, "UPL", x + 12, y + 70, { size: 10, color: am(0.7), spacing: 1.6 });
    text(ctx, RATE(net.up), x + w - 12, y + 70, { size: 13, align: "right", color: am(0.9) });
  }

  // ---------------------------------------------------------- o'ngdagi soat
  function drawSideClock(ctx, x, y, t) {
    const d = new Date();
    text(ctx, pad(d.getSeconds()), x, y, {
      size: 20, weight: 700, align: "right", color: cy(0.7),
    });
    text(ctx, `${pad(d.getHours())}:${pad(d.getMinutes())}`, x - 34, y, {
      size: 54, weight: 700, align: "right", color: wh(0.95), glow: 16,
    });
    text(ctx, `${WEEK_UZ[d.getDay()]}`, x, y + 20, { size: 11, align: "right", color: cy(0.7), spacing: 2.6 });
    text(ctx, `${d.getDate()} ${MONTH_UZ[d.getMonth()]} ${d.getFullYear()}`, x, y + 38,
         { size: 10, align: "right", color: wh(0.45), spacing: 1.6 });
    // Sekund strelkasi bo'lgan kichik analog siferblat
    const cxx = x - 210;
    const cyy = y - 14;
    const r = 30;
    ctx.strokeStyle = cy(0.3);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cxx, cyy, r, 0, TAU);
    ctx.stroke();
    for (let i = 0; i < 12; i++) {
      const a = (i / 12) * TAU;
      ctx.beginPath();
      ctx.moveTo(cxx + Math.cos(a) * r * 0.86, cyy + Math.sin(a) * r * 0.86);
      ctx.lineTo(cxx + Math.cos(a) * r, cyy + Math.sin(a) * r);
      ctx.strokeStyle = cy(i % 3 === 0 ? 0.6 : 0.25);
      ctx.stroke();
    }
    const secs = d.getSeconds() + d.getMilliseconds() / 1000;
    const hands = [
      [((d.getHours() % 12) + d.getMinutes() / 60) / 12, r * 0.5, 2.4, wh(0.85)],
      [(d.getMinutes() + secs / 60) / 60, r * 0.75, 1.8, wh(0.7)],
      [secs / 60, r * 0.85, 1, cy(0.9)],
    ];
    for (const [frac, len, lw, color] of hands) {
      const a = frac * TAU - Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(cxx, cyy);
      ctx.lineTo(cxx + Math.cos(a) * len, cyy + Math.sin(a) * len);
      ctx.strokeStyle = color;
      ctx.lineWidth = lw;
      ctx.stroke();
    }
    ctx.lineWidth = 1;
  }

  // ---------------------------------------------------------- fayl tizimlari
  function drawFilesystems(ctx, x, y, w, sys) {
    const disks = (sys.disks || []).slice(0, 4);
    const h = 34 + Math.max(1, disks.length) * 30;
    panel(ctx, x, y, w, h, { title: "FILESYSTEMS" });
    if (!disks.length) {
      text(ctx, "disklar o'qilmoqda…", x + 12, y + 50, { size: 10, color: wh(0.35) });
      return h;
    }
    disks.forEach((d, i) => {
      const ry = y + 44 + i * 30;
      text(ctx, d.name, x + 12, ry, { size: 11, color: cy(0.85), spacing: 1 });
      text(ctx, `${GB(d.usedGb)} / ${GB(d.totalGb)}`, x + w - 12, ry,
           { size: 10, align: "right", color: wh(0.6) });
      bar(ctx, x + 12, ry + 6, w - 24, 5, d.percent / 100,
          d.percent > 90 ? P.RGB.red : P.RGB.cyan, { ticks: 24 });
    });
    return h;
  }

  // ---------------------------------------------------------- zirh siluetlari
  function drawArmorSilhouette(ctx, x, y, h, t, phase) {
    const s = h / 100;
    ctx.save();
    ctx.translate(x, y);
    ctx.strokeStyle = cy(0.30);
    ctx.lineWidth = 1.2;

    const part = (pts, close) => {
      ctx.beginPath();
      pts.forEach(([px, py], i) => {
        if (i === 0) ctx.moveTo(px * s, py * s);
        else ctx.lineTo(px * s, py * s);
      });
      if (close) ctx.closePath();
      ctx.stroke();
    };

    // Bosh
    part([[-5, 0], [5, 0], [7, 7], [5, 13], [-5, 13], [-7, 7]], true);
    // Yelka va tana
    part([[-6, 14], [-16, 18], [-19, 30], [-14, 32], [-12, 50], [-9, 62],
          [9, 62], [12, 50], [14, 32], [19, 30], [16, 18], [6, 14]], true);
    // Qo'llar
    part([[-19, 30], [-23, 46], [-22, 58], [-18, 58], [-16, 44]], true);
    part([[19, 30], [23, 46], [22, 58], [18, 58], [16, 44]], true);
    // Oyoqlar
    part([[-9, 62], [-11, 82], [-10, 96], [-3, 96], [-2, 80], [-1, 62]], true);
    part([[9, 62], [11, 82], [10, 96], [3, 96], [2, 80], [1, 62]], true);

    // Reaktor nuqtasi
    const pulse = 0.4 + 0.6 * Math.abs(Math.sin(t * 1.3 + phase));
    ctx.fillStyle = cy(pulse);
    ctx.beginPath();
    ctx.arc(0, 26 * s, 2.4 * s, 0, TAU);
    ctx.fill();

    // Skanerlash chizig'i — pastdan yuqoriga yuguradi
    const scan = ((t * 0.35 + phase) % 1) * 100;
    ctx.save();
    ctx.beginPath();
    ctx.rect(-26 * s, (scan - 3) * s, 52 * s, 6 * s);
    ctx.clip();
    ctx.strokeStyle = cy(0.85);
    ctx.lineWidth = 1.6;
    part([[-6, 14], [-16, 18], [-19, 30], [-14, 32], [-12, 50], [-9, 62],
          [9, 62], [12, 50], [14, 32], [19, 30], [16, 18], [6, 14]], true);
    part([[-9, 62], [-11, 82], [-10, 96], [-3, 96], [-2, 80], [-1, 62]], true);
    part([[9, 62], [11, 82], [10, 96], [3, 96], [2, 80], [1, 62]], true);
    ctx.restore();
    ctx.restore();
  }

  // ---------------------------------------------------------- radial menyu
  const RADIAL = [
    { label: "MAIL", url: "https://gmail.com" },
    { label: "GOOGLE", url: "https://google.com" },
    { label: "YOUTUBE", url: "https://youtube.com" },
    { label: "GITHUB", url: "https://github.com" },
    { label: "CLAUDE", url: "https://claude.ai" },
    { label: "WIKI", url: "https://wikipedia.org" },
  ];

  function drawRadial(ctx, x, y, r, t, hover) {
    // Tashqi zargaldoq yoy
    ctx.beginPath();
    ctx.arc(x, y, r * 1.18, Math.PI * 1.05, Math.PI * 1.95);
    ctx.strokeStyle = am(0.55);
    ctx.lineWidth = 14;
    ctx.stroke();
    ctx.lineWidth = 1;

    dial(ctx, x, y, r * 0.72, t, { speed: 0.3 });
    dial(ctx, x, y, r * 0.42, -t, { speed: 0.6, alpha: 0.7 });

    RADIAL.forEach((item, i) => {
      const a = -Math.PI / 2 + (i / RADIAL.length) * TAU * 0.62 - 0.3;
      const px = x + Math.cos(a) * r * 1.34;
      const py = y + Math.sin(a) * r * 1.34;
      const hot = hover && hover.kind === "url" && hover.id === item.url;
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(a) * r * 0.98, y + Math.sin(a) * r * 0.98);
      ctx.lineTo(px - 6, py);
      ctx.strokeStyle = cy(hot ? 0.9 : 0.35);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(px, py, 4, 0, TAU);
      ctx.fillStyle = hot ? cy(1) : cy(0.6);
      ctx.fill();
      text(ctx, item.label, px + 10, py + 4, {
        size: 11, color: hot ? cy(1) : wh(0.65), spacing: 1.4, glow: hot ? 10 : 0,
      });
      const w = measure(ctx, item.label, 11, 600, 1.4);
      zoneRect("url", item.url, px - 6, py - 12, w + 24, 24, item.label);
    });
  }

  // ---------------------------------------------------------- papkalar
  const FOLDERS = [
    { key: "downloads", label: "YUKLAMALAR" },
    { key: "documents", label: "HUJJATLAR" },
    { key: "pictures", label: "RASMLAR" },
    { key: "music", label: "MUSIQA" },
    { key: "videos", label: "VIDEOLAR" },
    { key: "desktop", label: "ISH STOLI" },
  ];

  // ---------------------------------------------------------- ovoz balandligi
  //
  // O'ng chekkadagi ustun. Bosilsa — tizim ovozi o'sha darajaga qo'yiladi.
  function drawVolume(ctx, x, yTop, h, volume, hover) {
    const v = Math.max(0, Math.min(100, volume === null || volume === undefined ? 0 : volume));
    const slots = 24;
    const slotH = h / slots;
    const lit = Math.round((v / 100) * slots);
    for (let i = 0; i < slots; i++) {
      const yy = yTop + h - (i + 1) * slotH;
      const on = i < lit;
      ctx.fillStyle = am(on ? 0.9 : 0.12);
      ctx.fillRect(x, yy + 1.5, 22, slotH - 3);
    }
    corners(ctx, x - 6, yTop - 6, 34, h + 12, 8, am(hover ? 0.9 : 0.45));
    text(ctx, "OVOZ", x + 11, yTop + h + 20, { size: 10, align: "center", color: am(0.8), spacing: 1.6 });
    text(ctx, `${Math.round(v)}%`, x + 11, yTop - 14, { size: 11, align: "center", color: wh(0.75) });
    zoneRect("volume", "volume", x - 8, yTop - 8, 38, h + 16, "Ovoz balandligi");
  }

  // ---------------------------------------------------------- bosh chizmasi
  function drawHead(ctx, x, y, r, t) {
    ctx.save();
    ctx.translate(x, y);
    ctx.strokeStyle = cy(0.30);
    ctx.lineWidth = 1;
    // Bosh konturi
    ctx.beginPath();
    ctx.ellipse(0, 0, r * 0.62, r, 0, 0, TAU);
    ctx.stroke();
    // Ichki chiziqlar — profil hissi
    for (let i = -2; i <= 2; i++) {
      ctx.beginPath();
      ctx.ellipse(0, 0, r * 0.62 * (1 - Math.abs(i) * 0.18), r, 0, 0, TAU);
      ctx.strokeStyle = cy(0.10);
      ctx.stroke();
    }
    for (let i = 1; i < 6; i++) {
      const yy = -r + (i / 6) * r * 2;
      const rr = r * 0.62 * Math.sqrt(Math.max(0, 1 - (yy / r) ** 2));
      ctx.beginPath();
      ctx.ellipse(0, yy, rr, rr * 0.2, 0, 0, TAU);
      ctx.strokeStyle = cy(0.10);
      ctx.stroke();
    }
    // Skanerlash chizig'i
    const scan = Math.sin(t * 0.7) * r;
    const rr = r * 0.62 * Math.sqrt(Math.max(0, 1 - (scan / r) ** 2));
    ctx.beginPath();
    ctx.ellipse(0, scan, rr, Math.max(1, rr * 0.2), 0, 0, TAU);
    ctx.strokeStyle = cy(0.8);
    ctx.lineWidth = 1.6;
    ctx.stroke();
    ctx.restore();
    text(ctx, "BIOMETRIYA", x, y + r + 18, { size: 9, align: "center", color: cy(0.5), spacing: 2 });
  }

  // ---------------------------------------------------------- media boshqaruvi
  function drawMedia(ctx, x, y, w, media, hover) {
    panel(ctx, x, y, w, 78, { cut: 8 });
    const title = media && media.title ? media.title : "ijro yo'q";
    const sub = media && media.artist ? media.artist : "—";
    text(ctx, title.length > 26 ? title.slice(0, 25) + "…" : title,
         x + 12, y + 22, { size: 11, color: wh(0.85), spacing: 0.6 });
    text(ctx, sub.length > 30 ? sub.slice(0, 29) + "…" : sub,
         x + 12, y + 38, { size: 9.5, color: cy(0.55) });

    const buttons = [
      ["prev", x + 12], ["playpause", x + 48], ["next", x + 84],
    ];
    for (const [id, bx] of buttons) {
      const by = y + 60;
      const hot = hover && hover.kind === "media" && hover.id === id;
      ctx.fillStyle = hot ? cy(0.95) : cy(0.6);
      ctx.beginPath();
      if (id === "prev") {
        ctx.moveTo(bx + 14, by - 6); ctx.lineTo(bx + 14, by + 6); ctx.lineTo(bx + 5, by);
        ctx.closePath(); ctx.fill();
        ctx.fillRect(bx + 2, by - 6, 2, 12);
      } else if (id === "next") {
        ctx.moveTo(bx + 2, by - 6); ctx.lineTo(bx + 2, by + 6); ctx.lineTo(bx + 11, by);
        ctx.closePath(); ctx.fill();
        ctx.fillRect(bx + 12, by - 6, 2, 12);
      } else if (media && media.playing) {
        ctx.fillRect(bx + 3, by - 6, 4, 12);
        ctx.fillRect(bx + 10, by - 6, 4, 12);
      } else {
        ctx.moveTo(bx + 3, by - 6); ctx.lineTo(bx + 3, by + 6); ctx.lineTo(bx + 14, by);
        ctx.closePath(); ctx.fill();
      }
      zoneRect("media", id, bx - 4, by - 12, 26, 24, id);
    }

    // Ijro chizig'i
    const prog = media && media.duration ? Math.min(1, (media.position || 0) / media.duration) : 0;
    bar(ctx, x + 120, y + 58, w - 132, 4, prog, P.RGB.cyan, { ticks: 30 });
  }

  // ---------------------------------------------------------- axlat qutisi
  function drawTrash(ctx, x, y, sys, hover) {
    const hot = hover && hover.kind === "trash";
    ctx.strokeStyle = cy(hot ? 0.95 : 0.5);
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(x - 16, y - 18);
    ctx.lineTo(x - 12, y + 18);
    ctx.lineTo(x + 12, y + 18);
    ctx.lineTo(x + 16, y - 18);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - 20, y - 18);
    ctx.lineTo(x + 20, y - 18);
    ctx.moveTo(x - 6, y - 18);
    ctx.lineTo(x - 6, y - 24);
    ctx.lineTo(x + 6, y - 24);
    ctx.lineTo(x + 6, y - 18);
    ctx.stroke();
    for (let i = -1; i <= 1; i++) {
      ctx.beginPath();
      ctx.moveTo(x + i * 7, y - 12);
      ctx.lineTo(x + i * 7, y + 12);
      ctx.strokeStyle = cy(0.25);
      ctx.stroke();
    }
    const count = sys.trash;
    text(ctx, count === null || count === undefined ? "AXLAT" : `AXLAT · ${count}`,
         x, y + 34, { size: 9.5, align: "center", color: cy(hot ? 0.95 : 0.55), spacing: 1.6 });
    zoneRect("trash", "trash", x - 24, y - 28, 48, 56, "Axlat qutisi");
  }

  // ---------------------------------------------------------- quvvat qatori
  function drawPowerLine(ctx, x, y, sys, state) {
    const b = sys.battery || {};
    const pct = b.percent === null || b.percent === undefined ? 100 : Math.round(b.percent);
    const word = b.charging ? "quvvat olmoqda" : "barqaror turibdi";
    const line = `Quvvat darajasi ${pct} foiz — ${word}.`;
    text(ctx, line, x, y, { size: 15, align: "center", color: wh(0.75), font: 'ui-sans-serif, system-ui, sans-serif' });
    const label = { idle: "KUTMOQDA", wake: "UYG'ONDI", listening: "TINGLAMOQDA",
                    thinking: "O'YLAMOQDA", speaking: "GAPIRMOQDA", confirm: "TASDIQ",
                    error: "XATO" }[state] || "KUTMOQDA";
    text(ctx, label, x, y + 22, { size: 10, align: "center", color: cy(0.7), spacing: 3.4 });
  }

  // ============================================================== fon

  const MOTES = Array.from({ length: 60 }, () => ({
    x: Math.random(), y: Math.random(),
    drift: 0.003 + Math.random() * 0.012,
    phase: Math.random() * TAU,
    size: 0.6 + Math.random() * 1.4,
  }));

  function drawBackground(ctx, W, H, t) {
    // Chuqur ko'k-qora fon
    const g = ctx.createRadialGradient(W * 0.5, H * 0.45, 0, W * 0.5, H * 0.5, Math.max(W, H) * 0.75);
    g.addColorStop(0, "#071722");
    g.addColorStop(0.55, "#04101a");
    g.addColorStop(1, "#01060a");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    // Chizma qog'ozi to'ri
    const step = Math.max(34, Math.round(W / 48));
    ctx.strokeStyle = cy(0.035);
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = step; x < W; x += step) { ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, H); }
    for (let y = step; y < H; y += step) { ctx.moveTo(0, y + 0.5); ctx.lineTo(W, y + 0.5); }
    ctx.stroke();

    ctx.strokeStyle = cy(0.075);
    ctx.beginPath();
    for (let x = step * 4; x < W; x += step * 4) {
      for (let y = step * 4; y < H; y += step * 4) {
        ctx.moveTo(x - 4, y); ctx.lineTo(x + 4, y);
        ctx.moveTo(x, y - 4); ctx.lineTo(x, y + 4);
      }
    }
    ctx.stroke();

    // Suzuvchi zarrachalar
    for (const m of MOTES) {
      const y = (m.y + t * m.drift) % 1;
      const tw = 0.3 + 0.7 * Math.abs(Math.sin(t * 0.9 + m.phase));
      ctx.beginPath();
      ctx.arc(m.x * W, y * H, m.size, 0, TAU);
      ctx.fillStyle = cy(0.12 * tw);
      ctx.fill();
    }
  }

  // Uyqu pardasi — hammasi ko'rinadi, lekin so'ngan
  function drawVeil(ctx, W, H, boot, t) {
    if (boot > 0.995) return;
    ctx.save();
    ctx.fillStyle = `rgba(2, 7, 11, ${((1 - boot) * 0.62).toFixed(3)})`;
    ctx.fillRect(0, 0, W, H);
    const wake = 1 - Math.abs(boot * 2 - 1);
    if (wake > 0.05) {
      const y = H * (0.5 - Math.cos(t * 1.6) * 0.5);
      const g = ctx.createLinearGradient(0, y - 70, 0, y + 70);
      g.addColorStop(0, cy(0));
      g.addColorStop(0.5, cy(0.12 * wake));
      g.addColorStop(1, cy(0));
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = g;
      ctx.fillRect(0, y - 70, W, 140);
    }
    ctx.restore();
  }

  // ============================================================== kadr

  /**
   * Bitta kadr.
   *
   * f = {
   *   width, height, t, state, level, flash, boot, hover,
   *   figure,                       // foydalanuvchi rasmi bormi (markazga zirh chizilmaydi)
   *   sys: { cpu, ram, swap, ramUsedGb, ramTotalGb, uptimeSec, disks[], battery, net,
   *          volume, user, host, ip, city, trash },
   *   weather, media,
   * }
   */
  function draw(ctx, f) {
    zones = [];
    const W = f.width;
    const H = f.height;
    const t = f.t;
    const sys = f.sys || {};
    const hover = f.hover;
    const boot = f.boot === undefined ? 1 : Math.max(0, Math.min(1, f.boot));
    const mood = P.STATE_MOOD[f.state] || P.STATE_MOOD.idle;
    const level = Math.max(0, Math.min(1, f.level || 0));
    const active = f.state === "listening" || f.state === "speaking";

    let eyes = 0.25 + mood.glow * 0.5 + (f.flash || 0) * 0.6;
    if (f.state === "thinking") eyes = 0.45 + Math.abs(Math.sin(t * 2.2)) * 0.3;
    eyes = Math.min(1, eyes) * boot * boot;
    const surge = Math.min(1, mood.core * 0.6 + (f.flash || 0) + level * 0.6) * boot;

    drawBackground(ctx, W, H, t);

    const s = Math.min(W / VW, H / VH);
    view = { s, dx: (W - VW * s) / 2, dy: (H - VH * s) / 2 };
    ctx.save();
    ctx.translate(view.dx, view.dy);
    ctx.scale(s, s);

    // ---- markaz: zirh chizmasi va uning halqalari
    const suit = { cx: 960, topY: 130, height: 810 };
    if (!f.figure) {
      const anchor = SUIT.reactorAt(suit);
      drawRings(ctx, anchor.x, anchor.y, suit.height * 0.46, t, mood.glow * boot);
      SUIT.draw(ctx, { ...suit, t, eyes, surge });
      zoneCircle("activate", "activate", anchor.x, anchor.y, 70, "Jarvis'ni chaqirish");
    }

    // ---- chap ustun
    drawShield(ctx, 100, 96, 56, t);
    drawIdentity(ctx, 168, 46, 240, 78, sys, t);
    drawAppRail(ctx, 168, 175, hover);
    text(ctx, "STARK INDUSTRIES", 168, 478, { size: 11, color: cy(0.35), spacing: 4 });

    ctx.save();
    ctx.translate(42, 620);
    ctx.rotate(-Math.PI / 2);
    text(ctx, "BRIDGE CONTROL", 0, 0, { size: 10, color: wh(0.25), spacing: 6 });
    ctx.restore();

    gear(ctx, 285, 530, 44, 14, t * 0.3, 0.28);
    gear(ctx, 345, 568, 26, 10, -t * 0.5, 0.22);
    gear(ctx, 240, 578, 20, 8, -t * 0.6, 0.20);

    drawJarvisEmblem(ctx, 280, 830, 105, t, level, mood,
                     hover && hover.kind === "dials");
    drawVuColumn(ctx, 110, 640, 260, level, active);
    drawCalendar(ctx, 190, 966);
    drawBattery(ctx, 190, 1028, sys.battery);
    hexField(ctx, 420, 780, 4, 3, 17, t);

    // ---- ikkinchi ustun: o'lchagichlar
    drawRamGauge(ctx, 430, 140, sys, t);
    drawSystemPanel(ctx, 430, 250, 250, sys);
    drawDrivePanel(ctx, 430, 420, 250, sys);
    dial(ctx, 560, 640, 100, t, {
      value: (sys.cpu || 0) / 100, label: `${Math.round(sys.cpu || 0)}%`,
      sub: "CPU YUKI", speed: 0.22,
    });

    // ---- markaz chapdagi havolalar
    drawLinks(ctx, 800, 340, hover);

    // ---- yuqori o'ng: dok va sana
    drawDock(ctx, 1120, 44, hover);
    drawDateBlock(ctx, 1890, 118);

    // ---- o'ng ustun
    drawWeather(ctx, 1180, 280, f.weather, t);
    drawNetPanel(ctx, 1370, 280, 180, sys);
    drawSideClock(ctx, 1890, 300, t);
    drawGlobe(ctx, 1260, 470, 72, t, sys);
    drawFilesystems(ctx, 1500, 400, 320, sys);
    drawTrash(ctx, 1230, 620, sys, hover);

    // Yuk tarixi grafigi
    panel(ctx, 1310, 600, 220, 104, { title: "YUK TARIXI" });
    graph(ctx, 1322, 632, 196, 60, history.cpu, P.RGB.cyan);
    graph(ctx, 1322, 632, 196, 60, history.ram, P.RGB.amber);
    text(ctx, "CPU", 1322, 700, { size: 9, color: cy(0.7), spacing: 1.4 });
    text(ctx, "RAM", 1360, 700, { size: 9, color: am(0.7), spacing: 1.4 });
    text(ctx, "NET", 1398, 700, { size: 9, color: wh(0.4), spacing: 1.4 });

    drawArmorSilhouette(ctx, 1600, 570, 220, t, 0);
    drawArmorSilhouette(ctx, 1720, 570, 220, t, 0.5);
    drawRadial(ctx, 1330, 840, 95, t, hover);
    drawFolders3(ctx, 1440, 985, hover);
    drawVolume(ctx, 1870, 560, 340, sys.volume,
               hover && hover.kind === "volume");

    // ---- pastki qator
    drawPowerLine(ctx, 960, 968, sys, f.state);
    drawBigClock(ctx, 460, 1050, t);
    drawMedia(ctx, 740, 1000, 300, f.media, hover);
    drawHead(ctx, 1230, 1000, 52, t);

    ctx.restore();
    drawVeil(ctx, W, H, boot, t);
    return { eyes, surge };
  }

  // Zirh orqasidagi katta halqalar
  function drawRings(ctx, cx, cyy, R, t, energy) {
    const spin = t * 0.06;
    ctx.strokeStyle = cy(0.20);
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < 90; i++) {
      const a = spin + (i / 90) * TAU;
      const r0 = R * (i % 15 === 0 ? 0.95 : 0.975);
      ctx.moveTo(cx + Math.cos(a) * r0, cyy + Math.sin(a) * r0);
      ctx.lineTo(cx + Math.cos(a) * R, cyy + Math.sin(a) * R);
    }
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cyy, R, 0, TAU);
    ctx.strokeStyle = cy(0.16);
    ctx.stroke();

    ctx.setLineDash([3, 9]);
    ctx.beginPath();
    ctx.arc(cx, cyy, R * 0.88, -t * 0.1, -t * 0.1 + TAU);
    ctx.strokeStyle = cy(0.15);
    ctx.stroke();
    ctx.setLineDash([]);

    for (const [k, from, sweep, speed, w] of [
      [1.06, 0.4, 1.3, 0.22, 2], [1.06, 3.6, 0.6, 0.22, 2],
      [0.80, 2.0, 1.8, -0.15, 2.6], [0.72, 5.0, 0.9, 0.3, 1.4],
    ]) {
      const a = from + t * speed;
      ctx.beginPath();
      ctx.arc(cx, cyy, R * k, a, a + sweep);
      ctx.strokeStyle = cy(0.22 + energy * 0.3);
      ctx.lineWidth = w;
      ctx.stroke();
    }
    ctx.lineWidth = 1;
  }

  // Papkalar — uch ustun, ikki qator (pastki o'ng burchak)
  function drawFolders3(ctx, x, y, hover) {
    FOLDERS.forEach((f, i) => {
      const col = i % 3;
      const row = Math.floor(i / 3);
      const bx = x + col * 153;
      const by = y + row * 40;
      const hot = hover && hover.kind === "folder" && hover.id === f.key;
      chip(ctx, bx, by, 145, 30, f.label, hot, "slate");
      zoneRect("folder", f.key, bx, by, 145, 30, f.label);
    });
  }

  // ============================================================== bosish

  // Ekran koordinatasi -> qaysi vidjet ustida turibmiz
  function hit(x, y) {
    const vx = (x - view.dx) / view.s;
    const vy = (y - view.dy) / view.s;
    for (let i = zones.length - 1; i >= 0; i--) {
      const z = zones[i];
      if (z.r !== undefined) {
        if ((vx - z.cx) ** 2 + (vy - z.cy) ** 2 <= z.r * z.r) return { ...z, vx, vy };
      } else if (vx >= z.x && vx <= z.x + z.w && vy >= z.y && vy <= z.y + z.h) {
        return { ...z, vx, vy };
      }
    }
    return null;
  }

  // Ovoz ustunida bosilgan nuqta -> 0..100 daraja
  function volumeFromHit(zone) {
    if (!zone || zone.kind !== "volume") return null;
    const rel = 1 - (zone.vy - zone.y) / zone.h;
    return Math.round(Math.max(0, Math.min(1, rel)) * 100);
  }

  return { draw, hit, pushStats, volumeFromHit, VW, VH };
})();

if (typeof module !== "undefined") module.exports = SHELL;
