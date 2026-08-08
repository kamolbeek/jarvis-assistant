// Jarvis orb — ekranda doim ustida turadigan suzuvchi oyna.
//
// Uchta narsa muhim:
//   1. Oyna shaffof va ramkasiz — faqat orb ko'rinadi.
//   2. Barcha ish stollarida va to'liq ekran ilovalar ustida ko'rinadi.
//   3. Bo'sh joyi "o'tkazuvchan" — orbdan tashqarisiga bosilsa, bosish ostidagi
//      ilovaga o'tadi. Aks holda orb ekranning bir qismini bloklab qo'yardi.

const { app, BrowserWindow, ipcMain, screen, globalShortcut } = require("electron");
const path = require("node:path");

const WINDOW_WIDTH = 360;
const WINDOW_HEIGHT = 460;
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
