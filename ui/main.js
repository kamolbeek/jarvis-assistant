// Jarvis orb — ekranda doim ustida turadigan suzuvchi oyna.
//
// Uchta narsa muhim:
//   1. Oyna shaffof va ramkasiz — faqat orb ko'rinadi.
//   2. Barcha ish stollarida va to'liq ekran ilovalar ustida ko'rinadi.
//   3. Bo'sh joyi "o'tkazuvchan" — orbdan tashqarisiga bosilsa, bosish ostidagi
//      ilovaga o'tadi. Aks holda orb ekranning bir qismini bloklab qo'yardi.

const { app, BrowserWindow, ipcMain, screen, globalShortcut } = require("electron");
const path = require("node:path");

// Orbning o'lchami. Kichik bo'lishi kerak — u ish stolining bir burchagida
// turadi va ishga xalaqit bermasligi shart. Oyna orbdan kattaroq: pastida
// izoh va tasdiq tugmalari uchun joy kerak, lekin o'sha qism shaffof va
// bosishlarni o'tkazib yuboradi.
const ORB_SIZE = Math.max(80, Math.min(320, Number(process.env.JARVIS_ORB_SIZE) || 150));
const WINDOW_WIDTH = Math.max(300, ORB_SIZE + 40);
const WINDOW_HEIGHT = ORB_SIZE + 170;
const MARGIN = 24;

let win = null;

// Foydalanuvchi orbni sudrab ko'chirsa, joyi eslab qolinadi — har ishga
// tushirishda uni qaytadan surishga majbur qilmaymiz.
const ORB_STATE = () => path.join(app.getPath("userData"), "orb-position.json");

function savedPosition() {
  try {
    const raw = JSON.parse(fs.readFileSync(ORB_STATE(), "utf8"));
    if (Number.isFinite(raw.x) && Number.isFinite(raw.y)) return raw;
  } catch { /* birinchi ishga tushirish — saqlangan joy yo'q */ }
  return null;
}

function savePosition() {
  if (!win) return;
  const [x, y] = win.getPosition();
  try {
    fs.writeFileSync(ORB_STATE(), JSON.stringify({ x, y }));
  } catch { /* saqlanmasa ham ishlashda davom etamiz */ }
}

// Orb ekrandan butunlay chiqib ketmasligi kerak — aks holda uni qaytarib
// bo'lmaydi. Har doim kamida bir qismi ko'rinib turadi.
function clamp(x, y) {
  const area = screen.getDisplayNearestPoint({ x, y }).workArea;
  const keep = 60;
  return {
    x: Math.round(Math.min(Math.max(x, area.x - WINDOW_WIDTH + keep),
                           area.x + area.width - keep)),
    y: Math.round(Math.min(Math.max(y, area.y), area.y + area.height - keep)),
  };
}

function positionFor(position, display) {
  const { x, y, width, height } = display.workArea;
  const right = x + width - WINDOW_WIDTH - MARGIN;
  const bottom = y + height - WINDOW_HEIGHT - MARGIN;

  switch (position) {
    case "bottom-left":
      return { x: x + MARGIN, y: bottom };
    case "top-right":
      return { x: right, y: y + MARGIN };
    case "top-left":
      return { x: x + MARGIN, y: y + MARGIN };
    case "center":
      return {
        x: Math.round(x + (width - WINDOW_WIDTH) / 2),
        y: Math.round(y + (height - WINDOW_HEIGHT) / 2),
      };
    default:
      return { x: right, y: bottom };
  }
}

function createWindow() {
  const display = screen.getPrimaryDisplay();
  const position = process.env.JARVIS_ORB_POSITION || "bottom-right";
  // Saqlangan joy ustun: foydalanuvchi bir marta surib qo'ygan bo'lsa,
  // keyingi safar o'sha yerda turishi kerak.
  const { x, y } = savedPosition() || positionFor(position, display);

  win = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    x,
    y,
    frame: false,
    transparent: true,
    hasShadow: false,
    resizable: false,
    movable: true,
    skipTaskbar: true,
    // Dock'da ko'rinmasin va boshqa oynadan fokusni tortib olmasin.
    focusable: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // "screen-saver" darajasi to'liq ekran ilovalar ustida ham ko'rinishini ta'minlaydi.
  win.setAlwaysOnTop(true, "screen-saver");
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  // Standart holat: bosishlar o'tib ketadi. Sichqoncha orb ustiga kelganda
  // renderer bizga xabar beradi va biz vaqtincha o'chiramiz.
  win.setIgnoreMouseEvents(true, { forward: true });

  win.loadFile(path.join(__dirname, "renderer", "index.html"));

  if (process.argv.includes("--dev")) {
    win.webContents.openDevTools({ mode: "detach" });
  }

  win.on("closed", () => {
    win = null;
  });
}

