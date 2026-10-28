/**
 * Red-line plotting sheets over the organiser's PowerPoint template.
 *
 *   node plot.mjs            # writes every sheet into ./sheets/
 *   node plot.mjs 03         # just one, by its number
 *
 * Needs playwright on the path (npx playwright install chromium once).
 * Every number in GEO was measured off template-1920x1080.png rather than
 * eyeballed; measure.py re-derives them if the organiser ships a new file.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// playwright is not a dependency of this workspace - it is only needed to turn
// these sheets into PNGs, and the sheets themselves are plain HTML. Point
// PLAYWRIGHT_DIR at any node_modules that has it if it is not installed here.
const pw = await import('playwright').catch(() => {
  const dir = process.env.PLAYWRIGHT_DIR;
  if (!dir) {
    console.error('playwright not found. Either `npm i -D playwright` in this folder, '
      + 'or run with PLAYWRIGHT_DIR=/path/to/node_modules');
    process.exit(1);
  }
  // Imported by path it arrives as CommonJS, so the named exports sit on default.
  return import(pathToFileURL(path.join(dir, 'playwright', 'index.js')).href);
});
const { chromium } = pw.chromium ? pw : pw.default;
const TEMPLATE = path.join(HERE, 'template-1920x1080.png');
const OUT = path.join(HERE, 'sheets');

/* ----------------------------------------------------------------- measured */
export const GEO = {
  canvas: { w: 1920, h: 1080 },

  // The organiser's own artwork. Nothing of ours may sit on these.
  brand: {
    sokrates: { x: 82, y: 58, w: 282, h: 82 },
    hackathon: { x: 1452, y: 52, w: 392, h: 130 },
    partners: { x: 66, y: 912, w: 510, h: 112 },
    photo: { x: 1460, y: 834, w: 458, h: 244 },
  },

  // The band left between the logos, top and bottom.
  band: { x: 80, y: 240, r: 1840, b: 856 },

  // Where the background still reads as white, so dark text is legible.
  // The white area is a wedge: wide at the top, narrow at the bottom.
  white: {
    wide: { x: 80, y: 240, r: 1032, b: 500 }, // measured: holds to x=1036
    tall: { x: 80, y: 500, r: 768, b: 856 }, // measured: holds to x=768
  },

  // 12 columns of 110 with 40 gutters = exactly 1760 = the band's width.
  grid: { cols: 12, col: 110, gutter: 40 },
};

const colX = (i) => GEO.band.x + (i - 1) * (GEO.grid.col + GEO.grid.gutter);
const spanW = (n) => n * GEO.grid.col + (n - 1) * GEO.grid.gutter;

/* -------------------------------------------------------------------- style */
const RED = '#E5484D';

