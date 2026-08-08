// Orb — Jarvis'ning ko'rinadigan yuzi.
//
// Chizish 2D canvas'da: konsentrik halqalar, aylanuvchi yoylar, ovozga javob
// beradigan to'lqin va markazdagi yadro. Har bir holat o'z rangi va tezligiga ega,
// shuning uchun ekranga bir qarabroq Jarvis nima qilayotgani tushuniladi.

const CANVAS = document.getElementById("orb");
const CTX = CANVAS.getContext("2d");

// Har bir holat uchun rang va harakat xarakteri.
const PALETTE = {
  idle:      { hue: 190, glow: 0.30, spin: 0.12, pulse: 0.30, core: 0.32 },
  wake:      { hue: 190, glow: 1.00, spin: 1.60, pulse: 1.00, core: 1.00 },
  listening: { hue: 190, glow: 0.72, spin: 0.42, pulse: 0.55, core: 0.62 },
  thinking:  { hue: 205, glow: 0.62, spin: 1.35, pulse: 0.42, core: 0.48 },
  speaking:  { hue: 186, glow: 0.85, spin: 0.30, pulse: 0.70, core: 0.75 },
  confirm:   { hue: 38,  glow: 0.80, spin: 0.20, pulse: 0.62, core: 0.68 },
  error:     { hue: 2,   glow: 0.85, spin: 0.16, pulse: 0.80, core: 0.70 },
};

// Aylanuvchi yoylar: radius ulushi, boshlanish burchagi, uzunlik, tezlik, qalinlik.
// Qarama-qarshi yo'nalishdagi tezliklar HUD ko'rinishini beradi.
const ARCS = [
  { r: 0.92, start: 0.00, sweep: 1.25, speed:  0.55, width: 1.6, alpha: 0.75 },
  { r: 0.92, start: 3.30, sweep: 0.70, speed:  0.55, width: 1.6, alpha: 0.45 },
  { r: 0.79, start: 1.60, sweep: 2.10, speed: -0.34, width: 2.4, alpha: 0.65 },
  { r: 0.66, start: 4.20, sweep: 1.05, speed:  0.85, width: 1.3, alpha: 0.55 },
];

const TICK_COUNT = 48;
const WAVE_BARS = 64;

let state = "idle";
let level = 0;        // yadrodan kelgan xom daraja
let smoothLevel = 0;  // silliqlangan — animatsiya sakramasligi uchun
let hue = PALETTE.idle.hue;
let glow = PALETTE.idle.glow;
let flash = 0;        // uyg'onganda qisqa chaqnash

let width = 240;
let height = 240;