// ---------------------------------------------------------------- Ish stoli HUD
//
// Butun ekranni egallaydigan Rainmeter uslubidagi sahna. Ikki rejim bor:
//
//   JARVIS_DESKTOP=1 (standart) — asosiy oyna. Yashirin turadi va chaqirilganda
//       (qarsak, «hey jarvis», ⌘⇧J) ochiladi.
//   JARVIS_DESKTOP=ambient      — jonli fon. Doim ko'rinadi, oynalar ORQASIDA.
//   JARVIS_DESKTOP=0            — butunlay o'chirilgan.
//
// Ochilganda sahna darhol "to'liq ishlamaydi": uyqu holatida turadi va
// foydalanuvchi gapirganda yonadi. Bu mantiq renderer tomonda.
//
// XAVFSIZLIK QOIDASI: bu oyna butun ekranni egallaydi, shuning uchun undan
// chiqish yo'li HECH QACHON renderer'ga bog'liq bo'lmasligi kerak. Sahifaning
// JS'i buzilsa ham foydalanuvchi qamalib qolmasligi shart. Shuning uchun:
//   * oyna "hamma narsa ustida" emas — Cmd+Tab bilan boshqa ilovaga o'tsa,
//     u oldinga chiqadi va HUD orqada qoladi;
//   * fokus yo'qolsa, oyna o'zi yashirinadi;
//   * Esc global tugma sifatida ro'yxatdan o'tadi (faqat oyna ochiq turganda) —
//     u main jarayonida ishlaydi, sahifadan mustaqil;
//   * ⌘⇧J ikkinchi marta bosilsa yopadi.
// Bir marta bu qoida buzilgan edi va foydalanuvchi kompyuterni qayta
// yoqishga majbur bo'lgan.

const DESK_MODE = process.env.JARVIS_DESKTOP || "1";
const DESK_AMBIENT = DESK_MODE === "ambient";

let deskWin = null;

function createDesktopWindow() {
  const { x, y, width, height } = screen.getPrimaryDisplay().bounds;

  deskWin = new BrowserWindow({
    x, y, width, height,
    // "desktop" turi oynani ish stoli fonining darajasiga qo'yadi — oddiy
    // oynalar uning ustida ochiladi. Asosiy oyna rejimida bu kerak emas:
    // u chaqirilganda hammasining ustiga chiqishi kerak.
    ...(DESK_AMBIENT ? { type: "desktop" } : {}),
    show: false,
    frame: false,
    resizable: false,
    movable: false,
    skipTaskbar: true,
    // Asosiy oyna rejimida Esc ishlashi uchun fokus kerak.
    focusable: !DESK_AMBIENT,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload-desktop.js"),
      contextIsolation: true,
      nodeIntegration: false,
      // Yashirin oynada ham WebSocket tinglashi kerak: chaqirilganini bilib,
      // o'zini ko'rsatishni so'raydi.
      backgroundThrottling: false,
    },
  });

  deskWin.loadFile(path.join(__dirname, "renderer", "desktop.html"));
  deskWin.on("closed", () => { deskWin = null; });

  if (DESK_AMBIENT) {
    deskWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    deskWin.showInactive();
  } else {
    // Fokus boshqa ilovaga o'tsa — yashiramiz. Bu eng ishonchli chiqish yo'li:
    // foydalanuvchi Cmd+Tab bosса yoki boshqa oynaga bossa, HUD yo'qoladi.
    deskWin.on("blur", hideDesktop);

    // Sahifadan mustaqil klaviatura yo'li: bu hodisa main jarayonida,
    // sahifa JS'i ishga tushmasa ham keladi.
    deskWin.webContents.on("before-input-event", (event, input) => {
      if (input.type !== "keyDown") return;
      const quit = input.key === "Escape" || (input.meta && input.key.toLowerCase() === "w");
      if (quit) {
        event.preventDefault();
        hideDesktop();
      }
    });
  }

  startStats();
  startWeather();
}

// Esc faqat HUD ochiq turganda global tugma bo'ladi. Global — chunki oyna
// fokusda bo'lmasligi yoki sahifa javob bermasligi mumkin.
let escapeBound = false;

function bindEscape() {
  if (escapeBound) return;
  escapeBound = globalShortcut.register("Escape", hideDesktop);
  if (!escapeBound) console.warn("Esc ro'yxatdan o'tmadi — oynani ⌘⇧J bilan yoping");
}