const CSS = `
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1920px;height:1080px;overflow:hidden}
body{position:relative;font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;
     background:url("${path.basename(TEMPLATE)}") no-repeat 0 0 / 1920px 1080px}
.abs{position:absolute}

/* --- red plotting marks ------------------------------------------------- */
.box{outline:2px dashed ${RED};outline-offset:0}
.box.solid{outline-style:solid}
.forbid{background:repeating-linear-gradient(135deg,
        rgba(229,72,77,.16) 0 7px, rgba(229,72,77,0) 7px 14px);
        outline:2px solid rgba(229,72,77,.85)}
.tag{position:absolute;font-size:17px;font-weight:700;letter-spacing:.04em;
     color:#fff;background:${RED};padding:4px 9px;white-space:nowrap;line-height:1.1}
.tag.ghost{background:rgba(229,72,77,.12);color:${RED};
           box-shadow:inset 0 0 0 1.5px ${RED}}
.tag.bl{left:0;top:100%}
.tag.tl{left:0;bottom:100%}
.tag.tr{right:0;bottom:100%}
.tag.in{left:0;top:0}
.tag.inb{left:0;bottom:0}
.vline{position:absolute;top:0;width:1px;height:1080px;background:rgba(229,72,77,.30)}
.colband{position:absolute;background:rgba(229,72,77,.07);
         box-shadow:inset 0 0 0 1px rgba(229,72,77,.22)}
.hline{position:absolute;left:0;width:1920px;height:0;
       border-top:1.5px dashed rgba(229,72,77,.75)}
.hlab{position:absolute;font-size:15px;font-weight:700;color:${RED};
      background:rgba(255,255,255,.9);padding:1px 5px}
/* The left gutter is only 80px wide, so its labels have to be short and small
   or they get clipped at the canvas edge. */
.hlab.gut{font-size:12px;letter-spacing:.02em;padding:1px 3px}
.legend{position:absolute;background:rgba(255,255,255,.96);border-radius:8px;
        padding:22px 26px;box-shadow:0 14px 44px rgba(60,20,90,.22);
        font-size:19px;line-height:1.75;color:#3C4149}
.legend b{color:#15171A;display:inline-block;min-width:74px}
.legend .ttl{font-size:15px;font-weight:800;letter-spacing:.12em;color:${RED};
             text-transform:uppercase;margin-bottom:10px;display:block}
.dim{position:absolute;height:0;border-top:1.5px solid ${RED}}
.dim::before,.dim::after{content:"";position:absolute;top:-4px;width:0;height:0;
      border-top:4.5px solid transparent;border-bottom:4.5px solid transparent}
.dim::before{left:-1px;border-right:8px solid ${RED}}
.dim::after{right:-1px;border-left:8px solid ${RED}}
.dimv{position:absolute;width:0;border-left:1.5px solid ${RED}}
.dimtxt{position:absolute;font-size:16px;font-weight:700;color:${RED};
        background:#fff;padding:1px 6px;white-space:nowrap}

/* --- placeholder content ------------------------------------------------ */
.eyebrow{font-size:21px;font-weight:800;letter-spacing:.17em;color:${RED};
         text-transform:uppercase}
.h1{font-size:92px;font-weight:800;letter-spacing:-.025em;line-height:.98;color:#15171A}
.h2{font-size:58px;font-weight:800;letter-spacing:-.02em;line-height:1.04;color:#15171A}
.lede{font-size:30px;line-height:1.42;color:#3C4149;font-weight:400}
.body{font-size:26px;line-height:1.5;color:#3C4149}
.small{font-size:20px;line-height:1.45;color:#6A7079}
.num{font-size:108px;font-weight:800;letter-spacing:-.03em;color:#15171A;line-height:.9}
.numred{color:${RED}}
.rule{height:4px;background:${RED}}
.onpurple{color:#fff}
.onpurple .lede,.onpurple .body{color:rgba(255,255,255,.88)}
.card{background:rgba(255,255,255,.97);border-radius:10px;
      box-shadow:0 18px 60px rgba(60,20,90,.18)}
.pill{display:inline-block;font-size:19px;font-weight:700;color:#15171A;
      border:2px solid #15171A;border-radius:999px;padding:5px 14px;margin-right:9px}
.pill.red{color:${RED};border-color:${RED}}
.kv{font-size:24px;color:#3C4149;line-height:1.6}
.kv b{color:#15171A}
`;

/* ------------------------------------------------------------- mark helpers */
const px = (n) => `${Math.round(n)}px`;
const at = (x, y, w, h) => `left:${px(x)};top:${px(y)};width:${px(w)};height:${px(h)}`;

const forbid = (b, label) =>
  `<div class="abs forbid" style="${at(b.x, b.y, b.w, b.h)}">
     <span class="tag bl">${label}</span></div>`;

const zone = (x, y, r, b, label, where = 'tl') =>
  `<div class="abs box" style="${at(x, y, r - x, b - y)}">
     <span class="tag ${where}">${label}</span></div>`;

const hline = (y, label) =>
  `<div class="hline" style="top:${px(y)}"></div>
   <div class="hlab" style="left:1848px;top:${px(y - 10)}">y ${y}</div>
   ${label ? `<div class="hlab gut" style="left:4px;top:${px(y - 9)}">${label}</div>` : ''}`;

const dimH = (x, y, w, text) =>
  `<div class="dim" style="${at(x, y, w, 0)}"></div>
   <div class="dimtxt" style="left:${px(x + w / 2 - 55)};top:${px(y - 11)}">${text}</div>`;

