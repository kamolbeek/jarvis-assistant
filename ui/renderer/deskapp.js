// Ish stoli sahnasini yurituvchi umumiy qatlam.
//
// Bir xil kod ikki joyda ishlaydi:
//   * Electron oynasi (ui/renderer/desktop.html) — ma'lumot IPC va WebSocket'dan;
//   * brauzer demosi (docs/orb-demo.html)      — ma'lumot taqlid qilinadi.
//
// Shu tufayli demo hech qachon haqiqiy ko'rinishdan farq qilmaydi: ikkalasi
// ham SHELL.draw() ni chaqiradi, faqat manba boshqacha.

const DESKAPP = (() => {
  // Uyqu va yoqilish: oyna ochilganda sahna ko'rinadi, lekin Jarvis uxlab
  // yotibdi — ko'zlar o'chgan. Foydalanuvchi GAPIRGANDA yonadi.
  const DORMANT = 0.25;
  const SPEAK_LEVEL = 0.08;
  const AWAKE_SEC = 8;
  const BUSY = new Set(["thinking", "speaking", "confirm"]);

  function start(opts = {}) {
    const actions = opts.actions || {};
    const canvas = document.getElementById("hud-canvas");
    const ctx = canvas.getContext("2d");
    const fxCanvas = document.getElementById("fx-canvas");
    const fxCtx = fxCanvas.getContext("2d");
    const dialPanel = document.getElementById("dial-panel");
    const dialCanvas = document.getElementById("dial-canvas");
    const dialCtx = dialCanvas ? dialCanvas.getContext("2d") : null;
    const captionBox = document.getElementById("caption");

    const st = {
      W: 0, H: 0,
      state: "idle",
      level: 0, smoothLevel: 0, flash: 0,
      boot: 0, awakeUntil: 0,
      hover: null,
      systems: [],
      weather: null,
      media: null,
      // Ko'rsatkichlar kelgunicha bo'sh emas, "o'lchanmoqda" holatida
      sys: {
        cpu: 0, ram: 0, swap: 0, disks: [], battery: null, net: { down: 0, up: 0 },
        volume: null, uptimeSec: 0, user: "", host: "", ip: "", city: "", trash: null,
      },
      figure: false,
      figureCal: null,
    };

    let captionTimer = null;

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      st.W = window.innerWidth;
      st.H = window.innerHeight;
      for (const [c, cx] of [[canvas, ctx], [fxCanvas, fxCtx]]) {
        c.width = Math.round(st.W * dpr);
        c.height = Math.round(st.H * dpr);
        cx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      if (dialCanvas && dialPanel) {
        const ds = dialPanel.clientWidth || 330;
        dialCanvas.width = dialCanvas.height = Math.round(ds * dpr);
        dialCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
    }

    // Kadr siklini avlod raqami bilan yuritamiz: oyna yashiringanda brauzer
    // requestAnimationFrame'ni to'xtatadi va o'zi doim ham tiklamaydi.
    let generation = 0;
    let lastFrameAt = 0;

    function schedule() {
      const mine = ++generation;
      requestAnimationFrame((now) => {
        if (mine === generation) frame(now);
      });
    }

    function frame(now) {
      lastFrameAt = now;
      const t = now / 1000;
      st.smoothLevel += (st.level - st.smoothLevel) * (st.level > st.smoothLevel ? 0.4 : 0.1);
      st.flash *= 0.93;
      if (st.flash < 0.01) st.flash = 0;

      const target = BUSY.has(st.state) || t < st.awakeUntil ? 1 : DORMANT;
      st.boot += (target - st.boot) * (target > st.boot ? 0.08 : 0.015);

      const out = SHELL.draw(ctx, {
        width: st.W, height: st.H, t,
        state: st.state, level: st.smoothLevel, flash: st.flash, boot: st.boot,
        sys: st.sys, weather: st.weather, media: st.media,
        hover: st.hover, figure: st.figure,
      });

      // Foydalanuvchi o'z rasmini qo'ygan bo'lsa — ko'zlari va reaktori jonlanadi
      fxCtx.clearRect(0, 0, st.W, st.H);
      if (st.figure && st.figureCal && opts.figureRect) {
        const rect = opts.figureRect();
        if (rect) DESK.drawFigureFx(fxCtx, rect, st.figureCal, t, out.eyes, out.surge, st.boot);
      }

      if (dialCtx && dialPanel.classList.contains("on")) {
        const size = dialCanvas.clientWidth || 314;
        HUD.draw(dialCtx, {
          width: size, height: size, t, state: st.state,
          level: st.smoothLevel, flash: st.flash, systems: st.systems,
        });
      }
      schedule();
    }

    // Sikl to'xtab qolsa — qaytadan yo'lga solamiz (yashirilgan oyna muammosi)
    setInterval(() => {
      if (performance.now() - lastFrameAt > 1200) schedule();
    }, 600);

    // ------------------------------------------------------------ bosish
    function apply(zone, click) {
      if (!zone) return;
      switch (zone.kind) {
        case "app": if (click) actions.openApp && actions.openApp(zone.id); break;
        case "folder": if (click) actions.openFolder && actions.openFolder(zone.id); break;
        case "url": if (click) actions.openUrl && actions.openUrl(zone.id); break;
        case "trash": if (click) actions.openTrash && actions.openTrash(); break;
        case "media": if (click) actions.media && actions.media(zone.id); break;
        case "activate": if (click) actions.activate && actions.activate(); break;
        case "volume":
          if (click && actions.setVolume) {
            const v = SHELL.volumeFromHit(zone);
            st.sys.volume = v;
            actions.setVolume(v);
          }
          break;
        case "dials":
          if (click && dialPanel) dialPanel.classList.toggle("on");
          break;
        default: break;
      }
    }

    window.addEventListener("mousemove", (e) => {
      const zone = SHELL.hit(e.clientX, e.clientY);
      st.hover = zone ? { kind: zone.kind, id: zone.id } : null;
      document.body.style.cursor = zone ? "pointer" : "default";
    });

    window.addEventListener("click", (e) => {
      if (e.target.closest && e.target.closest("#dial-panel, #drawer")) return;
      apply(SHELL.hit(e.clientX, e.clientY), true);
    });

    window.addEventListener("resize", () => {
      resize();
      if (opts.onResize) opts.onResize();
    });

    // ------------------------------------------------------------ tashqi API
    const api = {
      setState(next) {
        if (next === "wake" && st.state !== "wake") st.flash = 1;
        st.state = next;
      },
      setLevel(v) {
        st.level = v;
        if (st.state === "listening" && v > SPEAK_LEVEL) api.engage();
      },
      engage() { st.awakeUntil = performance.now() / 1000 + AWAKE_SEC; },
      sleep() { st.boot = 0; st.awakeUntil = 0; },
      flash() { st.flash = 1; },
      setSystems(list) { st.systems = list || []; },
      setWeather(w) { st.weather = w; },
      setMedia(m) { st.media = m; },
      setStats(s) {
        Object.assign(st.sys, s);
        SHELL.pushStats(st.sys);
      },
      setFigure(on, cal) { st.figure = Boolean(on); st.figureCal = cal || null; },
      caption(who, text) {
        if (!captionBox) return;
        captionBox.querySelector("b").textContent = who || "";
        captionBox.querySelector("span").textContent = text || "";
        captionBox.classList.toggle("on", Boolean(text));
        clearTimeout(captionTimer);
        if (text) captionTimer = setTimeout(() => captionBox.classList.remove("on"), 9000);
      },
      state: st,
      resize,
    };

    resize();
    schedule();
    return api;
  }

  return { start };
})();

if (typeof module !== "undefined") module.exports = DESKAPP;
