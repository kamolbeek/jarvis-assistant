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

  const page = path.join(__dirname, "renderer", "desktop.html");
  deskWin.loadFile(page);
  deskWin.on("closed", () => { deskWin = null; });

  // Sahifadagi xato terminalda ko'rinsin. Aks holda HUD "yarim ishlagan"
  // holatda qoladi va sababini faqat DevTools bilan topsa bo'ladi.
  console.log(`Ish stoli sahifasi: ${page}`);
  deskWin.webContents.on("console-message", (...args) => {
    // Electron 33 da imzo (event, level, message, line, source),
    // yangiroq versiyalarda (event, details) — ikkalasini ham qo'llaymiz.
    const d = args[1] && typeof args[1] === "object" ? args[1] : null;
    const level = d ? d.level : args[1];
    const message = d ? d.message : args[2];
    if (level === 3 || level === "error" || level === "warning") {
      console.warn(`[HUD] ${message}`);
    }
  });
  deskWin.webContents.on("did-fail-load", (_e, code, desc, url) => {
    console.error(`[HUD] sahifa yuklanmadi (${code}): ${desc} — ${url}`);
  });
  deskWin.webContents.on("render-process-gone", (_e, details) => {
    console.error(`[HUD] renderer to'xtadi: ${details.reason}`);
  });

  if (process.argv.includes("--dev")) {
    deskWin.webContents.openDevTools({ mode: "detach" });
  }

  if (DESK_AMBIENT) {
    deskWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    deskWin.showInactive();
  } else {
    // Fokus boshqa ilovaga o'tsa — yashiramiz. Bu eng ishonchli chiqish yo'li:
    // foydalanuvchi Cmd+Tab bossa yoki boshqa oynaga bossa, HUD yo'qoladi.
    //
    // Lekin ochilish paytidagi blur'ni sanamaymiz. macOS'da Dock ikonkasi
    // yashirin ilova (accessory) oynasi ko'rsatilganda darhol bir marta
    // fokusni yo'qotishi mumkin — o'sha payt yashirsak, oyna "ochilmagandek"
    // ko'rinadi: aynan shu sabab HUD chaqirilganda chaqnab yo'qolardi.
    deskWin.on("blur", () => {
      if (Date.now() < showGuardUntil) return;
      hideDesktop();
    });

    // Sahifadan mustaqil klaviatura yo'li: bu hodisa main jarayonida,
    // sahifa JS'i ishga tushmasa ham keladi.
    deskWin.webContents.on("before-input-event", (event, input) => {
      if (input.type !== "keyDown") return;
      const quit = input.key === "Escape" || (input.meta && input.key.toLowerCase() === "w");
      if (quit) {
        event.preventDefault();
        dismissDesktop();
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
  escapeBound = globalShortcut.register("Escape", dismissDesktop);
  if (!escapeBound) console.warn("Esc ro'yxatdan o'tmadi — oynani ⌘⇧J bilan yoping");
}

function releaseEscape() {
  if (!escapeBound) return;
  globalShortcut.unregister("Escape");
  escapeBound = false;
}

// Ochilgandan keyin shuncha vaqt ichida kelgan blur e'tiborga olinmaydi.
let showGuardUntil = 0;

function showDesktop() {
  if (!deskWin || deskWin.isDestroyed() || DESK_AMBIENT) return;
  const wasHidden = !deskWin.isVisible();
  showGuardUntil = Date.now() + 1200;

  // Dock ikonkasi yashirin ilova o'zi old planga chiqmaydi — buni aniq
  // so'rash kerak, aks holda oyna ochiladi-yu, boshqa ilova ustida qolib
  // ketadi yoki darhol fokusni yo'qotib yashirinadi.
  if (process.platform === "darwin") app.focus({ steal: true });

  // Ko'rinib turgan bo'lsa ham `show()` — oynani oldinga chiqaradi.
  deskWin.show();
  deskWin.focus();
  deskWin.moveTop();
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
  if (deskWin.isVisible()) dismissDesktop();
  else showDesktop();
}

// Oynani yopishning ikki xili bor va ular bir xil emas:
//
//   hideDesktop  — oyna ko'rinmay qoldi (masalan boshqa ilovaga o'tildi).
//                  Jarvis suhbatni davom ettirishga tayyor turaveradi.
//   dismissDesktop — foydalanuvchi ATAYLAB yopdi (Esc, ⌘W, ⌘⇧J). Bu
//                  ovozdagi «bekor qil» bilan bir xil ma'no: yadro sukut
//                  holatiga o'tadi. Renderer buni yadroga yetkazadi.
function dismissDesktop() {
  hideDesktop();
  if (deskWin && !deskWin.isDestroyed()) deskWin.webContents.send("desk-dismissed");
}

ipcMain.on("desk-show", showDesktop);
ipcMain.on("desk-hide", hideDesktop);

// --- Tizim ko'rsatkichlari ---
//
// HUD'dagi har bir raqam shu yerdan keladi: CPU, RAM, SWAP, disklar,
// batareya, tarmoq tezligi, ovoz balandligi, axlat qutisi. Sekin
// o'lchovlar (disk, batareya, ijro) alohida, siyrak taymerlarda yangilanadi —
// har ikki soniyada `df` chaqirish kompyuterni bekorga bezovta qiladi.

const os = require("node:os");
const fs = require("node:fs");
const { execFile } = require("node:child_process");
const { shell } = require("electron");

const MAC = process.platform === "darwin";

// Tashqi buyruq. Xato bo'lsa bo'sh satr — ko'rsatkich yo'qligi HUD uchun
// halokat emas, o'sha katak "—" bo'lib turadi.
function run(cmd, args, timeout = 4000) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout, maxBuffer: 1 << 20 }, (err, stdout) => {
      resolve(err ? "" : String(stdout));
    });
  });
}

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