const dimV = (x, y, h, text) =>
  `<div class="dimv" style="${at(x, y, 0, h)}"></div>
   <div class="dimtxt" style="left:${px(x + 8)};top:${px(y + h / 2 - 11)}">${text}</div>`;

const columns = () =>
  Array.from({ length: GEO.grid.cols }, (_, i) =>
    `<div class="colband" style="${at(colX(i + 1), GEO.band.y, GEO.grid.col, GEO.band.b - GEO.band.y)}"></div>`,
  ).join('');

const brandForbidden = () =>
  forbid(GEO.brand.sokrates, 'LOGO PANITIA') +
  forbid(GEO.brand.hackathon, 'LOGO PANITIA') +
  forbid(GEO.brand.partners, 'LOGO PARTNER') +
  // The photo runs to the bottom edge, so its label has to sit above it.
  `<div class="abs forbid" style="${at(GEO.brand.photo.x, GEO.brand.photo.y, GEO.brand.photo.w, GEO.brand.photo.h)}">
     <span class="tag tl">FOTO TEMPLATE</span></div>`;

/* ------------------------------------------------------------------ sheets */
const sheets = [];
const sheet = (id, title, html) => sheets.push({ id, title, html });

/* 00 — the measurement sheet everything else rests on. */
sheet('00', 'grid', `
  ${columns()}
  ${Array.from({ length: GEO.grid.cols }, (_, i) =>
    `<div class="hlab" style="left:${px(colX(i + 1) + 38)};top:276px">${i + 1}</div>`).join('')}

  ${hline(240, 'ATAS')}
  ${hline(500, 'PUTIH')}
  ${hline(856, 'BAWAH')}
  ${hline(888, 'FOOT')}

  ${zone(GEO.white.wide.x, GEO.white.wide.y, GEO.white.wide.r, GEO.white.wide.b,
    'ZONA A · PUTIH LEBAR · 952 × 260', 'in')}
  ${zone(GEO.white.tall.x, GEO.white.tall.y, GEO.white.tall.r, GEO.white.tall.b,
    'ZONA B · KOLOM PUTIH · 688 × 356', 'inb')}
  <div class="abs box" style="${at(1060, 240, 780, 300)};outline-color:rgba(255,255,255,.85)">
    <span class="tag in">ZONA C · GRADIEN</span>
  </div>

  ${brandForbidden()}

  ${dimH(GEO.band.x, 196, GEO.band.r - GEO.band.x, '1760 px · 12 kolom')}
  ${dimH(colX(1), 876, GEO.grid.col, '110')}
  ${dimH(colX(2), 876, GEO.grid.col, '110')}
  ${dimV(1856, GEO.band.y, GEO.band.b - GEO.band.y, '616')}
  ${dimV(44, GEO.white.tall.y, GEO.white.tall.b - GEO.white.tall.y, '356')}

  <div class="abs chrome" style="left:470px;top:58px;width:760px">
    <div class="eyebrow" style="font-size:19px">LEMBAR PLOTTING · 1920 × 1080</div>
    <div class="small" style="margin-top:6px;font-size:18px">
      Semua angka diukur dari template-1920x1080.png, bukan dikira-kira.
    </div>
  </div>

  <div class="legend" style="${at(1180, 580, 660, 0)}">
    <span class="ttl">Garis bantu</span>
    <div><b>y 240</b> atas konten — di bawah kedua logo</div>
    <div><b>y 500</b> batas bawah zona putih lebar</div>
    <div><b>y 856</b> bawah konten — di atas logo partner</div>
    <div><b>x 768</b> batas kanan kolom putih (kolom 1–5)</div>
    <div><b>x 1032</b> batas kanan zona putih lebar (kolom 1–7)</div>
  </div>
`);