function releaseEscape() {
  if (!escapeBound) return;
  globalShortcut.unregister("Escape");
  escapeBound = false;
}

function showDesktop() {
  if (!deskWin || DESK_AMBIENT) return;
  const wasHidden = !deskWin.isVisible();
  // Ko'rinib turgan bo'lsa ham `show()` — oynani oldinga chiqaradi.
  deskWin.show();
  deskWin.focus();
  if (wasHidden) {
    // Renderer yoqilish animatsiyasini noldan boshlaydi.
    deskWin.webContents.send("desk-visible");
  }
  bindEscape();
}

function hideDesktop() {
  releaseEscape();
  if (deskWin && !DESK_AMBIENT && deskWin.isVisible()) deskWin.hide();
}

function toggleDesktop() {
  if (!deskWin || DESK_AMBIENT) return;
  if (deskWin.isVisible()) hideDesktop();
  else showDesktop();
}

ipcMain.on("desk-show", showDesktop);
ipcMain.on("desk-hide", hideDesktop);

// --- Tizim ko'rsatkichlari: CPU (o'lchovlar farqidan), RAM, disk, ish vaqti ---

const os = require("node:os");
const fs = require("node:fs");
const { execFile } = require("node:child_process");
const { shell } = require("electron");

let prevCpu = null;

function cpuPercent() {
  const cpus = os.cpus();
  let idle = 0, total = 0;
  for (const c of cpus) {
    for (const k of Object.keys(c.times)) total += c.times[k];
    idle += c.times.idle;
  }
  let percent = 0;
  if (prevCpu) {
    const dTotal = total - prevCpu.total;
    const dIdle = idle - prevCpu.idle;
    if (dTotal > 0) percent = (1 - dIdle / dTotal) * 100;
  }
  prevCpu = { idle, total };
  return percent;
}

function startStats() {
  const send = () => {
    if (!deskWin) return;
    let disk = null;
    try {
      // Node 18+: statfsSync. Ba'zi tizimlarda yo'q bo'lishi mumkin.
      const s = fs.statfsSync("/");
      const totalB = s.blocks * s.bsize;
      const freeB = s.bavail * s.bsize;
      disk = { percent: (1 - freeB / totalB) * 100, usedGb: (totalB - freeB) / 1e9, freeGb: freeB / 1e9 };
    } catch { /* disk ko'rsatkichisiz davom etamiz */ }

    deskWin.webContents.send("stats", {
      cpu: cpuPercent(),
      ram: (1 - os.freemem() / os.totalmem()) * 100,
      disk: disk ? disk.percent : 0,
      diskUsedGb: disk ? disk.usedGb : null,
      diskFreeGb: disk ? disk.freeGb : null,
      uptimeSec: os.uptime(),
    });
  };
  send();
  setInterval(send, 2000);
}

// --- Ob-havo: open-meteo (kalitsiz). Tarmoq bo'lmasa jim o'tib ketadi. ---

async function fetchWeather() {
  const lat = process.env.JARVIS_LAT || "41.31";
  const lon = process.env.JARVIS_LON || "69.24";
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
    `&daily=temperature_2m_max,temperature_2m_min,weather_code&timezone=auto&forecast_days=2`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    const d = data.daily;
    return {
      today: { max: Math.round(d.temperature_2m_max[0]), min: Math.round(d.temperature_2m_min[0]), code: d.weather_code[0] },
      tomorrow: { max: Math.round(d.temperature_2m_max[1]), min: Math.round(d.temperature_2m_min[1]), code: d.weather_code[1] },
    };
  } catch {
    return null;
  }
}

function startWeather() {
  const send = async () => {
    if (!deskWin) return;
    const weather = await fetchWeather();
    if (weather && deskWin) deskWin.webContents.send("weather", weather);
  };
  send();
  setInterval(send, 30 * 60 * 1000);
}

// --- Ochish buyruqlari: faqat oq ro'yxatdagilar ---

const ALLOWED_APPS = new Set([
  "Finder", "Safari", "Terminal", "Notes", "Music", "System Settings",
  "Calendar", "Mail", "Messages",
]);

const FOLDER_KEYS = {
  downloads: "downloads", documents: "documents", pictures: "pictures",
  music: "music", videos: "videos", desktop: "desktop",
};

ipcMain.on("desk-open-app", (_e, name) => {
  if (!ALLOWED_APPS.has(name)) return;
  if (process.platform === "darwin") execFile("open", ["-a", name]);
});