// --- SWAP ---

async function swapPercent() {
  if (MAC) {
    // "total = 2048.00M  used = 1024.00M  free = 1024.00M"
    const out = await run("sysctl", ["-n", "vm.swapusage"]);
    const total = /total\s*=\s*([\d.]+)M/.exec(out);
    const used = /used\s*=\s*([\d.]+)M/.exec(out);
    if (!total || !used || Number(total[1]) === 0) return 0;
    return (Number(used[1]) / Number(total[1])) * 100;
  }
  try {
    const info = fs.readFileSync("/proc/meminfo", "utf8");
    const total = /SwapTotal:\s+(\d+)/.exec(info);
    const free = /SwapFree:\s+(\d+)/.exec(info);
    if (!total || !free || Number(total[1]) === 0) return 0;
    return (1 - Number(free[1]) / Number(total[1])) * 100;
  } catch {
    return 0;
  }
}

// --- Disklar ---
//
// `df -k` — barcha tizimlarda bor. Faqat haqiqiy tomlarni olamiz: tizim
// bo'limlari (devfs, map, overlay) foydalanuvchiga hech nima aytmaydi.

async function diskList() {
  // -P (POSIX) — macOS va Linux'da ustunlar bir xil: oxirgisi ulanish nuqtasi
  const out = await run("df", ["-kP"]);
  const disks = [];
  for (const line of out.split("\n").slice(1)) {
    const parts = line.trim().split(/\s+/);
    if (parts.length < 6) continue;
    const source = parts[0];
    const mount = parts.slice(5).join(" ");
    if (!source.startsWith("/dev/")) continue;
    if (mount !== "/" && !mount.startsWith("/Volumes/") && !mount.startsWith("/mnt/") &&
        !mount.startsWith("/media/") && mount !== "/home") continue;
    const totalGb = (Number(parts[1]) * 1024) / 1e9;
    const usedGb = (Number(parts[2]) * 1024) / 1e9;
    if (!Number.isFinite(totalGb) || totalGb < 1) continue;
    const name = mount === "/" ? (MAC ? "Macintosh HD" : "System") : mount.split("/").pop();
    if (disks.some((d) => d.name === name)) continue;
    disks.push({ name, usedGb, totalGb, percent: (usedGb / totalGb) * 100 });
  }
  return disks.slice(0, 4);
}

// --- Batareya ---

async function batteryInfo() {
  if (MAC) {
    // "Now drawing from 'Battery Power' ... -InternalBattery-0 ... 84%; discharging"
    const out = await run("pmset", ["-g", "batt"]);
    const pct = /(\d+)%/.exec(out);
    if (!pct) return null;
    return {
      percent: Number(pct[1]),
      charging: /AC Power/.test(out) || /charging/.test(out),
    };
  }
  try {
    const base = "/sys/class/power_supply";
    const bat = fs.readdirSync(base).find((n) => n.startsWith("BAT"));
    if (!bat) return null;
    return {
      percent: Number(fs.readFileSync(`${base}/${bat}/capacity`, "utf8").trim()),
      charging: fs.readFileSync(`${base}/${bat}/status`, "utf8").trim() !== "Discharging",
    };
  } catch {
    return null;
  }
}