/* 01 — cover */
sheet('01', 'cover', `
  ${columns()}
  ${brandForbidden()}
  ${zone(80, 240, 1032, 856, 'ISI SAMPUL · kolom 1–7', 'in')}
  <div class="abs" style="${at(80, 278, 952, 0)}">
    <div class="eyebrow">SAP + AWS AGENTIC AI HACKATHON 2026 · SUPPLY CHAIN</div>
    <div class="h1" style="margin-top:26px">SIGAP</div>
    <div class="rule" style="width:150px;margin:30px 0 26px"></div>
    <div class="h2" style="font-size:46px;max-width:688px">
      Gangguan pasok yang ditangani sebelum orang pertama menyadarinya
    </div>
    <div class="lede" style="margin-top:28px;max-width:660px">
      Dua belas agen membaca SAP, mematuhi TKDN dan LARTAS,
      lalu menaruh satu keputusan yang bisa disetujui di meja Anda.
    </div>
    <div style="margin-top:34px">
      <span class="pill">Tim Socrates</span>
      <span class="pill">Jakarta</span>
      <span class="pill red">Live demo</span>
    </div>
  </div>
  ${hline(240, '')}
  ${hline(856, '')}
`);

/* 02 — section divider */
sheet('02', 'divider', `
  ${columns()}
  ${brandForbidden()}
  ${zone(80, 380, 768, 700, 'NOMOR + JUDUL BAGIAN · kolom 1–5', 'in')}
  <div class="abs" style="${at(80, 420, 688, 0)}">
    <div class="num numred">04</div>
    <div class="h2" style="margin-top:22px">Kenapa ini<br>bisa dipercaya</div>
    <div class="rule" style="width:110px;margin-top:30px"></div>
  </div>
  <div class="abs" style="${at(1180, 300, 560, 0)}">
    <div class="eyebrow onpurple" style="color:#fff;opacity:.85">BAGIAN INI MENJAWAB</div>
    <div class="body" style="color:#fff;margin-top:14px;font-size:28px;line-height:1.45">
      Dari mana tiap angka berasal, apa yang ditolak mesin,
      dan apa yang terjadi kalau ia salah.
    </div>
  </div>
  <div class="abs box" style="${at(1160, 280, 600, 220)};outline-color:rgba(255,255,255,.9)">
    <span class="tag tr">TEKS PUTIH DI ATAS GRADIEN</span>
  </div>
`);

/* 03 — the workhorse: title + body */
sheet('03', 'content', `
  ${columns()}
  ${brandForbidden()}
  ${hline(240, 'EYEBROW')}
  ${hline(300, 'JUDUL')}
  ${hline(430, 'GARIS')}
  ${hline(478, 'ISI')}
  ${hline(856, 'BAWAH')}
  ${zone(80, 240, 1032, 430, 'JUDUL · boleh selebar kolom 1–7', 'tl')}
  ${zone(80, 478, 768, 856, 'ISI · kolom 1–5, di bawah sini gradien naik', 'inb')}

  <div class="abs" style="${at(80, 244, 952, 0)}">
    <div class="eyebrow">02 · SOLUSI</div>
    <div class="h2" style="margin-top:18px;max-width:900px">
      Veto di dua pintu, bukan satu
    </div>
  </div>
  <div class="rule" style="position:absolute;left:80px;top:430px;width:110px"></div>
  <div class="abs" style="${at(80, 478, 688, 0)}">
    <div class="body" style="margin-bottom:22px">
      <b>Saat opsi dipilih.</b> Opsi E — Rp 48 jt, termurah — dicoret
      karena TKDN jatuh ke 34,8%.
    </div>
    <div class="body" style="margin-bottom:22px">
      <b>Saat PO diterbitkan.</b> Dari 18 supplier: 6 domestik lolos,
      12 asing diblok.
    </div>
    <div class="small">Aturan dibaca dari rule pack, bukan dari prompt.</div>
  </div>
  <div class="abs" style="${at(1140, 492, 600, 0)}">
    <div class="num onpurple" style="color:#fff">Rp 46 jt</div>
    <div class="body" style="color:rgba(255,255,255,.92);margin-top:18px">
      harga kepatuhan — selisih yang kami bayar untuk menaati aturan,
      dan kami tunjukkan
    </div>
  </div>
  <div class="abs box" style="${at(1120, 470, 660, 290)};outline-color:rgba(255,255,255,.9)">
    <span class="tag in">ANGKA BESAR · PUTIH DI ATAS GRADIEN</span>
  </div>
`);

