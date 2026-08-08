// Zirh chizmasi — ish stoli markazidagi figura.
//
// Simli (wireframe) uslubda chizilgan zirhli byust: dubulg'a, yelka
// qalqonlari, ko'krak va reaktor. Chiziqlar siyon, ayrim qirralar qizil
// urg'u bilan — havoladagi chizmadagidek. Hammasi 400x540 dizayn
// fazosida belgilangan, chapki yarmi o'ngga ko'zgu qilinadi.
//
// Jonli qismlari:
//   eyes  (0..1) — ko'zlar yorqinligi: «Hey Jarvis» deganda chaqnaydi
//   surge (0..1) — reaktor kuchayishi: gapirganda/uyg'onganda
//   t             — vaqt: reaktor segmentlari va nafas olish

const SUIT = (() => {
  const TAU = Math.PI * 2;
  const DW = 400; // dizayn fazosi kengligi
  const DCX = 200;

  // --- Chiziqlar: chap yarim (ko'zgu qilinadi) ---
  // pts — nuqtalar, w — qalinlik, a — shaffoflik,
  // red — qizil urg'u, close — yopiq kontur, curve — silliq egri
  const HALF = [
    // Dubulg'a tashqi konturi — kvadratroq, jag' tomon torayadi
    { pts: [[200,32],[176,35],[162,50],[155,74],[153,100],[155,124],[160,144],[168,158],[180,168],[192,173],[200,174]], curve: true, w: 2.2, a: 0.95 },
    // Yuz plastinasi ichki chizig'i
    { pts: [[200,46],[179,50],[167,63],[163,83],[163,105],[166,126],[173,144],[182,152]], curve: true, w: 1.1, a: 0.4 },
    // Quloq diski
    { pts: [[151,96],[146,104],[147,114],[153,120]], curve: true, w: 1.4, a: 0.6 },
    // Qosh plastinasi — V shaklida
    { pts: [[163,90],[187,82],[200,88]], w: 2.4, a: 0.95 },
    { pts: [[166,76],[200,72]], w: 1.2, a: 0.45 },
    // Yonoq paneli — ko'z ostidan og'iz tomon
    { pts: [[165,112],[172,132],[182,142],[189,147]], curve: true, w: 1.2, a: 0.55 },
    // Yonoq vertikal choki
    { pts: [[189,147],[189,159]], w: 1.2, a: 0.55 },
    // Jag' choki
    { pts: [[158,122],[163,143],[172,156]], curve: true, w: 1.0, a: 0.35 },
    // Bo'yin
    { pts: [[182,175],[176,198]], w: 1.5, a: 0.7 },
    // Yoqa yon tomoni
    { pts: [[148,202],[138,222]], w: 1.5, a: 0.8 },
    // Yelka qalqoni — baland va keng
    { pts: [[138,206],[96,197],[62,205],[40,225],[30,249],[28,277],[32,302]], curve: true, w: 2.2, a: 0.92 },
    // Yelka qalqoni — ichki chok
    { pts: [[138,220],[100,215],[72,227],[56,247],[52,274]], curve: true, w: 1.1, a: 0.45 },
    // Yelka qirrasi — qizil urg'u
    { pts: [[30,284],[70,294]], w: 1.5, a: 0.6, red: true },
    // Qo'l — tashqi
    { pts: [[32,304],[36,352],[40,392]], curve: true, w: 1.8, a: 0.8 },
    // Qo'l — ichki
    { pts: [[74,302],[78,348],[80,386]], curve: true, w: 1.1, a: 0.45 },
    // Bilaguzuk chizig'i
    { pts: [[38,356],[80,350]], w: 1.1, a: 0.45 },
    // Ko'krak plastinasi
    { pts: [[146,224],[198,224],[198,246],[192,284],[154,274],[146,250]], close: true, w: 1.6, a: 0.85 },
    // Ko'krak osti — qizil urg'u
    { pts: [[154,276],[190,286]], w: 1.6, a: 0.65, red: true },
    // Yon qiyshiq chok — qizil urg'u
    { pts: [[148,292],[162,346]], w: 1.4, a: 0.5, red: true },
    // Qorin yon tomoni
    { pts: [[152,284],[158,318],[162,356],[170,398],[176,428]], curve: true, w: 1.6, a: 0.8 },
    // Bel plastinasi diagonali
    { pts: [[166,366],[186,402]], w: 1.0, a: 0.3 },
  ];

  // --- To'liq (ko'zgusiz) chiziqlar ---
  const FULL = [
    // Yoqa
    { pts: [[148,202],[252,202]], w: 1.5, a: 0.8 },
    { pts: [[138,222],[262,222]], w: 1.5, a: 0.8 },
    // Og'iz tirqishi
    { pts: [[189,151],[211,151]], w: 2.2, a: 0.85 },
    // Iyak osti chizig'i
    { pts: [[191,163],[209,163]], w: 1.1, a: 0.45 },
    // Qorin choklari
    { pts: [[164,324],[200,330],[236,324]], curve: true, w: 1.1, a: 0.45 },
    { pts: [[168,356],[200,362],[232,356]], curve: true, w: 1.1, a: 0.45 },
    { pts: [[174,392],[200,398],[226,392]], curve: true, w: 1.1, a: 0.45 },
    // Ko'krak markaziy choki
    { pts: [[200,224],[200,254]], w: 1.1, a: 0.45 },
    // Pastki qirra
    { pts: [[180,430],[200,436],[220,430]], curve: true, w: 1.4, a: 0.55 },
  ];

  // Ko'z tirqishi: chap (ko'zgu qilinadi)
  // Ko'z tirqishi burchaklari (chap): tashqi tomoni biroz yuqoriroq
  const EYE = { pts: [[166,97],[190,95],[190,103],[166,106]] };

  const REACTOR = { x: 200, y: 288, r: 24 };

  function path(ctx, pts, sx, sy, curve, close, mirror) {
    const X = (p) => sx(mirror ? DW - p[0] : p[0]);
    ctx.beginPath();
    ctx.moveTo(X(pts[0]), sy(pts[0][1]));
    if (curve && pts.length > 2) {
      // Nuqtalar orasini o'rta nuqtalar orqali silliqlash
      for (let i = 1; i < pts.length - 1; i++) {
        const mx = (pts[i][0] + pts[i + 1][0]) / 2;
        const my = (pts[i][1] + pts[i + 1][1]) / 2;
        ctx.quadraticCurveTo(X(pts[i]), sy(pts[i][1]), sx(mirror ? DW - mx : mx), sy(my));
      }
      const last = pts[pts.length - 1];
      ctx.lineTo(X(last), sy(last[1]));
    } else {
      for (let i = 1; i < pts.length; i++) ctx.lineTo(X(pts[i]), sy(pts[i][1]));
    }
    if (close) ctx.closePath();
    ctx.stroke();
  }

  function drawEye(ctx, sx, sy, s, eyes, mirror) {
    const X = (p) => sx(mirror ? DW - p[0] : p[0]);
    ctx.save();
    ctx.shadowColor = P.toCss(P.RGB.cyan, 0.95);
    ctx.shadowBlur = (6 + eyes * 28) * s;

    const c = EYE.pts;
    const g = ctx.createLinearGradient(X(c[0]), sy(c[0][1]), X(c[1]), sy(c[1][1]));
    g.addColorStop(0, P.toCss(P.RGB.cyan, 0.55 + eyes * 0.45));
    g.addColorStop(0.5, P.toCss(P.RGB.white, 0.65 + eyes * 0.35));
    g.addColorStop(1, P.toCss(P.RGB.cyan, 0.55 + eyes * 0.45));
    ctx.fillStyle = g;

    ctx.beginPath();
    ctx.moveTo(X(c[0]), sy(c[0][1]));
    for (let i = 1; i < c.length; i++) ctx.lineTo(X(c[i]), sy(c[i][1]));
    ctx.closePath();
    ctx.fill();
    // Ikkinchi qatlam — markaz oq-issiq bo'lsin
    ctx.fill();
    ctx.restore();
  }

  function drawReactor(ctx, sx, sy, s, t, surge) {
    const x = sx(REACTOR.x);
    const y = sy(REACTOR.y);
    const r = REACTOR.r * s;
    const bright = 0.55 + surge * 0.45;

    // Nur
    const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 2.2);
    glow.addColorStop(0, P.toCss(P.RGB.white, 0.5 * bright));
    glow.addColorStop(0.35, P.toCss(P.RGB.cyan, 0.28 * bright));
    glow.addColorStop(1, P.toCss(P.RGB.cyan, 0));
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, r * 2.2, 0, TAU);
    ctx.fill();

    // Tashqi va ichki halqa
    for (const [k, w, a] of [[1, 2, 0.95], [0.42, 1.2, 0.8]]) {
      ctx.beginPath();
      ctx.arc(x, y, r * k, 0, TAU);
      ctx.strokeStyle = P.toCss(P.RGB.cyan, a * bright);
      ctx.lineWidth = w * s;
      ctx.stroke();
    }

    // Aylanuvchi segmentlar — reaktorning "tirik" qismi
    const spin = t * (0.5 + surge * 1.6);
    ctx.lineWidth = Math.max(2.5 * s, 2);
    for (let i = 0; i < 10; i++) {
      const a0 = spin + (i / 10) * TAU;
      ctx.beginPath();
      ctx.arc(x, y, r * 0.72, a0, a0 + 0.38);
      ctx.strokeStyle = P.toCss(P.RGB.white, (0.35 + surge * 0.55) * (i % 2 ? 0.6 : 1));
      ctx.stroke();
    }

    // Markaziy nuqta
    ctx.beginPath();
    ctx.arc(x, y, r * 0.2, 0, TAU);
    ctx.fillStyle = P.toCss(P.RGB.white, 0.85 + surge * 0.15);
    ctx.fill();
  }

  /**
   * Zirh byustini chizadi.
   * @param {object} o — {cx, topY, height, t, eyes, surge}
   *   cx — markaz X; topY — dubulg'a tepasi Y; height — byust balandligi
   */
  function draw(ctx, o) {
    const s = o.height / 540;
    const left = o.cx - DCX * s;
    const sx = (x) => left + x * s;
    const sy = (y) => o.topY + y * s;

    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    // Nafas olish — butun figura juda sekin "tirik" turadi
    const breathe = 1 + Math.sin(o.t * 0.9) * 0.012;

    for (const mirror of [false, true]) {
      for (const line of HALF) {
        const color = line.red ? P.RGB.red : P.RGB.cyan;
        ctx.strokeStyle = P.toCss(color, line.a * breathe * (line.red ? 0.9 : 1));
        ctx.lineWidth = line.w * s;
        path(ctx, line.pts, sx, sy, line.curve, line.close, mirror);
      }
    }
    for (const line of FULL) {
      ctx.strokeStyle = P.toCss(P.RGB.cyan, line.a * breathe);
      ctx.lineWidth = line.w * s;
      path(ctx, line.pts, sx, sy, line.curve, line.close, false);
    }

    drawEye(ctx, sx, sy, s, o.eyes, false);
    drawEye(ctx, sx, sy, s, o.eyes, true);
    drawReactor(ctx, sx, sy, s, o.t, o.surge);

    ctx.restore();
  }

  // Reaktor markazining ekran koordinatasi — orqa halqalarni shu yerga qo'yish uchun
  function reactorAt(o) {
    const s = o.height / 540;
    return { x: o.cx, y: o.topY + REACTOR.y * s };
  }

  return { draw, reactorAt };
})();

if (typeof module !== "undefined") module.exports = SUIT;