ipcMain.on("desk-open-folder", (_e, key) => {
  const mapped = FOLDER_KEYS[key];
  if (!mapped) return;
  try {
    shell.openPath(app.getPath(mapped));
  } catch { /* noma'lum papka — e'tiborsiz */ }
});

// --- Markaziy rasm: foydalanuvchi o'z rasmini tashlaydi, biz saqlaymiz ---
//
// Foydalanuvchi HUD ustiga rasm faylini tashlasa, u userData ichiga yoziladi
// va keyingi ishga tushirishlarda ham o'sha rasm ko'rsatiladi.

const FIGURE_PATH = () => path.join(app.getPath("userData"), "markaz.png");

ipcMain.handle("figure-get", () => {
  try {
    return fs.existsSync(FIGURE_PATH()) ? FIGURE_PATH() : null;
  } catch {
    return null;
  }
});

ipcMain.handle("figure-save", (_e, buffer) => {
  try {
    fs.writeFileSync(FIGURE_PATH(), Buffer.from(buffer));
    return FIGURE_PATH();
  } catch {
    return null;
  }
});

ipcMain.handle("figure-clear", () => {
  try {
    fs.rmSync(FIGURE_PATH(), { force: true });
  } catch { /* yo'q bo'lsa ham mayli */ }
  return null;
});

ipcMain.on("desk-open-url", (_e, url) => {
  // Faqat https va aniq ro'yxat — renderer buzilsa ham ixtiyoriy manzil ochilmasin
  const ALLOWED_URLS = new Set([
    "https://youtube.com", "https://gmail.com", "https://github.com",
    "https://t.me", "https://wikipedia.org", "https://claude.ai",
    "https://google.com", "https://facebook.com", "https://imdb.com",
    "https://yahoo.com",
  ]);
  if (ALLOWED_URLS.has(url)) shell.openExternal(url);
});

// --- Orbni sudrab ko'chirish ---
//
// Ramkasiz oynani `-webkit-app-region: drag` bilan sudrash mumkin edi, lekin
// u bosishni butunlay yutib yuboradi — orbga bosib Jarvisni chaqirib
// bo'lmay qolardi. Shuning uchun renderer o'zi hal qiladi: kichik siljish
// bosish, kattarog'i sudrash. Bu yerga faqat ekran koordinatalaridagi farq
// keladi, ya'ni oyna kursor ostidan siljisa ham hisob to'g'ri qoladi.

ipcMain.on("orb-drag", (_event, delta) => {
  if (!win) return;
  const [x, y] = win.getPosition();
  const next = clamp(x + Math.round(delta.dx || 0), y + Math.round(delta.dy || 0));
  win.setPosition(next.x, next.y);
});

ipcMain.on("orb-drag-end", savePosition);

// Renderer sichqoncha interaktiv element ustida ekanini aytadi.
ipcMain.on("set-interactive", (_event, interactive) => {
  if (!win) return;
  if (interactive) {
    win.setIgnoreMouseEvents(false);
  } else {
    win.setIgnoreMouseEvents(true, { forward: true });
  }
});

// Tasdiq oynasi ochilganda oyna fokus olishi kerak (klaviatura uchun).
ipcMain.on("set-focusable", (_event, focusable) => {
  if (!win) return;
  win.setFocusable(Boolean(focusable));
});

ipcMain.on("quit", () => app.quit());

app.whenReady().then(() => {
  // macOS'da Dock ikonkasi kerak emas — bu fon ilovasi.
  if (process.platform === "darwin" && app.dock) {
    app.dock.hide();
  }

  createWindow();

  // Ish stoli HUD — standart yoqilgan; JARVIS_DESKTOP=0 bilan o'chiriladi.
  if (DESK_MODE !== "0") {
    createDesktopWindow();
  }

  // Global tugma: uyg'otuvchi so'zsiz chaqirish. Ikkinchi marta bosilsa
  // oynani yopadi — ochish va yopish bitta tugmada bo'lishi kerak.
  const combo = process.env.JARVIS_HOTKEY || "CommandOrControl+Shift+J";
  const registered = globalShortcut.register(combo, () => {
    const opening = !deskWin || DESK_AMBIENT || !deskWin.isVisible();
    if (opening) win?.webContents.send("hotkey");
    toggleDesktop();
  });
  if (!registered) {
    console.warn(`Global tugmani (${combo}) ro'yxatdan o'tkazib bo'lmadi`);
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

// Fon ilovasi — oyna yopilsa ham ishlashda davom etadi.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
