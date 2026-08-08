// HUD chizuvchi — Jarvis'ning ko'rinadigan yuzi.
//
// Tuzilishi markazdan tashqariga qarab:
//
//   0.00–0.34  yadro (reaktor) va JARVIS yozuvi — asosiy ikonka
//   0.44       ovoz to'lqini — gapirganda va tinglaganda jonlanadi
//   0.52–0.66  chizma yoylari — turli tezlikda aylanadi
//   0.75       bo'g'in siferblatlari — har biri bitta tizimga bog'langan
//   0.88       siferblat yozuvlari — gorizontal oq matn
//   0.94–1.00  chekka: darajali bo'linmalar, burchak qavslari, radar chizig'i
//
// Asosiy g'oya: har bir siferblat tirik ko'rsatkich. Aylanayotgani — o'sha
// bo'g'in ishlayapti; tezroq aylanishi — hozir ish bajaryapti; qizarishi va
// to'xtashi — buzilgan. Ekranga bir qarabroq qayerda muammo borligi ko'rinadi.

const HUD = (() => {
  const TAU = Math.PI * 2;

  // ---------------------------------------------------------------- geometriya

  const RING = {
    core: 0.34,
    wave: 0.44,
    blueprint: [0.52, 0.59, 0.66],
    dials: 0.75,
    labels: 0.88,
    ticks: 0.94,
    edge: 1.0,
  };

  const DIAL_RADIUS = 0.075; // R ga nisbatan
  const TICK_COUNT = 72;
  const WAVE_BARS = 72;
  const MOTE_COUNT = 34;

  // Chizma yoylari — Iron Man chizmalaridagi konsentrik detallar.
  // Qarama-qarshi yo'nalishdagi tezliklar "mexanizm" hissini beradi.
  const ARCS = [
    { ring: 0, start: 0.00, sweep: 1.30, speed: 0.55, width: 1.6, alpha: 0.78 },
    { ring: 0, start: 3.35, sweep: 0.75, speed: 0.55, width: 1.6, alpha: 0.50 },
    { ring: 1, start: 1.60, sweep: 2.20, speed: -0.33, width: 2.4, alpha: 0.70 },
    { ring: 1, start: 4.60, sweep: 0.50, speed: -0.33, width: 2.4, alpha: 0.42 },
    { ring: 2, start: 4.20, sweep: 1.10, speed: 0.88, width: 1.3, alpha: 0.62 },
    { ring: 2, start: 0.90, sweep: 0.35, speed: 0.88, width: 1.3, alpha: 0.40 },
  ];

  const BRACKETS = [0, Math.PI / 2, Math.PI, Math.PI * 1.5];

  // Suzuvchi zarrachalar — bo'shliqni to'ldiradi, hajm beradi.
  const MOTES = Array.from({ length: MOTE_COUNT }, (_, i) => ({
    angle: (i / MOTE_COUNT) * TAU + Math.random(),
    radius: 0.40 + Math.random() * 0.48,
    speed: (Math.random() - 0.5) * 0.14,
    size: 0.5 + Math.random() * 1.2,
    phase: Math.random() * TAU,
  }));

  // ---------------------------------------------------------------- yordamchi

  function ringColor(status) {
    return P.RGB[P.STATUS_COLOR[status] || "slate"];
  }

  // Siferblat yozuvi — gorizontal, halqa bo'ylab egilgan emas.
  //
  // Egilgan matn chiroyli ko'rinadi, lekin o'ng va chap chekkada harflar
  // vertikal bo'lib qolib o'qilmaydi. Muammoni yozuvni gorizontal qoldirib,
  // faqat tayanch nuqtasini almashtirib hal qilamiz: o'ng yarimda matn
  // o'ngga, chap yarimda chapga o'sadi — shunda u hech qachon kadrdan
  // chiqib ketmaydi.
  function drawLabel(ctx, text, cx, cy, radius, angle, size, color, bounds) {
    const cos = Math.cos(angle);
    const y = cy + Math.sin(angle) * radius;

    ctx.save();
    ctx.font = `700 ${size}px ui-sans-serif, -apple-system, system-ui, sans-serif`;
    if ("letterSpacing" in ctx) ctx.letterSpacing = `${size * 0.11}px`;
    const align = cos > 0.25 ? "left" : cos < -0.25 ? "right" : "center";
    ctx.textAlign = align;
    ctx.textBaseline = "middle";

    // Kadr chetiga tegib qolgan yozuv kesiladi ("ASBOB" -> "SBOB"), shuning
    // uchun tayanch nuqtasini o'lchab ichkariga suramiz. Halqadan biroz
    // chekinish uzun yozuvni yo'qotib qo'yishdan afzal.
    const w = ctx.measureText(text).width;
    const pad = 3;
    let x = cx + cos * radius;
    if (align === "left") x = Math.min(x, bounds - pad - w);
    else if (align === "right") x = Math.max(x, pad + w);
    else x = Math.min(Math.max(x, pad + w / 2), bounds - pad - w / 2);

    ctx.fillStyle = color;
    // Qora fonda ingichka oq harflar yo'qolmasin
    ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
    ctx.shadowBlur = 4;
    ctx.fillText(text, x, y);
    ctx.restore();
  }

  // ---------------------------------------------------------------- qatlamlar

  function drawGlow(ctx, cx, cy, R, tint, intensity) {
    const g = ctx.createRadialGradient(cx, cy, R * 0.06, cx, cy, R);
    g.addColorStop(0, P.toCss(tint, 0.22 * intensity));
    g.addColorStop(0.45, P.toCss(tint, 0.07 * intensity));
    g.addColorStop(1, P.toCss(tint, 0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, TAU);
    ctx.fill();
  }

  function drawMotes(ctx, cx, cy, R, t, tint, intensity) {
    for (const m of MOTES) {
      const angle = m.angle + t * m.speed;
      const r = R * (m.radius + Math.sin(t * 0.7 + m.phase) * 0.025);
      const twinkle = 0.3 + 0.7 * Math.abs(Math.sin(t * 1.3 + m.phase));
      ctx.beginPath();
      ctx.arc(cx + Math.cos(angle) * r, cy + Math.sin(angle) * r, m.size, 0, TAU);
      ctx.fillStyle = P.toCss(tint, 0.3 * twinkle * intensity);
      ctx.fill();
    }
  }

  function drawTicks(ctx, cx, cy, R, t, tint, intensity) {
    const outer = R * RING.edge;
    for (let i = 0; i < TICK_COUNT; i++) {
      const angle = (i / TICK_COUNT) * TAU;
      const major = i % 6 === 0;
      const wave = 0.55 + 0.45 * Math.sin(t * 1.8 - i * 0.22);
      const len = (major ? 9 : 4) * (major ? 1 : wave);
      const inner = outer - len;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
      ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
      ctx.strokeStyle = P.toCss(tint, (major ? 0.72 : 0.3 * wave) * intensity);
      ctx.lineWidth = major ? 1.6 : 1;
      ctx.stroke();
    }
  }

  function drawBrackets(ctx, cx, cy, R, t, tint, intensity) {
    const r = R * 0.97;
    const spin = -t * 0.12;
    ctx.strokeStyle = P.toCss(tint, 0.65 * intensity);
    ctx.lineWidth = 2.2;
    for (const offset of BRACKETS) {
      const a = spin + offset;
      ctx.beginPath();
      ctx.arc(cx, cy, r, a - 0.17, a + 0.17);
      ctx.stroke();
      for (const end of [a - 0.17, a + 0.17]) {
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(end) * r, cy + Math.sin(end) * r);
        ctx.lineTo(cx + Math.cos(end) * (r - 8), cy + Math.sin(end) * (r - 8));
        ctx.stroke();
      }
    }
  }

  // Radar chizig'i — butun tizim tirikligining yagona umumiy belgisi.
  function drawSweep(ctx, cx, cy, R, t, tint, intensity) {
    const angle = t * 0.5;
    const r = R * RING.ticks;
    // Markazdan emas, yadro chekkasidan — aks holda chiziq JARVIS yozuvini kesadi
    const from = R * RING.blueprint[0];
    const x0 = cx + Math.cos(angle) * from;
    const y0 = cy + Math.sin(angle) * from;
    const x1 = cx + Math.cos(angle) * r;
    const y1 = cy + Math.sin(angle) * r;

    const g = ctx.createLinearGradient(x0, y0, x1, y1);
    g.addColorStop(0, P.toCss(tint, 0));
    g.addColorStop(1, P.toCss(tint, 0.55 * intensity));
    ctx.strokeStyle = g;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();

    // Chiziq ortidan qolgan xira iz
    ctx.beginPath();
    ctx.arc(cx, cy, r, angle - 0.55, angle);
    ctx.strokeStyle = P.toCss(tint, 0.14 * intensity);
    ctx.lineWidth = 3;
    ctx.stroke();
  }

  function drawArcs(ctx, cx, cy, R, t, spin, tint, intensity) {
    for (const arc of ARCS) {
      const r = R * RING.blueprint[arc.ring];
      const from = arc.start + t * arc.speed * spin;
      ctx.beginPath();
      ctx.arc(cx, cy, r, from, from + arc.sweep);
      ctx.strokeStyle = P.toCss(tint, arc.alpha * intensity);
      ctx.lineWidth = arc.width;
      ctx.stroke();
    }
    // Yoylar orasidagi uzuq halqa
    ctx.setLineDash([2, 7]);
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.585, 0, TAU);
    ctx.strokeStyle = P.toCss(tint, 0.38 * intensity);
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Bo'g'in siferblatlari — HUD'ning ma'no jihatidan eng muhim qismi.
  function drawDials(ctx, cx, cy, R, t, systems, intensity, width) {
    if (!systems.length) return;
    const ringR = R * RING.dials;
    const dialR = R * DIAL_RADIUS;

    systems.forEach((sys, i) => {
      // Tepadan boshlab soat yo'nalishida
      const angle = -Math.PI / 2 + (i / systems.length) * TAU;
      const x = cx + Math.cos(angle) * ringR;
      const y = cy + Math.sin(angle) * ringR;
      const color = ringColor(sys.status);
      const down = sys.status === "down";
      const heat = sys.heat || 0;
      const alive = !down && sys.status !== "unknown";

      // Tashqi halqa
      ctx.beginPath();
      ctx.arc(x, y, dialR, 0, TAU);
      ctx.strokeStyle = P.toCss(color, (down ? 1 : 0.58 + heat * 0.42) * intensity);
      ctx.lineWidth = down ? 1.8 : 1.2;
      ctx.stroke();

      // Ichki aylanuvchi yoy: ish bo'lganda tezlashadi.
      // Buzilgan bo'g'in aylanmaydi — to'xtagan siferblat darhol ko'zga tashlanadi.
      if (alive) {
        const speed = 0.6 + heat * 4.5;
        const from = t * speed + i * 1.7;
        ctx.beginPath();
        ctx.arc(x, y, dialR * 0.62, from, from + 1.5 + heat * 1.6);
        ctx.strokeStyle = P.toCss(color, (0.78 + heat * 0.22) * intensity);
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Markaziy nuqta — issiqlikka qarab yorqinlashadi
      ctx.beginPath();
      ctx.arc(x, y, 1.8 + heat * 1.6, 0, TAU);
      ctx.fillStyle = P.toCss(color, (0.6 + heat * 0.4) * intensity);
      ctx.fill();

      // Nosozlik belgisi — siferblat ustidan kesib o'tuvchi chiziq
      if (down) {
        const d = dialR * 0.48;
        ctx.strokeStyle = P.toCss(color, 0.95 * intensity);
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(x - d, y - d);
        ctx.lineTo(x + d, y + d);
        ctx.moveTo(x + d, y - d);
        ctx.lineTo(x - d, y + d);
        ctx.stroke();
      }

      // Siferblatdan yozuvga bog'lovchi chiziq va uchidagi nuqta
      const from = ringR + dialR + 2;
      const to = R * RING.labels - 5;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * from, cy + Math.sin(angle) * from);
      ctx.lineTo(cx + Math.cos(angle) * to, cy + Math.sin(angle) * to);
      ctx.strokeStyle = P.toCss(color, (down ? 0.7 : 0.42) * intensity);
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cx + Math.cos(angle) * to, cy + Math.sin(angle) * to, 1.6, 0, TAU);
      ctx.fillStyle = P.toCss(color, (down ? 0.9 : 0.6) * intensity);
      ctx.fill();

      const labelAlpha = down ? 1 : sys.status === "unknown" ? 0.4 : 0.8 + heat * 0.2;
      const labelColor = down || sys.status === "warn" ? color : P.RGB.white;
      drawLabel(
        ctx, sys.label, cx, cy, R * RING.labels, angle,
        Math.max(8, R * 0.046), P.toCss(labelColor, labelAlpha * intensity), width,
      );
    });
  }

  function drawWave(ctx, cx, cy, R, t, level, tint, intensity) {
    const base = R * RING.wave;
    ctx.beginPath();
    for (let i = 0; i <= WAVE_BARS; i++) {
      const angle = (i / WAVE_BARS) * TAU;
      // Ikki xil chastota — jonli, takrorlanmaydigan to'lqin
      const ripple =
        Math.sin(angle * 3 + t * 2.4) * 0.6 + Math.sin(angle * 6 - t * 1.7) * 0.4;
      const r = base + ripple * level * R * 0.085;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = P.toCss(tint, (0.45 + level * 0.5) * intensity);
    ctx.lineWidth = 1.8;
    ctx.stroke();
  }

  function drawCore(ctx, cx, cy, R, t, coreLevel, tint, intensity) {
    const r = R * RING.core;

    // Oq-issiq markaz — reaktor
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    g.addColorStop(0, P.toCss(P.RGB.white, 0.95 * coreLevel * intensity));
    g.addColorStop(0.35, P.toCss(tint, 0.5 * coreLevel * intensity));
    g.addColorStop(1, P.toCss(tint, 0));
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, TAU);
    ctx.fill();

    // Konsentrik halqalar
    for (const [k, alpha, width] of [[0.32, 0.8, 1.6], [0.25, 0.5, 1.1], [0.17, 0.95, 1.8]]) {
      ctx.beginPath();
      ctx.arc(cx, cy, R * k, 0, TAU);
      ctx.strokeStyle = P.toCss(tint, alpha * intensity);
      ctx.lineWidth = width;
      ctx.stroke();
    }

    // Yadro atrofidagi aylanuvchi segmentlar
    for (let i = 0; i < 8; i++) {
      const a = t * 0.4 + (i / 8) * TAU;
      ctx.beginPath();
      ctx.arc(cx, cy, R * 0.30, a, a + 0.28);
      ctx.strokeStyle = P.toCss(P.RGB.white, 0.28 * coreLevel * intensity);
      ctx.lineWidth = 2.4;
      ctx.stroke();
    }
  }

  // JARVIS yozuvi — asosiy ikonka. Uyg'onganda yorqinlashadi va biroz kattalashadi.
  function drawWordmark(ctx, cx, cy, R, mark, intensity, pulse) {
    const size = R * 0.132 * (1 + pulse * 0.05);
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `800 ${size}px ui-sans-serif, -apple-system, "SF Pro Display", system-ui, sans-serif`;
    if ("letterSpacing" in ctx) ctx.letterSpacing = `${size * 0.16}px`;

    const alpha = Math.min(1, (0.55 + mark * 0.45) * intensity);

    // Siyon nur — yozuv orqasidan yonib turadi. Uch qatlam: keng nur,
    // tor nur, so'ng toza oq harflar. Bitta qatlam qora fonda xira chiqadi.
    ctx.shadowColor = P.toCss(P.RGB.cyan, 0.95);
    ctx.shadowBlur = 26 * mark + 10;
    ctx.fillStyle = P.toCss(P.RGB.white, alpha * 0.85);
    ctx.fillText("JARVIS", cx, cy);

    ctx.shadowBlur = 10 * mark + 4;
    ctx.fillStyle = P.toCss(P.RGB.white, alpha);
    ctx.fillText("JARVIS", cx, cy);

    ctx.shadowBlur = 0;
    ctx.fillStyle = P.toCss(P.RGB.white, alpha);
    ctx.fillText("JARVIS", cx, cy);
    ctx.restore();
  }

  // ---------------------------------------------------------------- umumiy chizish

  /**
   * Bir kadr chizadi.
   *
   * @param {CanvasRenderingContext2D} ctx
   * @param {object} f — kadr ma'lumotlari:
   *   width, height, t (soniya), state, level (0..1), flash (0..1),
   *   systems: [{id, label, status, heat}]
   */
  function draw(ctx, f) {
    const { width: W, height: H } = f;
    ctx.clearRect(0, 0, W, H);

    const cx = W / 2;
    const cy = H / 2;
    const R = Math.min(W, H) / 2 - 6;

    const mood = P.STATE_MOOD[f.state] || P.STATE_MOOD.idle;
    const tint = P.mix("cyan", mood.tint, mood.blend);
    const t = f.t;

    // Chaqnash va nafas — umumiy yorqinlik
    const breath = 1 + Math.sin(t * 1.5) * 0.05 * mood.glow;
    const intensity = Math.min(1.7, (0.82 + mood.glow * 0.55) * breath + f.flash * 0.45);
    const pulse = (Math.sin(t * 2.2) + 1) / 2;

    // Nosozlik bo'lsa, chekka qizg'ish tus oladi — muammo periferiyada ko'rinadi
    const broken = (f.systems || []).some((s) => s.status === "down");
    const edgeTint = broken ? P.mix("cyan", "red", 0.7) : tint;

    ctx.lineCap = "round";

    drawGlow(ctx, cx, cy, R, tint, intensity);
    drawMotes(ctx, cx, cy, R, t, tint, intensity);
    drawSweep(ctx, cx, cy, R, t, edgeTint, intensity);
    drawTicks(ctx, cx, cy, R, t, edgeTint, intensity);
    drawBrackets(ctx, cx, cy, R, t, edgeTint, intensity);
    drawDials(ctx, cx, cy, R, t, f.systems || [], intensity, W);
    drawArcs(ctx, cx, cy, R, t, mood.spin, tint, intensity);
    drawWave(ctx, cx, cy, R, t, f.level, tint, intensity);
    drawCore(ctx, cx, cy, R, t, mood.core + f.flash * 0.35, tint, intensity);
    drawWordmark(ctx, cx, cy, R, Math.min(1, mood.mark + f.flash), intensity, pulse);
  }

  return { draw, RING };
})();

if (typeof module !== "undefined") module.exports = HUD;