function setupCanvas() {
  const dpr = window.devicePixelRatio || 1;
  width = CANVAS.clientWidth || 240;
  height = CANVAS.clientHeight || 240;
  CANVAS.width = Math.round(width * dpr);
  CANVAS.height = Math.round(height * dpr);
  CTX.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

// Burchaklarni eng qisqa yo'l bilan aralashtiramiz (190° -> 2° orqaga ketmasin).
function lerpHue(a, b, t) {
  let delta = ((b - a + 540) % 360) - 180;
  return (a + delta * t + 360) % 360;
}

function stroke(color, lineWidth) {
  CTX.strokeStyle = color;
  CTX.lineWidth = lineWidth;
  CTX.stroke();
}

function draw(time) {
  const p = PALETTE[state] || PALETTE.idle;
  const t = time / 1000;

  // Holat o'zgarganda rang va yorqinlik silliq o'tsin.
  hue = lerpHue(hue, p.hue, 0.08);
  glow = lerp(glow, p.glow, 0.08);
  smoothLevel = lerp(smoothLevel, level, 0.22);
  flash *= 0.9;

  const cx = width / 2;
  const cy = height / 2;
  const base = Math.min(width, height) / 2 - 14;

  // Nafas olish: sekin pulsatsiya + ovoz darajasi.
  const breath = 1 + Math.sin(t * 1.7) * 0.02 * p.pulse;
  const energy = Math.min(1, smoothLevel * 1.4);
  const radius = base * breath;
  const intensity = Math.min(1, glow + flash + energy * 0.35);

  CTX.clearRect(0, 0, width, height);
  CTX.save();
  // Yorug'liklar qo'shilib yorishsin — neon effekti shundan chiqadi.
  CTX.globalCompositeOperation = "lighter";

  drawGlow(cx, cy, radius, intensity);
  drawTicks(cx, cy, radius, t, intensity);
  drawArcs(cx, cy, radius, t, p.spin, intensity);
  drawWave(cx, cy, radius, t, energy, intensity);
  drawCore(cx, cy, radius, t, p.core, energy, intensity);
  drawScan(cx, cy, radius, t, intensity);

  CTX.restore();
  requestAnimationFrame(draw);
}

function drawGlow(cx, cy, radius, intensity) {
  const gradient = CTX.createRadialGradient(cx, cy, radius * 0.1, cx, cy, radius * 1.5);
  gradient.addColorStop(0, `hsla(${hue}, 100%, 62%, ${0.20 * intensity})`);
  gradient.addColorStop(0.55, `hsla(${hue}, 100%, 55%, ${0.07 * intensity})`);
  gradient.addColorStop(1, "hsla(0, 0%, 0%, 0)");
  CTX.fillStyle = gradient;
  CTX.beginPath();
  CTX.arc(cx, cy, radius * 1.5, 0, Math.PI * 2);
  CTX.fill();
}

function drawTicks(cx, cy, radius, t, intensity) {
  // Sekin aylanadigan shkala — masshtab hissini beradi.
  const spin = t * 0.06;
  for (let i = 0; i < TICK_COUNT; i++) {
    const angle = spin + (i / TICK_COUNT) * Math.PI * 2;
    const major = i % 6 === 0;
    const inner = radius * (major ? 0.99 : 1.01);
    const outer = radius * (major ? 1.09 : 1.05);
    CTX.beginPath();
    CTX.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
    CTX.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
    stroke(
      `hsla(${hue}, 100%, 70%, ${(major ? 0.5 : 0.2) * intensity})`,
      major ? 1.4 : 0.9
    );
  }
}

function drawArcs(cx, cy, radius, t, spin, intensity) {
  CTX.lineCap = "round";
  for (const arc of ARCS) {
    const angle = arc.start + t * arc.speed * spin * 2.2;
    CTX.beginPath();
    CTX.arc(cx, cy, radius * arc.r, angle, angle + arc.sweep);
    stroke(`hsla(${hue}, 100%, 66%, ${arc.alpha * intensity})`, arc.width);
  }
  CTX.lineCap = "butt";

  // Ichki uzluksiz halqa — kompozitsiyani ushlab turadi.
  CTX.beginPath();
  CTX.arc(cx, cy, radius * 0.55, 0, Math.PI * 2);
  stroke(`hsla(${hue}, 100%, 60%, ${0.22 * intensity})`, 1);
}

function drawWave(cx, cy, radius, t, energy, intensity) {
  // Tinglash va gapirishda ovozga javob beradigan radial to'lqin.
  if (state !== "listening" && state !== "speaking") return;

  const inner = radius * 0.60;
  for (let i = 0; i < WAVE_BARS; i++) {
    const angle = (i / WAVE_BARS) * Math.PI * 2;
    // Ikki xil chastotali sinus — jonli, takrorlanmaydigan naqsh beradi.
    const noise =
      Math.sin(i * 0.7 + t * 5.5) * 0.5 + Math.sin(i * 1.9 - t * 3.1) * 0.5;
    const amplitude = radius * 0.16 * energy * (0.45 + 0.55 * Math.abs(noise));
    const outer = inner + Math.max(1.5, amplitude);

    CTX.beginPath();
    CTX.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
    CTX.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
    stroke(`hsla(${hue}, 100%, 72%, ${(0.30 + energy * 0.5) * intensity})`, 1.8);
  }
}

function drawCore(cx, cy, radius, t, coreLevel, energy, intensity) {
  const pulse = 1 + Math.sin(t * 2.6) * 0.06 + energy * 0.16;
  const r = radius * 0.30 * pulse;

  const gradient = CTX.createRadialGradient(cx, cy, 0, cx, cy, r);
  gradient.addColorStop(0, `hsla(${hue}, 100%, 92%, ${0.95 * coreLevel * intensity})`);
  gradient.addColorStop(0.45, `hsla(${hue}, 100%, 68%, ${0.55 * coreLevel * intensity})`);
  gradient.addColorStop(1, "hsla(0, 0%, 0%, 0)");
  CTX.fillStyle = gradient;
  CTX.beginPath();
  CTX.arc(cx, cy, r, 0, Math.PI * 2);
  CTX.fill();

  // "O'ylash" holatida yadro atrofida tez aylanuvchi nuqta.
  if (state === "thinking") {
    const angle = t * 3.4;
    const orbit = radius * 0.42;
    CTX.beginPath();
    CTX.arc(cx + Math.cos(angle) * orbit, cy + Math.sin(angle) * orbit, 2.6, 0, Math.PI * 2);
    CTX.fillStyle = `hsla(${hue}, 100%, 88%, ${0.9 * intensity})`;
    CTX.fill();
  }
}

function drawScan(cx, cy, radius, t, intensity) {
  // Sekin aylanuvchi radar nuri — orb "tirik" ko'rinadi.
  const angle = (t * 0.5) % (Math.PI * 2);
  const gradient = CTX.createLinearGradient(
    cx, cy,
    cx + Math.cos(angle) * radius,
    cy + Math.sin(angle) * radius
  );
  gradient.addColorStop(0, "hsla(0, 0%, 0%, 0)");
  gradient.addColorStop(1, `hsla(${hue}, 100%, 78%, ${0.16 * intensity})`);

  CTX.beginPath();
  CTX.moveTo(cx, cy);
  CTX.arc(cx, cy, radius, angle - 0.18, angle + 0.18);
  CTX.closePath();
  CTX.fillStyle = gradient;
  CTX.fill();
}

// ---------------------------------------------------------------- UI elementlari

const orbWrap = document.getElementById("orb-wrap");
const statusDot = document.getElementById("status-dot");
const caption = document.getElementById("caption");
const captionRole = document.getElementById("caption-role");
const captionText = document.getElementById("caption-text");
const confirmPanel = document.getElementById("confirm");
const confirmAction = document.getElementById("confirm-action");
const confirmDetail = document.getElementById("confirm-detail");
const offlinePanel = document.getElementById("offline");

let socket = null;
let pendingConfirmId = null;
let captionTimer = null;

function setState(next) {
  if (next === "wake") flash = 1;
  state = next;
}

function showCaption(role, text) {
  captionRole.textContent = role;
  captionText.textContent = text;
  caption.classList.remove("hidden");
  clearTimeout(captionTimer);
  // Matn ekranda abadiy qolmasin.
  captionTimer = setTimeout(() => caption.classList.add("hidden"), 9000);
}

function showConfirm(id, action, detail) {
  pendingConfirmId = id;
  confirmAction.textContent = action;
  confirmDetail.textContent = detail;
  confirmPanel.classList.remove("hidden");
  // Klaviatura yorliqlari ishlashi uchun oyna fokus olishi kerak.
  window.orb.setFocusable(true);
  window.orb.setInteractive(true);
}

function hideConfirm() {
  pendingConfirmId = null;
  confirmPanel.classList.add("hidden");
  window.orb.setFocusable(false);
}

function answerConfirm(approved) {
  if (!pendingConfirmId) return;
  send({ type: "confirm_result", id: pendingConfirmId, approved });
  hideConfirm();
}

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
  }
}

