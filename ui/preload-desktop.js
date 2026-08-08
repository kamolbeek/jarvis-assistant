// Ish stoli HUD oynasi uchun ko'prik.
// Renderer'ga Node ochilmaydi — faqat quyidagi tor imkoniyatlar.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desk", {
  // Tizim ko'rsatkichlari (CPU/RAM/disk/ish vaqti) — main jarayoni yig'adi.
  onStats: (callback) => ipcRenderer.on("stats", (_e, stats) => callback(stats)),

  // Ob-havo — main jarayoni open-meteo dan oladi (bo'lmasa null).
  onWeather: (callback) => ipcRenderer.on("weather", (_e, weather) => callback(weather)),

  // Ilova/papka/havola ochish — nomlar main tomonda oq ro'yxat bilan tekshiriladi.
  openApp: (name) => ipcRenderer.send("desk-open-app", String(name)),
  openFolder: (key) => ipcRenderer.send("desk-open-folder", String(key)),
  openUrl: (url) => ipcRenderer.send("desk-open-url", String(url)),

  // Yadro manzili — orb bilan bir xil.
  coreUrl: process.env.JARVIS_WS_URL || "ws://127.0.0.1:8765",
});
