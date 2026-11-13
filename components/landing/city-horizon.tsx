"use client";

/*
 * The closing scene's skyline, after the Dort landing's CityHorizon: a curved horizon glowing from behind,
 * a far and a near city layer standing on it, a few lit windows and square markers on rooftops. Drawn
 * from a seeded generator, so every render draws the same city.
 */

const W = 1600;
const H = 760;
const CX = W / 2;
const horizon = (x: number) => 430 + ((x - CX) / CX) ** 2 * 130;
const TOP = 230;
const r1 = (n: number) => Math.round(n * 10) / 10;

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type Bld = { x: number; w: number; y: number; h: number; mast: boolean };

function skyline(seed: number, scale: number, lift: number, minW: number) {
  const rand = rng(seed);
  const out: Bld[] = [];
  let x = -20;
  while (x < W + 20) {
    const w = minW + rand() * minW * 2.2;
    const near = 1 - Math.min(1, Math.abs(x + w / 2 - CX) / CX);
    const h = (14 + rand() * 34 + near ** 1.6 * 120 * rand()) * scale;
    const ground = horizon(x + w / 2) - lift;
    out.push({ x, w, y: ground - h, h, mast: near > 0.55 && rand() > 0.72 });
    x += w + 1.5 + rand() * 3;
  }
  return out;
}

const FAR = skyline(11, 0.7, 26, 10);
const NEAR = skyline(7, 1, 0, 14);
const WINDOWS = (() => {
  const rand = rng(3);
  const out: { x: number; y: number; o: number }[] = [];
  for (const b of NEAR) {
    const n = Math.floor((b.h / 40) * rand() * 2);
    for (let i = 0; i < n; i++) out.push({ x: r1(b.x + 3 + rand() * (b.w - 6)), y: r1(b.y + 6 + rand() * Math.max(4, b.h - 12)), o: 0.25 + rand() * 0.5 });
  }
  return out;
})();
const MARKERS = [0.33, 0.47, 0.61, 0.74].map((f) => {
  const b = NEAR.reduce((best, c) => (Math.abs(c.x - W * f) < Math.abs(best.x - W * f) ? c : best));
  return { x: r1(b.x + b.w / 2), y: r1(b.y - 26) };
});

const block = (b: Bld) => `M${r1(b.x)} ${r1(b.y)}h${r1(b.w)}V${H}H${r1(b.x)}Z`;
const roof = (b: Bld) => `M${r1(b.x)} ${r1(b.y)}h${r1(b.w)}`;
const rimAlpha = (b: Bld) => r1((0.12 + (1 - Math.abs(b.x + b.w / 2 - CX) / CX) * 0.5) * 100) / 100;

function byAlpha<T>(items: T[], alpha: (t: T) => number, d: (t: T) => string) {
  const out = new Map<number, string>();
  for (const t of items) {
    const a = Math.round(alpha(t) * 25) / 25;
    out.set(a, (out.get(a) ?? "") + d(t));
  }
  return [...out];
}
const FAR_D = FAR.map(block).join("");
const NEAR_D = NEAR.map(block).join("");
const ROOFS = byAlpha(NEAR, rimAlpha, roof);
const MASTS = NEAR.filter((b) => b.mast).map((b) => `M${r1(b.x + b.w / 2)} ${r1(b.y)}v-18`).join("");
const LITW = byAlpha(WINDOWS, (w) => w.o, (w) => `M${w.x} ${w.y}h1.6v1.6h-1.6z`);

export function CityHorizon() {
  return (
    <svg aria-hidden="true" viewBox={`0 ${TOP} ${W} ${H - TOP}`} preserveAspectRatio="xMidYMax slice"
      className="pointer-events-none absolute inset-x-0 bottom-0 h-[340px] w-full md:h-[clamp(420px,42vw,640px)]">
      <defs>
        <radialGradient id="ln-dawn" cx="50%" cy="34%" r="58%">
          <stop offset="0" stopColor="#eef0f5" stopOpacity=".5" />
          <stop offset=".22" stopColor="#b4b9c6" stopOpacity=".22" />
          <stop offset=".55" stopColor="#5b6070" stopOpacity=".06" />
          <stop offset="1" stopColor="#000" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ln-ground" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#eef3fb" />
          <stop offset="1" stopColor="#e3ebf7" />
        </linearGradient>
        <linearGradient id="ln-fadein" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0647b3" stopOpacity="1" />
          <stop offset="1" stopColor="#0647b3" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect y={TOP} width={W} height={H - TOP} fill="url(#ln-dawn)" />
      <rect y={TOP} width={W} height="150" fill="url(#ln-fadein)" />
      <path fill="#ffffff" d={FAR_D} />
      <path fill="url(#ln-ground)" d={NEAR_D} />
      <g strokeWidth="1">
        {ROOFS.map(([a, d]) => <path key={a} d={d} stroke={`rgba(255,255,255,${a})`} />)}
        <path d={MASTS} stroke="rgba(255,255,255,.35)" />
      </g>
      <g fill="#fff">{LITW.map(([a, d]) => <path key={a} d={d} opacity={a} />)}</g>
      <g>
        {MARKERS.map((m) => (
          <g key={`k${m.x}`}>
            <path d={`M${m.x} ${m.y + 6}V${m.y + 26}`} stroke="rgba(255,255,255,.35)" />
            <rect x={m.x - 5} y={m.y - 5} width="10" height="10" fill="#0647b3" stroke="#fff" strokeWidth="1" />
            <rect x={m.x - 2} y={m.y - 2} width="4" height="4" fill="#fff" />
          </g>
        ))}
      </g>
      <rect y={H - 220} width={W} height="220" fill="url(#ln-ground)" opacity=".85" />
    </svg>
  );
}
