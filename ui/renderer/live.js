// Wallpaperning O'ZINI jonlantiruvchi qatlam.
//
// Dizayn o'zgarmaydi: ekranda o'sha SHIELD OS rasmi turadi. Faqat undagi
// qotib qolgan raqamlar jonlanadi — soat haqiqiy vaqtni, CPU/RAM haqiqiy
// yukni, disk haqiqiy hajmni ko'rsatadi va tugmalar bosiladi.
//
// Usul oddiy: eski raqamni rasmning O'ZIDAN olingan toza ustunni cho'zib
// yopamiz (fon shu tufayli aynan mos tushadi — bir xil naqsh, bir xil
// gradient), so'ng ustiga yangi qiymatni chizamiz. Shuning uchun bu yerdagi
// barcha koordinatalar rasmning asl piksellarida (1920x1080) berilgan.

const LIVE = (() => {
  const IMG_W = 1920;
  const IMG_H = 1080;
  const TAU = Math.PI * 2;

  // Wallpaperdagi yozuvlar oq, biroz sovuq tusda
  const INK = "rgba(238, 246, 250, 0.94)";
  const INK_DIM = "rgba(214, 226, 234, 0.85)";
  const AMBER = "#f5a623";

  // Rasmdagi shrift topilmaydi — eng yaqin geometrik og'ir shriftlar.
  // Raqamlar kengroq bo'lgani uchun ular alohida chiziladi (advance bilan).
  const F_CLOCK = '"Eurostile", "Arial Rounded MT Bold", "Helvetica Neue", Helvetica, Arial, sans-serif';
  const F_TEXT = '"Helvetica Neue", Helvetica, Arial, sans-serif';

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONTHS_FULL = ["January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"];
  const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  const pad = (n) => String(n).padStart(2, "0");
  const gb = (v) => (v === null || v === undefined ? "—" : v >= 100 ? v.toFixed(1) : v.toFixed(1));
  const rateShort = (bps) => {
    if (!bps) return "0.0 b";
    if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)} M`;
    if (bps >= 1e3) return `${(bps / 1e3).toFixed(1)} K`;
    return `${Math.round(bps)} b`;
  };
  const rate = (bps) => {
    if (!bps) return "0.0 B";
    if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)} MB`;
    if (bps >= 1e3) return `${(bps / 1e3).toFixed(1)} KB`;
    return `${Math.round(bps)} B`;
  };

  // --------------------------------------------------------------- bosiladigan joylar
  //
  // Hammasi rasm piksellarida: [x, y, w, h]. Rasm ekranda kichrayganda ham
  // bir xil joyda qoladi, chunki hisob rasmga nisbatan yuritiladi.
  const ZONES = [
    // Chapdagi ilova tugmalari
    { box: [150, 106, 120, 42], app: "Safari", title: "Chrome" },
    { box: [150, 163, 120, 42], app: "System Settings", title: "Boshqaruv paneli" },
    { box: [150, 218, 120, 42], app: "Music", title: "Pleyer" },
    { box: [150, 273, 120, 42], app: "Safari", title: "Firefox" },
    { box: [150, 328, 120, 42], app: "Finder", title: "Fayllar" },
    { box: [150, 383, 120, 42], app: "Messages", title: "Skype" },

    // Yuqoridagi dok
    { box: [1155, 42, 110, 34], app: "Finder", title: "Photoshop" },
    { box: [1272, 42, 110, 34], app: "Safari", title: "IMG Tool" },
    { box: [1389, 42, 110, 34], app: "Notes", title: "Coll Edtior" },
    { box: [1506, 42, 110, 34], app: "Terminal", title: "Tool Kit" },
    { box: [1623, 42, 110, 34], app: "Music", title: "Audition" },

    // WEB ro'yxati
    { box: [762, 148, 92, 18], url: "https://google.com", title: "Google" },
    { box: [762, 167, 92, 18], url: "https://gmail.com", title: "Gmail" },
    { box: [762, 186, 92, 18], url: "https://facebook.com", title: "Facebook" },
    { box: [762, 205, 92, 18], url: "https://youtube.com", title: "YouTube" },
    { box: [762, 224, 92, 18], url: "https://imdb.com", title: "IMDB" },
    { box: [762, 340, 92, 18], url: "https://yahoo.com", title: "Yahoo" },
    { box: [762, 377, 92, 18], url: "https://wikipedia.org", title: "Wikipedia" },

    // O'ngdagi radial menyu
    { box: [1740, 626, 52, 48], url: "https://gmail.com", title: "Mail" },
    { box: [1757, 646, 56, 46], url: "https://google.com", title: "Google" },
    { box: [1777, 668, 84, 46], url: "https://github.com", title: "Deviantart" },
    { box: [1787, 690, 66, 46], url: "https://youtube.com", title: "YouTube" },
    { box: [1798, 740, 62, 28], url: "https://t.me", title: "Twitter" },
    { box: [1798, 771, 74, 28], url: "https://facebook.com", title: "Facebook" },

    // Papkalar
    { box: [1478, 826, 84, 32], folder: "downloads", title: "Yuklamalar" },
    { box: [1764, 824, 88, 32], folder: "documents", title: "Hujjatlar" },
    { box: [1508, 870, 82, 32], folder: "desktop", title: "Dropbox" },
    { box: [1738, 870, 80, 32], folder: "pictures", title: "Rasmlar" },
    { box: [1550, 898, 76, 32], folder: "music", title: "Musiqa" },
    { box: [1712, 898, 78, 32], folder: "videos", title: "Videolar" },

    // Axlat qutisi
    { box: [1160, 268, 140, 120], trash: true, title: "Axlat qutisi" },

    // Media tugmalari
    { box: [1548, 1002, 30, 36], media: "prev", title: "Oldingi" },
    { box: [1578, 1002, 32, 36], media: "playpause", title: "Ijro / to'xtatish" },
    { box: [1610, 1002, 32, 36], media: "next", title: "Keyingi" },

    // Ovoz ustuni — bosilgan balandlik yangi daraja bo'ladi
    { box: [1884, 596, 36, 226], volume: true, title: "Ovoz balandligi" },

    // Reaktor — Jarvis'ni chaqiradi
    { circle: [962, 770, 62], activate: true, title: "Jarvis'ni chaqirish" },
    // Chap pastdagi JARVIS doirasi — bo'g'in siferblatlari
    { circle: [370, 790, 84], dials: true, title: "Bo'g'inlar paneli" },
  ];

  function hitTest(nx, ny) {
    const px = nx * IMG_W;
    const py = ny * IMG_H;
    for (const z of ZONES) {
      if (z.circle) {
        const [cx, cy, r] = z.circle;
        if ((px - cx) ** 2 + (py - cy) ** 2 <= r * r) return z;
      } else {
        const [x, y, w, h] = z.box;
        if (px >= x && px <= x + w && py >= y && py <= y + h) return z;
      }
    }
    return null;
  }

  // Ovoz ustunida bosilgan nuqta -> 0..100
  function volumeAt(ny) {
    const [, y, , h] = ZONES.find((z) => z.volume).box;
    const rel = 1 - ((ny * IMG_H) - y) / h;
    return Math.round(Math.max(0, Math.min(1, rel)) * 100);
  }

  // --------------------------------------------------------------- chizish

  /**
   * Rasm ustidagi jonli qatlam.
   *
   * ctx  — fx canvas konteksti (rasm ustida turadi)
   * img  — wallpaper elementi (undan toza fon nusxalanadi)
   * rect — rasm ekranda egallagan to'rtburchak {x, y, w, h}
   * d    — jonli ma'lumot
   * t    — vaqt (soniya), aylanmalar uchun
   */
  function draw(ctx, img, rect, d, t) {
    if (!img || !img.naturalWidth) return;
    const k = rect.w / IMG_W;
    const X = (px) => rect.x + px * k;
    const Y = (py) => rect.y + py * k;
    const S = (v) => v * k;
    const now = new Date();

    // Eski qiymatni yopish: rasmning O'ZIDAN `srcX` ustunini cho'zib qo'yamiz.
    // Fon gorizontal yo'nalishda deyarli bir xil, shuning uchun ulanish joyi
    // ko'rinmaydi — panel naqshi ham, gradienti ham saqlanadi.
    function cover(px, py, w, h, srcX) {
      ctx.drawImage(img, srcX, py, 2, h, X(px), Y(py), S(w), S(h));
    }

    // Xuddi shu ustunlardan, lekin boshqa qatordan olingan bo'lak. Fon
    // vertikal o'zgaradigan joylarda ustun cho'zishdan tabiiyroq tushadi.
    function coverY(px, py, w, h, srcY) {
      ctx.drawImage(img, px, srcY, w, h, X(px), Y(py), S(w), S(h));
    }

    function txt(str, px, py, size, o = {}) {
      ctx.font = `${o.weight || 400} ${S(size)}px ${o.font || F_TEXT}`;
      ctx.textAlign = o.align || "left";
      ctx.textBaseline = "alphabetic";
      ctx.fillStyle = o.color || INK;
      // Shrift har kompyuterda boshqacha o'lchamda chiqadi. Rasmdagi joyga
      // aniq tushishi uchun kerak bo'lsa cho'zamiz-siqamiz: balandligi
      // `fitH` (rasmdagi harf balandligi), kengligi `maxW` bilan chegaralanadi.
      const m = ctx.measureText(str);
      const w = m.width;
      const asc = m.actualBoundingBoxAscent || S(size) * 0.72;
      let sx = 1, sy = 1;
      if (o.fitH) sx = sy = S(o.fitH) / asc;
      if (o.maxW && w * sx > S(o.maxW)) sx = S(o.maxW) / w;
      if (sx !== 1 || sy !== 1) {
        ctx.save();
        ctx.translate(X(px), Y(py));
        ctx.scale(sx, sy);
        ctx.fillText(str, 0, 0);
        ctx.restore();
        return;
      }
      ctx.fillText(str, X(px), Y(py));
    }

    // Soat raqamlari: har biri o'z katagida — rasmdagidek teng oraliqda
    function digits(str, rightPx, basePy, capH, adv, colonAdv, color) {
      // Rasmdagi raqam balandligi `capH` — shriftni aynan shunga moslaymiz
      const size = capH / 0.72;
      ctx.font = `700 ${S(size)}px ${F_CLOCK}`;
      ctx.textAlign = "center";
      ctx.fillStyle = color || INK;
      const asc = ctx.measureText("8").actualBoundingBoxAscent || S(capH);
      const scale = S(capH) / asc;
      let total = 0;
      for (const ch of str) total += ch === ":" ? colonAdv : adv;
      let x = rightPx - total;
      for (const ch of str) {
        const w = ch === ":" ? colonAdv : adv;
        ctx.save();
        ctx.translate(X(x + w / 2), Y(basePy));
        ctx.scale(scale, scale);
        ctx.fillText(ch, 0, 0);
        ctx.restore();
        x += w;
      }
    }

    const h12 = now.getHours() % 12 || 12;
    const ampm = now.getHours() < 12 ? "AM" : "PM";
    const ram = Math.round(d.ram || 0);
    const disks = d.disks || [];
    const bat = d.battery;

    // ================================================================ YOPISH
    // Avval hamma eski qiymat yopiladi, keyin yangisi chiziladi — shunda
    // qo'shni maydonning yopilishi yangi yozuvni yeb qo'ymaydi.

    cover(396, 984, 264, 84, 803);   // pastdagi katta soat + aksi
    coverY(640, 986, 44, 28, 952);   // AM/PM
    coverY(424, 968, 152, 22, 940);  // sana qatori
    cover(1638, 92, 104, 28, 1552);  // o'ngdagi soat
    cover(1645, 121, 74, 26, 1636);  // hafta kuni
    cover(1628, 144, 112, 15, 1636); // to'liq sana
    cover(1776, 18, 102, 90, 1771);   // sana bloki: kun
    cover(1806, 105, 60, 18, 1795);  // oy (zargaldoq chiziq ichidan)
    cover(1812, 122, 68, 13, 1794);  // hafta kuni
    cover(304, 36, 52, 32, 273);     // RAM USAGE foizi
    cover(284, 88, 110, 18, 280);   // Used:
    cover(284, 106, 110, 18, 280);  // Free:
    for (const by of [100, 120, 140]) cover(466, by, 192, 5, 676);  // SYSTEM chiziqlari
    for (const by of [88, 108, 128]) cover(630, by, 30, 13, 676);   // SYSTEM foizlari
    if (disks.length) {
      cover(582, 175, 26, 21, 677);    // DRIVE: HD C
      cover(1476, 199, 174, 19, 1436); // DISK C qatori
      cover(1440, 215, 220, 4, 1436);  // DISK C chizig'i
      cover(1680, 176, 54, 13, 1613);  // FILESYSTEMS C
      cover(1732, 177, 124, 12, 1613); // FILESYSTEMS C ko'rsatkichi
    }
    if (disks.length > 1) {
      cover(624, 175, 34, 21, 677);    // DRIVE: HD D
      cover(1476, 220, 174, 20, 1436); // DISK D qatori
      cover(1440, 235, 220, 4, 1436);  // DISK D chizig'i
      cover(1680, 190, 54, 13, 1613);  // FILESYSTEMS D
      cover(1732, 191, 124, 12, 1613); // FILESYSTEMS D ko'rsatkichi
    }
    cover(1364, 96, 128, 40, 1348);  // Speed / Total
    if (d.weather && d.weather.today) cover(1176, 117, 36, 18, 1212); // harorat
    if (d.trash) {
      cover(1178, 270, 77, 20, 1278); // axlat: nechta
      cover(1178, 288, 77, 22, 1278); // axlat: hajm
    }
    cover(206, 980, 176, 46, 200);   // taqvim (sarlavha + raqamlar + bugungi kun)
    cover(312, 1026, 84, 26, 388);   // batareya foizi
    cover(326, 1048, 108, 24, 388);   // batareya holati
    cover(250, 1023, 102, 11, 388);  // batareya chizig'i
    cover(920, 929, 38, 20, 965);    // "power level is at 100"
    cover(714, 998, 44, 24, 754);    // kichik CPU
    cover(674, 1022, 34, 28, 674);   // kichik RAM
    cover(1036, 997, 102, 47, 1085); // TIME / DATE
    cover(1150, 996, 28, 14, 1205);  // sekundlar
    if (d.media && d.media.position != null) cover(1528, 984, 52, 16, 1592); // media vaqti
    cover(1320, 762, 58, 20, 1305);  // pastdagi o'ng soat
    cover(276, 154, 206, 14, 272);   // tarmoq qatori (yuklash / jo'natish)
    cover(1386, 452, 26, 12, 1410);  // UPLOAD qiymati
    cover(1471, 452, 32, 12, 1410);  // DOWNLOAD qiymati

    // ================================================================ CHIZISH

    // ---- pastdagi katta soat (rasmdagi eng katta element)
    const clock = `${h12}:${pad(now.getMinutes())}`;
    // Aks: pastga qaragan, so'nuvchi nusxa — rasmda ham shunday edi
    ctx.save();
    ctx.translate(0, Y(1034) * 2 + S(3));
    ctx.scale(1, -1);
    ctx.globalAlpha = 0.18;
    digits(clock, 649, 1034, 47, 48, 25);
    ctx.restore();
    digits(clock, 649, 1034, 47, 48, 25);
    txt(ampm, 648, 1010, 20, { color: INK_DIM });
    txt(`${now.getDate()}-${MONTHS[now.getMonth()]}., ${DAYS[now.getDay()]}`, 428, 988, 20);

    // ---- o'ngdagi soat
    digits(`${pad(now.getHours())}:${pad(now.getMinutes())}`, 1739, 119, 24, 22, 12);
    txt(DAYS[now.getDay()], 1680, 143, 15, { align: "center" });
    txt(`${MONTHS_FULL[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()}`,
        1680, 155, 12, { align: "center", color: INK_DIM });

    // ---- sana bloki
    txt(String(now.getDate()), 1872, 104, 100,
        { align: "right", weight: 700, font: F_CLOCK, fitH: 78, maxW: 90 });
    txt(MONTHS_FULL[now.getMonth()].toUpperCase(), 1834, 120, 16,
        { align: "center", weight: 700, color: "rgba(18, 12, 3, 0.95)" });
    txt(DAYS[now.getDay()].toUpperCase(), 1878, 133, 13, { align: "right" });

    // ---- RAM USAGE
    txt(`${ram}%`, 329, 62, 26, { align: "center", fitH: 19, maxW: 40 });
    if (d.ramUsedGb !== undefined && d.ramUsedGb !== null) {
      txt(`Used:${gb(d.ramUsedGb)} GB`, 390, 104, 12, { align: "right" });
      txt(`Free:${gb(d.ramTotalGb - d.ramUsedGb)} GB`, 390, 120, 12, { align: "right" });
    }

    // ---- SYSTEM: CPU / RAM / SWAP
    [[d.cpu, 98], [d.ram, 118], [d.swap, 138]].forEach(([value, base]) => {
      const v = Math.max(0, Math.min(100, value || 0));
      ctx.fillStyle = AMBER;
      ctx.fillRect(X(467), Y(base + 3), S(190 * v / 100), Math.max(1, S(2)));
      txt(`${Math.round(v)}%`, 655, base, 11, { align: "right" });
    });

    // ---- DRIVE (HD C / HD D)
    disks.slice(0, 2).forEach((disk, i) => {
      const px = i === 0 ? 586 : 628;
      txt(`${Math.round(disk.percent)}%`, px, 184, 10, { fitH: 8, maxW: 24, color: INK_DIM });
      txt(`${(disk.totalGb - disk.usedGb).toFixed(1)} G`, px, 193, 9,
          { fitH: 7, maxW: 30, color: INK_DIM });
    });

    // ---- DISK paneli
    disks.slice(0, 2).forEach((disk, i) => {
      const base = i === 0 ? 217 : 238;
      txt(`${gb(disk.usedGb)} GB/${gb(disk.totalGb)} GB used`, 1645, base - 2, 17,
          { align: "right", maxW: 158 });
      ctx.fillStyle = AMBER;
      ctx.fillRect(X(1443), Y(i === 0 ? 217 : 237),
                   S(189 * Math.min(1, disk.percent / 100)), Math.max(1, S(1.5)));
    });

    // ---- FILESYSTEMS
    disks.slice(0, 2).forEach((disk, i) => {
      const base = i === 0 ? 187 : 201;
      txt(`${gb(disk.usedGb)} GB`, 1732, base, 11, { align: "right", color: INK_DIM });
      ctx.strokeStyle = "rgba(200, 210, 218, 0.5)";
      ctx.lineWidth = Math.max(1, S(1));
      ctx.strokeRect(X(1734), Y(base - 7), S(117), S(7));
      ctx.fillStyle = "rgba(200, 210, 218, 0.6)";
      ctx.fillRect(X(1735), Y(base - 6), S(115 * Math.min(1, disk.percent / 100)), S(5));
    });

    // ---- tarmoq
    const net = d.net || {};
    txt(`Speed:${rate(net.down)}`, 1486, 115, 20, { align: "right", maxW: 114 });
    txt(`Total:${(net.totalGb || 0).toFixed(1)} GB`, 1486, 131, 15, { align: "right", maxW: 114 });

    // ---- harorat
    if (d.weather && d.weather.today) {
      txt(`${d.weather.today.max}°C`, 1211, 132, 18, { align: "right" });
    }

    // ---- axlat qutisi
    if (d.trash) {
      txt(`${d.trash.count} items`, 1196, 284, 13);
      txt(d.trash.sizeGb === null || d.trash.sizeGb === undefined
            ? "— GB" : `${d.trash.sizeGb.toFixed(2)} GB`, 1196, 305, 13);
    }

    // ---- taqvim: shu hafta; bugungi ustun rasmdagidek yoritiladi
    const dow = now.getDay();
    const WEEK = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
    ctx.fillStyle = "rgba(255, 255, 255, 0.10)";
    ctx.fillRect(X(222 + dow * 23.5 - 12), Y(980), S(24), S(46));
    for (let i = 0; i < 7; i++) {
      const day = new Date(now);
      day.setDate(now.getDate() - dow + i);
      const cx = 222 + i * 23.5;
      txt(WEEK[i], cx, 998, 14, { align: "center", maxW: 19, color: INK_DIM });
      txt(String(day.getDate()), cx, 1020, 18,
          { align: "center", fitH: 15, maxW: 19, color: i === dow ? "#ffffff" : INK });
    }

    // ---- batareya
    const level = bat ? Math.max(0, Math.min(1, bat.percent / 100)) : 1;
    ctx.fillStyle = "rgba(205, 215, 222, 0.72)";
    ctx.fillRect(X(252), Y(1025), S(98 * level), S(7));
    txt(bat ? `${Math.round(bat.percent)}%` : "100%", 390, 1050, 26,
        { align: "right", fitH: 19, maxW: 72 });
    txt(bat ? (bat.charging ? "charging" : "on battery") : "no battery", 395, 1068, 15,
        { align: "right", maxW: 80, color: INK_DIM });
    txt(bat ? String(Math.round(bat.percent)) : "100", 940, 946, 20, { align: "center" });

    // ---- kichik CPU / RAM panellari
    txt(`${Math.round(d.cpu || 0)}%`, 718, 1019, 21, { color: INK_DIM });
    txt(`${ram}%`, 678, 1046, 23, { color: "rgba(236, 242, 246, 0.82)" });

    // ---- TIME / DATE paneli
    txt(`${pad(h12)}:${pad(now.getMinutes())}`, 1050, 1018, 16);
    txt(ampm, 1092, 1030, 12, { color: INK_DIM });
    txt(`${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${String(now.getFullYear()).slice(2)}`,
        1046, 1040, 16);
    txt(pad(now.getSeconds()), 1163, 1008, 11, { align: "center", color: INK_DIM });

    // ---- tarmoq: umumiy hajm va tezlik (chapdagi mayda qator)
    txt(`${(net.totalGb || 0).toFixed(1)} GIB - ${rateShort(net.down)}/S`, 285, 165, 9,
        { fitH: 7, maxW: 95, color: INK_DIM });
    txt(`${((net.upTotalGb || 0)).toFixed(1)} GIB - ${rateShort(net.up)}/S`, 385, 165, 9,
        { fitH: 7, maxW: 95, color: INK_DIM });

    // ---- UPLOAD / DOWNLOAD qiymatlari
    txt(rateShort(net.up), 1387, 462, 9, { fitH: 7, maxW: 24, color: INK_DIM });
    txt(rateShort(net.down), 1472, 462, 9, { fitH: 7, maxW: 30, color: INK_DIM });

    // ---- pastdagi o'ngdagi soat (radial menyu yonida)
    txt(`${pad(now.getHours())}:${pad(now.getMinutes())}`, 1373, 780, 22,
        { align: "right", fitH: 16, maxW: 52 });

    // ---- media vaqti
    if (d.media && d.media.position !== undefined && d.media.position !== null) {
      const pos = Math.max(0, Math.round(d.media.position));
      txt(`${Math.floor(pos / 60)}:${pad(pos % 60)}`, 1533, 998, 12, { maxW: 44 });
      // ijro chizig'i — rasmdagi bo'sh ramka to'ladi
      if (d.media.duration) {
        const frac = Math.max(0, Math.min(1, pos / d.media.duration));
        ctx.fillStyle = "rgba(214, 226, 234, 0.55)";
        ctx.fillRect(X(1553), Y(1044), S(232 * frac), S(6));
      }
    }

    // ---- ovoz ustuni (o'ng chekka)
    if (d.volume !== null && d.volume !== undefined) {
      const lit = (d.volume / 100) * 10;
      for (let i = 0; i < 10; i++) {
        const yy = 782 - i * 19;
        ctx.fillStyle = i < lit ? "#f7941e" : "rgba(116, 122, 126, 0.8)";
        ctx.fillRect(X(1889), Y(yy), S(23), S(15));
      }
    }

    // ---- rasmdagi siferblatlar aylanadi
    spin(ctx, X, Y, S, t);

    // ---- sichqoncha ostidagi tugma
    if (d.hover) {
      const z = d.hover;
      ctx.save();
      ctx.strokeStyle = "rgba(120, 226, 255, 0.8)";
      ctx.lineWidth = Math.max(1, S(1.5));
      ctx.shadowColor = "rgba(120, 226, 255, 0.9)";
      ctx.shadowBlur = S(10);
      if (z.circle) {
        const [cx, cy, r] = z.circle;
        ctx.beginPath();
        ctx.arc(X(cx), Y(cy), S(r), 0, TAU);
        ctx.stroke();
      } else {
        const [x, y, w, h] = z.box;
        ctx.strokeRect(X(x) - 2, Y(y) - 2, S(w) + 4, S(h) + 4);
      }
      ctx.restore();
    }
  }

  // Rasmdagi siferblatlar aylanadi: har biriga bir necha yupqa yoy qo'shamiz.
  // Rang va yorqinlik rasmnikiga moslangan — qo'shimcha element emas, xuddi
  // chizmaning o'zi harakatga kelgandek ko'rinadi.
  const DIALS = [
    { c: [560, 585, 86], speed: 0.20, arcs: 3, alpha: 0.34, cyan: false },
    { c: [1400, 556, 58], speed: -0.28, arcs: 2, alpha: 0.30, cyan: false },
    { c: [1487, 127, 34], speed: 0.55, arcs: 2, alpha: 0.40, cyan: false },
    { c: [1590, 122, 30], speed: -0.70, arcs: 2, alpha: 0.40, cyan: false },
    { c: [1640, 790, 58], speed: 0.45, arcs: 3, alpha: 0.55, cyan: true },
    { c: [1640, 790, 40], speed: -0.60, arcs: 2, alpha: 0.45, cyan: true },
  ];

  function spin(ctx, X, Y, S, t) {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const dial of DIALS) {
      const [cx, cy, r] = dial.c;
      ctx.lineWidth = Math.max(1, S(2));
      for (let i = 0; i < dial.arcs; i++) {
        const a = t * dial.speed + (i / dial.arcs) * TAU;
        ctx.beginPath();
        ctx.arc(X(cx), Y(cy), S(r), a, a + 0.7);
        ctx.strokeStyle = dial.cyan
          ? `rgba(90, 220, 255, ${dial.alpha})`
          : `rgba(226, 236, 242, ${dial.alpha})`;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  return { draw, hitTest, volumeAt, ZONES, IMG_W, IMG_H };
})();

if (typeof module !== "undefined") module.exports = LIVE;
