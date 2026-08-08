// Renderer bilan main jarayoni o'rtasidagi tor va xavfsiz ko'prik.
// Renderer'ga Node API'si ochilmaydi — faqat quyidagi to'rtta funksiya.

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("orb", {
  // Sichqoncha interaktiv element ustidami? (oyna bosishlarni o'tkazsinmi)
  setInteractive: (value) => ipcRenderer.send("set-interactive", Boolean(value)),

  // Tasdiq oynasi ochiq bo'lganda klaviatura kerak bo'ladi.
  setFocusable: (value) => ipcRenderer.send("set-focusable", Boolean(value)),

  // Global tugma bosilganda chaqiriladi.
  onHotkey: (callback) => ipcRenderer.on("hotkey", () => callback()),

  quit: () => ipcRenderer.send("quit"),

  // Yadro manzili — main jarayoniga bog'liq bo'lmasligi uchun shu yerda.
  coreUrl: process.env.JARVIS_WS_URL || "ws://127.0.0.1:8765",
});
