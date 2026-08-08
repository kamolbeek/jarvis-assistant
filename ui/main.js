// Jarvis orb — ekranda doim ustida turadigan suzuvchi oyna.
//
// Uchta narsa muhim:
//   1. Oyna shaffof va ramkasiz — faqat orb ko'rinadi.
//   2. Barcha ish stollarida va to'liq ekran ilovalar ustida ko'rinadi.
//   3. Bo'sh joyi "o'tkazuvchan" — orbdan tashqarisiga bosilsa, bosish ostidagi
//      ilovaga o'tadi. Aks holda orb ekranning bir qismini bloklab qo'yardi.

const { app, BrowserWindow, ipcMain, screen, globalShortcut } = require("electron");
const path = require("node:path");

const WINDOW_WIDTH = 420;
const WINDOW_HEIGHT = 596;
const MARGIN = 24;

let win = null;

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
  const { x, y } = positionFor(position, display);

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
// Butun ekranni egallaydigan, oynalar ORQASIDA (ish stoli darajasida)
// turadigan Rainmeter uslubidagi sahna. JARVIS_DESKTOP=0 bilan o'chiriladi.

let deskWin = null;

function createDesktopWindow() {
  const { x, y, width, height } = screen.getPrimaryDisplay().bounds;

  deskWin = new BrowserWindow({
    x, y, width, height,
    // "desktop" turi oynani ish stoli fonining darajasiga qo'yadi —
    // oddiy oynalar uning ustida ochiladi, xuddi jonli fon kabi.
    type: "desktop",
    frame: false,
    resizable: false,
    movable: false,
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, "preload-desktop.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  deskWin.loadFile(path.join(__dirname, "renderer", "desktop.html"));
  deskWin.on("closed", () => { deskWin = null; });

  startStats();
  startWeather();
}

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
  ]);
  if (ALLOWED_URLS.has(url)) shell.openExternal(url);
});

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
  if (process.env.JARVIS_DESKTOP !== "0") {
    createDesktopWindow();
  }

  // Global tugma: uyg'otuvchi so'zsiz chaqirish.
  const combo = process.env.JARVIS_HOTKEY || "CommandOrControl+Shift+J";
  const registered = globalShortcut.register(combo, () => {
    win?.webContents.send("hotkey");
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
