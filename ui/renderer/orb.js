// Orb boshqaruvchisi — yadro bilan aloqa, holat va kadrlar sikli.
// Chizishning o'zi `hud.js` da; bu fayl unga nima chizishni aytadi.

const CANVAS = document.getElementById("orb");
const CTX = CANVAS.getContext("2d");

const orbWrap = document.getElementById("orb-wrap");
const statusDot = document.getElementById("status-dot");
const caption = document.getElementById("caption");
const captionRole = document.getElementById("caption-role");
const captionText = document.getElementById("caption-text");
const confirmPanel = document.getElementById("confirm");
const confirmAction = document.getElementById("confirm-action");
const confirmDetail = document.getElementById("confirm-detail");
const offlinePanel = document.getElementById("offline");
const tooltip = document.getElementById("dial-tip");

let state = "idle";
let level = 0;        // yadrodan kelgan xom daraja
let smoothLevel = 0;  // silliqlangan — animatsiya sakramasin
let flash = 0;        // uyg'onganda qisqa chaqnash
let systems = [];     // bo'g'inlar holati (HUD siferblatlari)

let width = 0;
let height = 0;

let socket = null;
let pendingConfirmId = null;
let captionTimer = null;

// ---------------------------------------------------------------- Kadrlar sikli

function applySize() {
  // O'lchamni main jarayoni beradi (JARVIS_ORB_SIZE). CSS uni `--orb`
  // orqali oladi, canvas esa o'z CSS o'lchamidan — ya'ni bitta manba.
  const size = Number(window.orb.size) || 150;
  document.documentElement.style.setProperty("--orb", `${size}px`);
}

function setupCanvas() {
  const dpr = window.devicePixelRatio || 1;
  width = CANVAS.clientWidth || 150;
  height = CANVAS.clientHeight || 150;
  CANVAS.width = Math.round(width * dpr);
  CANVAS.height = Math.round(height * dpr);
  CTX.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function frame(now) {
  const t = now / 1000;

  // Daraja silliqlanadi: ko'tarilishi tez, tushishi sekin — nutq tabiiy ko'rinadi
  const rise = level > smoothLevel ? 0.35 : 0.08;
  smoothLevel += (level - smoothLevel) * rise;

  // Chaqnash so'nishi
  flash *= 0.92;
  if (flash < 0.01) flash = 0;

  HUD.draw(CTX, {
    width,
    height,
    t,
    state,
    level: smoothLevel,
    flash,
    systems,
  });

  requestAnimationFrame(frame);
}

// ---------------------------------------------------------------- Holat

function setState(next) {
  if (next === "wake" && state !== "wake") flash = 1;
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
    document.body.classList.remove("standby");
    // Aloqa yo'q — bo'g'inlar holati endi ishonchsiz, siferblatlar so'nsin.
    systems = systems.map((s) => ({ ...s, status: "unknown", heat: 0 }));
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
    case "health":
      systems = data.systems || [];
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
    // Sukut holati: yadro baribir tinglab turadi, faqat orb so'nadi.
    // Bosish yoki chaqirish bilan darhol qaytadi.
    case "standby":
      document.body.classList.toggle("standby", !!data.on);
      break;
  }
}

// ---------------------------------------------------------------- Siferblat izohi

// Sichqoncha siferblat ustiga kelganda nima buzilganini ko'rsatadi —
// qizil doiraning sababini bilish uchun jurnal ochish shart bo'lmasin.
function dialAt(clientX, clientY) {
  if (!systems.length) return null;
  const box = CANVAS.getBoundingClientRect();
  const cx = box.left + box.width / 2;
  const cy = box.top + box.height / 2;
  const R = Math.min(box.width, box.height) / 2 - 6;
  const ringR = R * HUD.RING.dials;
  const hitR = R * 0.1;

  for (let i = 0; i < systems.length; i++) {
    const angle = -Math.PI / 2 + (i / systems.length) * Math.PI * 2;
    const dx = clientX - (cx + Math.cos(angle) * ringR);
    const dy = clientY - (cy + Math.sin(angle) * ringR);
    if (dx * dx + dy * dy <= hitR * hitR) return systems[i];
  }
  return null;
}