// --- Tarmoq tezligi ---
//
// Umumiy hisoblagichlar farqidan o'lchaymiz: bir o'lchov o'zi hech nima
// bermaydi, ikkitasining farqi esa aynan tezlik.

let prevNet = null;
let netTotal = 0; // ishga tushgandan beri qabul qilingan baytlar
let netTotalUp = 0;

async function netRates() {
  let rx = 0, tx = 0;
  if (MAC) {
    const out = await run("netstat", ["-ib"]);
    const seen = new Set();
    for (const line of out.split("\n").slice(1)) {
      const p = line.trim().split(/\s+/);
      // Faqat <Link#N> qatorlari — qolganlari o'sha interfeysning takrori
      if (p.length < 10 || !p[2].startsWith("<Link#")) continue;
      if (p[0].startsWith("lo") || seen.has(p[0])) continue;
      seen.add(p[0]);
      rx += Number(p[6]) || 0;
      tx += Number(p[9]) || 0;
    }
  } else {
    try {
      for (const line of fs.readFileSync("/proc/net/dev", "utf8").split("\n").slice(2)) {
        const [name, rest] = line.split(":");
        if (!rest || name.trim().startsWith("lo")) continue;
        const p = rest.trim().split(/\s+/);
        rx += Number(p[0]) || 0;
        tx += Number(p[8]) || 0;
      }
    } catch { /* tarmoq ko'rsatkichisiz davom etamiz */ }
  }
  const now = Date.now();
  let rates = { down: 0, up: 0 };
  if (prevNet && now > prevNet.at) {
    const dt = (now - prevNet.at) / 1000;
    const dRx = Math.max(0, rx - prevNet.rx);
    rates = { down: dRx / dt, up: Math.max(0, (tx - prevNet.tx) / dt) };
    netTotal += dRx;
    netTotalUp += Math.max(0, tx - prevNet.tx);
  }
  prevNet = { rx, tx, at: now };
  return { ...rates, totalGb: netTotal / 1e9, upTotalGb: netTotalUp / 1e9 };
}

// --- Ovoz balandligi ---

async function outputVolume() {
  if (!MAC) return null;
  const out = await run("osascript", ["-e", "output volume of (get volume settings)"]);
  const value = Number(out.trim());
  return Number.isFinite(value) ? value : null;
}

async function setOutputVolume(level) {
  if (!MAC) return;
  const value = Math.max(0, Math.min(100, Math.round(Number(level) || 0)));
  await run("osascript", ["-e", `set volume output volume ${value}`]);
}

// --- Axlat qutisi ---

function trashPath() {
  return MAC
    ? path.join(os.homedir(), ".Trash")
    : path.join(os.homedir(), ".local", "share", "Trash", "files");
}

// Axlat qutisi: nechta fayl va qancha joy egallaydi. Hajmni `du` aytadi —
// u ruxsat bermasa, faqat sonini ko'rsatamiz.
async function trashInfo() {
  let count = null;
  try {
    count = fs.readdirSync(trashPath()).filter((n) => !n.startsWith(".")).length;
  } catch {
    return null;
  }
  let sizeGb = null;
  const out = await run("du", ["-sk", trashPath()], 5000);
  const kb = Number((out.trim().split(/\s+/)[0] || "").replace(/[^0-9]/g, ""));
  if (Number.isFinite(kb) && kb > 0) sizeGb = (kb * 1024) / 1e9;
  return { count, sizeGb };
}

// --- Ijro etilayotgan musiqa ---
//
// Yopiq ilovaga AppleScript bilan murojaat qilish uni OCHIB yuboradi —
// shuning uchun avval jarayonlar ro'yxatini tekshiramiz.

const TRACK_QUERY = (player) => `
if apps contains "${player}" then
  try
    tell application "${player}"
      if player state is not stopped then
        set out to (name of current track) & linefeed & (artist of current track) ¬
          & linefeed & (player state as text)
      end if
    end tell
  end try
end if`;

const PLAYER_SCRIPT = `
set out to ""
tell application "System Events" to set apps to name of processes
${TRACK_QUERY("Spotify")}
if out is "" then ${TRACK_QUERY("Music")}
end if
return out`;

async function nowPlaying() {
  if (!MAC) return null;
  const out = (await run("osascript", ["-e", PLAYER_SCRIPT], 6000)).trim();
  if (!out) return null;
  const [title, artist, state] = out.split("\n");
  return { title, artist, playing: (state || "").trim() === "playing" };
}