// ---------------------------------------------------------------- Yadro bilan aloqa

function connect() {
  socket = new WebSocket(window.orb.coreUrl);

  socket.addEventListener("open", () => {
    statusDot.classList.remove("offline");
    offlinePanel.classList.add("hidden");
  });

  socket.addEventListener("message", (event) => {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch {
      return;
    }
    handleEvent(data);
  });

  socket.addEventListener("close", () => {
    statusDot.classList.add("offline");
    offlinePanel.classList.remove("hidden");
    setState("idle");
    level = 0;
    // Yadro qayta ishga tushsa, o'zi ulanib olsin.
    setTimeout(connect, 1500);
  });

  socket.addEventListener("error", () => socket.close());
}

function handleEvent(data) {
  switch (data.type) {
    case "state":
      setState(data.state);
      if (data.state !== "confirm") hideConfirm();
      break;
    case "level":
      level = data.value;
      break;
    case "transcript":
      showCaption("Siz", data.text);
      break;
    case "say":
      showCaption("Jarvis", data.text);
      break;
    case "confirm":
      showConfirm(data.id, data.action, data.detail);
      break;
    case "confirm_closed":
      hideConfirm();
      break;
    case "log":
      if (data.level === "error" || data.level === "warn") {
        showCaption("Tizim", data.text);
      }
      break;
  }
}

// ---------------------------------------------------------------- Foydalanuvchi harakatlari

orbWrap.addEventListener("click", () => send({ type: "activate" }));

document.getElementById("approve").addEventListener("click", () => answerConfirm(true));
document.getElementById("deny").addEventListener("click", () => answerConfirm(false));

document.addEventListener("keydown", (event) => {
  if (!pendingConfirmId) return;
  if (event.key === "Enter") answerConfirm(true);
  if (event.key === "Escape") answerConfirm(false);
});

// Oyna bo'sh joyi bosishlarni o'tkazib yuborsin, faqat interaktiv elementlar ushlasin.
// Buni sichqoncha harakatini kuzatib hal qilamiz.
document.addEventListener("mousemove", (event) => {
  const target = document.elementFromPoint(event.clientX, event.clientY);
  const interactive = Boolean(target && target.closest(".interactive"));
  window.orb.setInteractive(interactive || Boolean(pendingConfirmId));
});

document.addEventListener("mouseleave", () => {
  if (!pendingConfirmId) window.orb.setInteractive(false);
});

window.orb.onHotkey(() => send({ type: "activate" }));

window.addEventListener("resize", setupCanvas);

setupCanvas();
connect();
requestAnimationFrame(draw);