/* 04 — two columns inside the white wedge */
sheet('04', 'two-column', `
  ${columns()}
  ${brandForbidden()}
  ${hline(240, '')}
  ${hline(420, '')}
  ${hline(856, '')}
  <div class="abs" style="${at(80, 244, 952, 0)}">
    <div class="eyebrow">01 · MASALAH</div>
    <div class="h2" style="margin-top:18px">Hari ini, jalurnya begini</div>
  </div>
  <!-- Below y=500 the gradient has eaten everything past x=768, so two columns
       on the 12-col grid (which would reach 910) do not fit. The pair is cut
       from the white column itself: 688 = 324 + 40 + 324. -->
  ${zone(80, 420, 404, 856, 'KOLOM KIRI · 324', 'in')}
  ${zone(444, 420, 768, 856, 'KOLOM KANAN · 324', 'in')}
  <div class="abs" style="${at(80, 456, 324, 0)}">
    <div class="eyebrow" style="color:#15171A">KABAR SAMPAI</div>
    <div class="body" style="margin-top:14px;font-size:24px">
      Berita, grup WhatsApp, telepon dari forwarder.
    </div>
    <div class="eyebrow" style="color:#15171A;margin-top:40px">MENELUSURI MANUAL</div>
    <div class="body" style="margin-top:14px;font-size:24px">
      Excel, email, tanya satu-satu: order mana yang kena.
    </div>
  </div>
  <div class="abs" style="${at(444, 456, 324, 0)}">
    <div class="eyebrow" style="color:#15171A">KEPUTUSAN DIAMBIL</div>
    <div class="body" style="margin-top:14px;font-size:24px">
      Dari data yang sudah basi sejak Selasa.
    </div>
    <div class="eyebrow" style="color:${RED};margin-top:40px">LALU HILANG</div>
    <div class="body" style="margin-top:14px;font-size:24px">
      Tak ada catatan dasar keputusan. Audit jadi rekonstruksi.
    </div>
  </div>
  ${dimH(80, 880, 324, '324')}
  ${dimH(444, 880, 324, '324')}
`);

/* 05 — metrics */
sheet('05', 'metrics', `
  ${columns()}
  ${brandForbidden()}
  ${hline(240, '')}
  ${hline(440, '')}
  ${hline(856, '')}
  <div class="abs" style="${at(80, 244, 952, 0)}">
    <div class="eyebrow">05 · DAMPAK</div>
    <div class="h2" style="margin-top:18px">Angka yang bisa dihitung ulang</div>
  </div>
  <!-- Three big numbers side by side do not fit: the white column is 688 wide,
       so each would get 260 and "Rp 116 jt" alone is wider than that. Stacked,
       each number gets the full width and the eye still reads them as a set. -->
  ${zone(80, 470, 768, 790, 'ANGKA BERDERET KE BAWAH · kolom 1–5', 'inb')}
  ${[['Rp 116 jt', 'opsi B+C · TKDN 41,6%'],
     ['Rp 70 jt', 'lebih hemat dari opsi A (38%)'],
     ['56', 'modul yang memeriksa dirinya']]
    .map(([n, c], i) => `
      <div class="abs" style="${at(96, 494 + i * 100, 656, 0)};display:flex;align-items:baseline;gap:24px">
        <div class="num" style="font-size:58px;min-width:250px">${n}</div>
        <div class="small" style="font-size:22px">${c}</div>
      </div>
      ${i < 2 ? `<div class="abs" style="${at(96, 574 + i * 100, 656, 1)};background:rgba(229,72,77,.25)"></div>` : ''}`).join('')}
  <div class="abs" style="${at(96, 812, 656, 0)}">
    <div class="small">Tiap angka di atas keluar dari engine/simulate.py, bukan dari model.</div>
  </div>
  ${dimH(96, 456, 656, '656 · isi tetap di dalam kolom putih')}`);

