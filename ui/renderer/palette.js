// Ranglar — bitta joyda.
//
// Iron Man HUD'ining rangi "dasturchi ko'ki" emas: u feruza-siyon, qora ustida
// yonib turadi va markazi oq-issiq. Farq shundaki, ko'k (#3B82F6) rang doirasida
// ~217° da yotadi, siyon esa ~187° da — va u har doim to'liq to'yingan.
// Shu farq butun ko'rinishni belgilaydi.

const P = (() => {
  const RGB = {
    cyan: [34, 227, 255],     // #22E3FF — asosiy chiziqlar
    cyanDeep: [0, 150, 196],  // chuqurroq soya, gradientlar uchun
    white: [236, 253, 255],   // oq-issiq yadro va yozuvlar
    amber: [255, 178, 62],    // ogohlantirish
    red: [255, 68, 58],       // nosozlik
    slate: [96, 126, 140],    // hali ishlatilmagan / o'chiq
  };

  // Ikki rang orasidagi oraliq — holat o'zgarganda rang sakramasin.
  function mix(a, b, t) {
    const A = RGB[a];
    const B = RGB[b];
    const k = Math.max(0, Math.min(1, t));
    return [
      Math.round(A[0] + (B[0] - A[0]) * k),
      Math.round(A[1] + (B[1] - A[1]) * k),
      Math.round(A[2] + (B[2] - A[2]) * k),
    ];
  }

  function toCss(color, alpha = 1) {
    const [r, g, b] = color;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  // Bo'g'in holati -> rang. Siferblatlar shu jadval bo'yicha bo'yaladi.
  const STATUS_COLOR = {
    unknown: "slate",
    ready: "cyan",
    active: "white",
    warn: "amber",
    down: "red",
  };

  // Jarvis holati -> harakat xarakteri. Rang deyarli har doim siyon bo'lib
  // qoladi; faqat tasdiq va xato uni sariq/qizilga suradi.
  //   glow — umumiy yorqinlik, spin — yoylar tezligi,
  //   core — yadro yorqinligi, mark — JARVIS yozuvining ko'rinishi
  const STATE_MOOD = {
    idle:      { tint: "cyan",  blend: 0.00, glow: 0.38, spin: 0.14, core: 0.38, mark: 0.42 },
    wake:      { tint: "white", blend: 0.30, glow: 1.00, spin: 1.70, core: 1.00, mark: 1.00 },
    listening: { tint: "cyan",  blend: 0.25, glow: 0.78, spin: 0.44, core: 0.66, mark: 0.85 },
    thinking:  { tint: "cyan",  blend: 0.10, glow: 0.66, spin: 1.45, core: 0.50, mark: 0.60 },
    speaking:  { tint: "white", blend: 0.18, glow: 0.90, spin: 0.32, core: 0.80, mark: 0.95 },
    confirm:   { tint: "amber", blend: 0.90, glow: 0.86, spin: 0.20, core: 0.70, mark: 0.75 },
    error:     { tint: "red",   blend: 0.90, glow: 0.88, spin: 0.14, core: 0.72, mark: 0.70 },
  };

  return { RGB, mix, toCss, STATUS_COLOR, STATE_MOOD };
})();

if (typeof module !== "undefined") module.exports = P;