const STATUS_TEXT = {
  unknown: "hali ishlatilmagan",
  ready: "tayyor",
  active: "ishlayapti",
  warn: "e'tibor talab qiladi",
  down: "ishlamayapti",
};

function updateTooltip(event) {
  const dial = dialAt(event.clientX, event.clientY);
  if (!dial) {
    tooltip.classList.add("hidden");
    return null;
  }
  const status = STATUS_TEXT[dial.status] || dial.status;
  tooltip.textContent = dial.detail ? `${dial.label} — ${status}: ${dial.detail}`
                                    : `${dial.label} — ${status}`;
  tooltip.classList.toggle("bad", dial.status === "down" || dial.status === "warn");
  tooltip.classList.remove("hidden");
  return dial;
}

// ---------------------------------------------------------------- Foydalanuvchi harakatlari

// --- Sudrab ko'chirish ---
//
// Orb ham bosiladi (Jarvisni chaqirish), ham sudraladi. Ikkisini ajratish
// uchun chegara: sichqoncha shu masofadan ko'p siljisa — bu sudrash, kamroq
// siljisa — bosish. Aks holda har bir bosishda oyna bir-ikki piksel siljib
// ketardi yoki sudrash chaqiruvni ishga tushirardi.
const DRAG_THRESHOLD = 4;

let dragging = false;
let moved = 0;
let lastScreen = null;

orbWrap.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  dragging = true;
  moved = 0;
  lastScreen = { x: event.screenX, y: event.screenY };
  // Kursor orbdan chiqib ketsa ham hodisalar shu elementga kelaveradi —
  // oyna kursor ostidan siljiganda bu shart.
  orbWrap.setPointerCapture(event.pointerId);
});

orbWrap.addEventListener("pointermove", (event) => {
  if (!dragging || !lastScreen) return;
  const dx = event.screenX - lastScreen.x;
  const dy = event.screenY - lastScreen.y;
  lastScreen = { x: event.screenX, y: event.screenY };
  moved += Math.abs(dx) + Math.abs(dy);
  if (moved < DRAG_THRESHOLD) return;

  document.body.classList.add("dragging");
  // Ekran koordinatalaridagi farq — oyna siljigani hisobga ta'sir qilmaydi.
  window.orb.drag(dx, dy);
});

orbWrap.addEventListener("pointerup", (event) => {
  if (!dragging) return;
  dragging = false;
  lastScreen = null;
  orbWrap.releasePointerCapture(event.pointerId);
  document.body.classList.remove("dragging");

  if (moved < DRAG_THRESHOLD) {
    send({ type: "activate" });
  } else {
    window.orb.dragEnd();
  }
});

orbWrap.addEventListener("pointercancel", () => {
  dragging = false;
  lastScreen = null;
  document.body.classList.remove("dragging");
});

document.getElementById("approve").addEventListener("click", () => answerConfirm(true));
document.getElementById("deny").addEventListener("click", () => answerConfirm(false));

document.addEventListener("keydown", (event) => {
  if (!pendingConfirmId) return;
  if (event.key === "Enter") answerConfirm(true);
  if (event.key === "Escape") answerConfirm(false);
});

// Oyna bo'sh joyi bosishlarni o'tkazib yuborsin, faqat interaktiv elementlar ushlasin.
document.addEventListener("mousemove", (event) => {
  updateTooltip(event);
  const target = document.elementFromPoint(event.clientX, event.clientY);
  const interactive = Boolean(target && target.closest(".interactive"));
  // Sudrash paytida kursor orbdan chiqib ketishi mumkin — o'sha payt oynani
  // "o'tkazuvchan" qilib qo'ysak, sudrash yarmida uzilib qolardi.
  window.orb.setInteractive(interactive || dragging || Boolean(pendingConfirmId));
});

document.addEventListener("mouseleave", () => {
  tooltip.classList.add("hidden");
  if (!pendingConfirmId && !dragging) window.orb.setInteractive(false);
});

window.orb.onHotkey(() => send({ type: "activate" }));

window.addEventListener("resize", setupCanvas);

applySize();
setupCanvas();
connect();
requestAnimationFrame(frame);