/* 06 — the escape hatch for anything wide */
sheet('06', 'wide-visual', `
  ${brandForbidden()}
  <div class="abs card" style="${at(80, 240, 1760, 616)}"></div>
  <div class="abs box solid" style="${at(80, 240, 1760, 616)}">
    <span class="tag tl">KARTU PUTIH 1760 × 616 · pakai ini untuk diagram, tabel, screenshot</span>
    <span class="tag bl">Logo panitia tetap terlihat di keempat sudut — itu yang dijaga</span>
  </div>
  <div class="abs" style="${at(136, 288, 1000, 0)}">
    <div class="eyebrow">03 · ARSITEKTUR</div>
    <div class="h2" style="margin-top:14px;font-size:46px">
      AWS untuk otaknya, SAP untuk datanya
    </div>
  </div>
  <div class="abs box" style="${at(136, 420, 1648, 380)};outline-color:rgba(229,72,77,.55)">
    <span class="tag ghost bl">AREA GAMBAR 1648 × 380 · sigap/architecture/diagram.py</span>
  </div>
  ${dimH(80, 212, 1760, '1760')}
  ${dimV(1856, 240, 616, '616')}
`);

/* ------------------------------------------------------------------- render */
const page = (body) =>
  `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head>
   <body>${body}</body></html>`;

const only = process.argv[2];
await fs.mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const tab = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });

/**
 * The sheets are only worth anything if the example content really sits where
 * the red lines say it does. Measuring beats looking: the first metrics sheet
 * looked plausible in the HTML and overflowed its column by 180px.
 */
async function audit(tab, geo) {
  return tab.evaluate((G) => {
    const SEL = '.h1,.h2,.lede,.body,.small,.eyebrow,.num,.pill,.kv';
    const chrome = (el) => el.closest('.chrome') !== null;
    const lum = (c) => {
      const [r, g, b] = (c.match(/[\d.]+/g) || [0, 0, 0]).map(Number);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const problems = [];
    for (const el of document.querySelectorAll(SEL)) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (chrome(el)) continue;
      const text = (el.textContent || '').trim().slice(0, 42);
      if (r.left < 0 || r.top < 0 || r.right > G.canvas.w || r.bottom > G.canvas.h) {
        problems.push(`off canvas: "${text}" [${Math.round(r.left)},${Math.round(r.top)} → ${Math.round(r.right)},${Math.round(r.bottom)}]`);
        continue;
      }
      // Content on a white card carries its own background with it.
      const card = el.closest('.card') || el.parentElement?.closest('.card');
      if (card) continue;
      const cardSibling = [...document.querySelectorAll('.card')].find((c) => {
        const cr = c.getBoundingClientRect();
        return r.left >= cr.left && r.right <= cr.right && r.top >= cr.top && r.bottom <= cr.bottom;
      });
      if (cardSibling) continue;

      for (const [name, b] of Object.entries(G.brand)) {
        if (r.left < b.x + b.w && r.right > b.x && r.top < b.y + b.h && r.bottom > b.y) {
          problems.push(`over ${name}: "${text}"`);
        }
      }
      if (lum(getComputedStyle(el).color) > 150) continue;   // light text: judged by eye on the gradient
      const limitRight = r.bottom <= G.white.wide.b ? G.white.wide.r : G.white.tall.r;
      if (r.left < G.band.x || r.top < G.band.y || r.bottom > G.band.b || r.right > limitRight) {
        problems.push(`dark text leaves the white zone: "${text}" right=${Math.round(r.right)} (max ${limitRight}), bottom=${Math.round(r.bottom)}`);
      }
    }
    return problems;
  }, geo);
}

let bad = 0;
for (const s of sheets) {
  if (only && s.id !== only) continue;
  const tmp = path.join(HERE, `.plot-${s.id}.html`);
  await fs.writeFile(tmp, page(s.html));
  await tab.goto(`file://${tmp}`);
  await tab.waitForTimeout(220);
  const out = path.join(OUT, `${s.id}-${s.title}.png`);
  await tab.screenshot({ path: out });
  const problems = await audit(tab, GEO);
  await fs.unlink(tmp);
  bad += problems.length;
  console.log(`${problems.length ? 'PROBLEM' : 'ok     '} ${s.id}-${s.title}`);
  problems.forEach((p) => console.log(`          ${p}`));
}

console.log(`\n${sheets.length} sheets · ${bad} problem(s)`);
await browser.close();
