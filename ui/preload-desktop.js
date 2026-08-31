// Ish stoli HUD oynasi uchun ko'prik.
// Renderer'ga Node ochilmaydi — faqat quyidagi tor imkoniyatlar.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desk", {
  // Tizim ko'rsatkichlari (CPU/RAM/disk/ish vaqti) — main jarayoni yig'adi.
  onStats: (callback) => ipcRenderer.on("stats", (_e, stats) => callback(stats)),

  // Ob-havo — main jarayoni open-meteo dan oladi (bo'lmasa null).
  onWeather: (callback) => ipcRenderer.on("weather", (_e, weather) => callback(weather)),

  // Ijro etilayotgan musiqa (Spotify/Music ochiq bo'lsa).
  onMedia: (callback) => ipcRenderer.on("media", (_e, media) => callback(media)),

  // Ilova/papka/havola ochish — nomlar main tomonda oq ro'yxat bilan tekshiriladi.
  openApp: (name) => ipcRenderer.send("desk-open-app", String(name)),
  openFolder: (key) => ipcRenderer.send("desk-open-folder", String(key)),
  openUrl: (url) => ipcRenderer.send("desk-open-url", String(url)),
  openTrash: () => ipcRenderer.send("desk-open-trash"),

  // Tizim ovozi va media tugmalari — HUD'dagi ustun va tugmachalar.
  setVolume: (level) => ipcRenderer.send("desk-set-volume", Number(level)),
  media: (action) => ipcRenderer.send("desk-media", String(action)),

  // Oynani ko'rsatish/yashirish. Chaqirilganda renderer o'zi so'raydi —
  // yadro faqat holatni biladi, oyna boshqaruvi main jarayonida.
  show: () => ipcRenderer.send("desk-show"),
  hide: () => ipcRenderer.send("desk-hide"),
  onVisible: (callback) => ipcRenderer.on("desk-visible", () => callback()),

  // Markaziy rasm: olish / saqlash / o'chirish.
  getFigure: () => ipcRenderer.invoke("figure-get"),
  saveFigure: (buffer) => ipcRenderer.invoke("figure-save", buffer),
  clearFigure: () => ipcRenderer.invoke("figure-clear"),

  // Yadro manzili — orb bilan bir xil.
  coreUrl: process.env.JARVIS_WS_URL || "ws://127.0.0.1:8765",
});
