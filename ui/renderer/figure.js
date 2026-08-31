// Foydalanuvchi rasmi ustidagi jonli qatlam.
//
// Sahnaning o'zi to'liq chiziladi (shell.js). Lekin foydalanuvchi markazga
// o'z rasmini qo'yishi mumkin — masalan eski wallpaperini. Shunda rasmning
// ko'zlari va reaktori "yonishi" kerak: rasm o'zi qimirlamaydi, ustiga
// nur qo'shamiz. Nuqtalar uch marta bosib sozlanadi (rasmga nisbatan
// 0..1 koordinatalar).

const DESK = (() => {
  const TAU = Math.PI * 2;

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

  return { drawFigureFx };
})();

if (typeof module !== "undefined") module.exports = DESK;
