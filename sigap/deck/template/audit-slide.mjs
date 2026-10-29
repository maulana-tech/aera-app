/**
 * Measure a deck built on the organiser's template.
 *
 *   npm run build && npm run preview          # in sigap/deck
 *   node template/audit-slide.mjs sigap-10 10
 *
 * The canvas does not scroll and the gradient is not a background you can put
 * dark text on, so both failures are silent: content past the edge disappears,
 * content over the purple goes unreadable on a projector. This measures every
 * text element against the zones in README.md instead of trusting the eye.
 */
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const pw = await import('playwright').catch(() => {
  const dir = process.env.PLAYWRIGHT_DIR;
  if (!dir) { console.error('playwright not found; set PLAYWRIGHT_DIR'); process.exit(1); }
  return import(pathToFileURL(path.join(dir, 'playwright', 'index.js')).href);
});
const { chromium } = pw.chromium ? pw : pw.default;

const SLIDE = process.argv[2] || 'sigap-10';
const TOTAL = Number(process.argv[3] || 10);
const BASE = process.env.PREVIEW || 'http://localhost:4173';

/** Same numbers as plot.mjs GEO, re-stated here so this file stands alone. */
const GEO = {
  canvas: { w: 1920, h: 1080 },
  brand: {
    sokrates: { x: 82, y: 58, w: 282, h: 82 },
    hackathon: { x: 1452, y: 52, w: 392, h: 130 },
    partners: { x: 66, y: 912, w: 510, h: 112 },
    photo: { x: 1460, y: 834, w: 458, h: 244 },
  },
  band: { x: 80, y: 240, r: 1840, b: 900 },
  white: { wideBottom: 500, wideRight: 1032, tallRight: 768 },
};

const browser = await chromium.launch();
const tab = await browser.newPage({ viewport: { width: 1920, height: 1200 }, deviceScaleFactor: 1 });

let bad = 0;
for (let n = 1; n <= TOTAL; n++) {
  await tab.goto(`${BASE}/s/${SLIDE}?p=${n}`, { waitUntil: 'networkidle' });
  await tab.waitForTimeout(350);

  const problems = await tab.evaluate((G) => {
    const canvases = [...document.querySelectorAll('*')].filter((el) => {
      const s = getComputedStyle(el);
      return s.width === '1920px' && s.height === '1080px';
    });
    if (!canvases.length) return ['no canvas found'];
    const stage = canvases.reduce((a, b) =>
      b.getBoundingClientRect().width > a.getBoundingClientRect().width ? b : a);
    const cr = stage.getBoundingClientRect();
    const scale = cr.width / 1920;
    const box = (el) => {
      const r = el.getBoundingClientRect();
      return {
        top: (r.top - cr.top) / scale, left: (r.left - cr.left) / scale,
        bottom: (r.bottom - cr.top) / scale, right: (r.right - cr.left) / scale,
        w: r.width / scale, h: r.height / scale,
      };
    };
    const lum = (c) => {
      const [r, g, b] = (c.match(/[\d.]+/g) || [0, 0, 0]).map(Number);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    // A white card carries its own background, so anything inside one is fine.
    const cards = [...stage.querySelectorAll('*')].filter((el) => {
      const s = getComputedStyle(el);
      const b = box(el);
      // Smaller than the stage: the viewer wraps every page in a full-bleed
      // white div, and counting that as a card excused every element on every
      // page from the zone, contrast and overlap rules below.
      return /rgba?\(255,\s*255,\s*255/.test(s.backgroundColor)
        && b.w > 600 && b.h > 300 && b.w < 1900 && b.h < 1040;
    }).map(box);

    const out = [];
    const laid = [];
    for (const el of stage.querySelectorAll('h1,h2,p,span,div,img')) {
      if (el.children.length > 0 && el.tagName !== 'IMG') continue;   // leaves only
      const text = (el.textContent || el.getAttribute('alt') || '').trim();
      if (el.tagName !== 'IMG' && !text) continue;
      const b = box(el);
      if (b.w === 0 && b.h === 0) continue;
      const name = `"${text.slice(0, 40) || el.tagName}"`;

      if (b.left < 0 || b.top < 0 || b.right > G.canvas.w || b.bottom > G.canvas.h) {
        out.push(`off canvas ${name} [${Math.round(b.left)},${Math.round(b.top)} → ${Math.round(b.right)},${Math.round(b.bottom)}]`);
        continue;
      }
      for (const [bn, z] of Object.entries(G.brand)) {
        if (b.left < z.x + z.w && b.right > z.x && b.top < z.y + z.h && b.bottom > z.y) {
          out.push(`covers the organiser's ${bn}: ${name}`);
        }
      }
      if (cards.some((c) => b.left >= c.left - 1 && b.right <= c.right + 1
        && b.top >= c.top - 1 && b.bottom <= c.bottom + 1)) continue;

      if (el.tagName === 'IMG') continue;
      if (lum(getComputedStyle(el).color) > 150) {
        if (b.right > G.band.r || b.bottom > G.band.b) {
          out.push(`light text leaves the band ${name} right=${Math.round(b.right)} bottom=${Math.round(b.bottom)}`);
        }
        continue;
      }
      const limit = b.bottom <= G.white.wideBottom ? G.white.wideRight : G.white.tallRight;
      if (b.left < G.band.x || b.top < G.band.y || b.bottom > G.band.b || b.right > limit) {
        out.push(`dark text leaves the white zone ${name} right=${Math.round(b.right)} (max ${limit}) bottom=${Math.round(b.bottom)} (max ${G.band.b})`);
      }
      laid.push({ b, name });
    }

    // Two pieces of text on top of each other stay inside every zone and still
    // ruin the page - the first version of the numbers page printed its
    // footnote straight through "Rp 46 jt". Zones alone do not catch that.
    for (let i = 0; i < laid.length; i++) {
      for (let j = i + 1; j < laid.length; j++) {
        const a = laid[i].b, c = laid[j].b;
        const ox = Math.min(a.right, c.right) - Math.max(a.left, c.left);
        const oy = Math.min(a.bottom, c.bottom) - Math.max(a.top, c.top);
        // A few pixels of leading overlap is normal; a real collision is both
        // wide and tall.
        if (ox > 12 && oy > 10) {
          out.push(`text overlaps text: ${laid[i].name} and ${laid[j].name} (${Math.round(ox)}x${Math.round(oy)}px)`);
        }
      }
    }
    return out;
  }, GEO);

  bad += problems.length;
  console.log(`${problems.length ? 'PROBLEM' : 'ok     '} p${String(n).padStart(2, '0')}`);
  problems.forEach((p) => console.log(`          ${p}`));
}

console.log(`\n${TOTAL} pages · ${bad} problem(s)`);
await browser.close();
process.exit(bad ? 1 : 0);