async function mediaCommand(action) {
  if (!MAC) return;
  const verb = { playpause: "playpause", next: "next track", prev: "previous track" }[action];
  if (!verb) return;
  const script = `
tell application "System Events" to set apps to name of processes
if apps contains "Spotify" then
  tell application "Spotify" to ${verb}
else if apps contains "Music" then
  tell application "Music" to ${verb}
end if`;
  await run("osascript", ["-e", script]);
}

// --- Mahalliy IP ---

function localIp() {
  for (const list of Object.values(os.networkInterfaces())) {
    for (const iface of list || []) {
      if (iface.family === "IPv4" && !iface.internal) return iface.address;
    }
  }
  return null;
}

// --- Yig'ish va yuborish ---
//
// Sekin o'lchovlar shu obyektda saqlanadi va o'z sur'atida yangilanadi.
const slow = { disks: [], battery: null, volume: null, trash: null, swap: 0, media: null };

function every(ms, fn) {
  const tick = async () => {
    try { await fn(); } catch { /* bitta o'lchov yiqilsa, qolgani ishlayveradi */ }
  };
  tick();
  return setInterval(tick, ms);
}

function startStats() {
  every(30_000, async () => { slow.disks = await diskList(); });
  every(15_000, async () => { slow.battery = await batteryInfo(); });
  every(60_000, async () => { slow.trash = await trashInfo(); });
  every(10_000, async () => { slow.swap = await swapPercent(); });
  every(5_000, async () => { slow.volume = await outputVolume(); });
  every(8_000, async () => { slow.media = await nowPlaying(); });

  const send = async () => {
    if (!deskWin || deskWin.isDestroyed()) return;
    const net = await netRates();
    const totalRam = os.totalmem();
    const freeRam = os.freemem();
    const primary = slow.disks[0];
    deskWin.webContents.send("stats", {
      cpu: cpuPercent(),
      ram: (1 - freeRam / totalRam) * 100,
      ramUsedGb: (totalRam - freeRam) / 1e9,
      ramTotalGb: totalRam / 1e9,
      swap: slow.swap,
      disk: primary ? primary.percent : 0,
      disks: slow.disks,
      battery: slow.battery,
      volume: slow.volume,
      trash: slow.trash,
      net,
      uptimeSec: os.uptime(),
      user: os.userInfo().username,
      host: os.hostname().replace(/\.local$/, ""),
      ip: localIp(),
      city: process.env.JARVIS_CITY || "TOSHKENT",
    });
    if (deskWin && !deskWin.isDestroyed()) deskWin.webContents.send("media", slow.media);
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

ipcMain.on("desk-open-trash", () => {
  try {
    shell.openPath(trashPath());
  } catch { /* axlat qutisi topilmadi — e'tiborsiz */ }
});

// Ovoz balandligi: HUD'dagi ustunga bosilsa shu daraja qo'yiladi.
ipcMain.on("desk-set-volume", (_e, level) => {
  const value = Number(level);
  if (!Number.isFinite(value)) return;
  setOutputVolume(value);
});

// Media tugmalari — faqat ochiq turgan pleyerga (Spotify/Music).
ipcMain.on("desk-media", (_e, action) => {
  mediaCommand(String(action));
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
  const onHotkey = () => {
    const opening = !deskWin || DESK_AMBIENT || !deskWin.isVisible();
    if (opening) win?.webContents.send("hotkey");
    toggleDesktop();
  };

  // Tugma band bo'lsa (boshqa ilova egallagan) — jimgina ishlamay qolmasin,
  // zaxira kombinatsiyani sinab ko'ramiz va qaysi biri ishlaganini aytamiz.
  const combos = [
    process.env.JARVIS_HOTKEY || "CommandOrControl+Shift+J",
    "CommandOrControl+Alt+J",
    "CommandOrControl+Shift+F12",
  ];
  const combo = combos.find((c) => globalShortcut.register(c, onHotkey));
  if (combo) {
    console.log(`Ish stoli HUD tugmasi: ${combo}`);
  } else {
    console.warn(`Global tugmani ro'yxatdan o'tkazib bo'lmadi: ${combos.join(", ")}`);
  }

  // Tekshirish uchun: `npm start -- --desk` HUD'ni darhol ochadi. Chaqiruv
  // zanjiri (mikrofon -> yadro -> WebSocket) ishlamayotganida muammo
  // oynadami yoki chaqiruvdami — shu bilan ajratiladi.
  if (process.argv.includes("--desk")) {
    setTimeout(showDesktop, 800);
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
