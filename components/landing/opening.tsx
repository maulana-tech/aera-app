/*
 * The opening screen, after the Dort landing's (components/landing/Opening.tsx there): a small eyebrow over
 * one enormous light headline, and under it an isometric model seen from above, its far edge dissolving
 * into the page. White pills float over single blocks, each carrying one number read from the public
 * ledger, and one block is lit: the one the Guardian's number sits on, because that is the subject.
 */

const HW = 46;
const HD = 23;
const N = 9;
const VB = { x: -430, y: -180, w: 860, h: 600 };

const BG = [9, 74, 180];
const FACE = { top: [112, 150, 211], left: [78, 125, 201], right: [53, 107, 194] };
const LIT = { top: [255, 255, 255], left: [214, 228, 250], right: [185, 205, 240] };

const mix = (c: number[], t: number) => `rgb(${c.map((v, k) => Math.round(v + (BG[k]! - v) * t)).join(",")})`;

/** A deterministic height per cell, so the server and the client draw the same model. */
function heightAt(i: number, j: number): number {
  const h = Math.sin(i * 12.9898 + j * 78.233) * 43758.5453;
  return h - Math.floor(h);
}

type Block = { i: number; j: number; h: number; cx: number; cy: number; xf: number; yf: number; depth: number };

function model(): Block[] {
  const out: Block[] = [];
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const r = heightAt(i, j);
      if (r < 0.26) continue;
      const h = 26 + r * 132;
      const cx = (i - j) * HW;
      const cy = (i + j) * HD;
      out.push({ i, j, h, cx, cy, xf: (cx - VB.x) / VB.w, yf: (cy - h - VB.y) / VB.h, depth: 1 - (i + j) / (2 * (N - 1)) });
    }
  }
  return out.sort((a, b) => a.i + a.j - (b.i + b.j));
}

function Box({ b, lit }: { b: Block; lit: boolean }) {
  const { cx, cy, h } = b;
  const t = cy - h;
  const f = lit ? LIT : FACE;
  const d = lit ? 0 : b.depth * 0.68;
  return (
    <g>
      <polygon points={`${cx},${t} ${cx + HW},${t + HD} ${cx},${t + HD * 2} ${cx - HW},${t + HD}`} fill={mix(f.top, d)} />
      <polygon points={`${cx - HW},${t + HD} ${cx},${t + HD * 2} ${cx},${cy + HD * 2} ${cx - HW},${cy + HD}`} fill={mix(f.left, d)} />
      <polygon points={`${cx + HW},${t + HD} ${cx},${t + HD * 2} ${cx},${cy + HD * 2} ${cx + HW},${cy + HD}`} fill={mix(f.right, d)} />
    </g>
  );
}

/** The tallest block in a band that is solid and on screen: pills hang off real apexes. */
function anchor(bs: Block[], from: number, to: number, top: number, bottom: number, used: Block[]) {
  return bs.filter((b) => b.xf >= from && b.xf <= to && b.yf > top && b.yf < bottom && !used.includes(b))
    .sort((a, b) => a.yf - b.yf)[0];
}

export type OpeningStat = { value: string; label: string; bad?: boolean };

export function Opening({ stats }: { stats: [OpeningStat, OpeningStat, OpeningStat, OpeningStat] }) {
  const bs = model();
  const used: Block[] = [];
  const lit = anchor(bs, 0.36, 0.58, 0.26, 0.5, used) ?? bs[0]!;
  used.push(lit);
  const spots: { s: OpeningStat; b: Block | undefined }[] = [
    { s: stats[0], b: anchor(bs, 0.06, 0.28, 0.34, 0.62, used) },
    { s: stats[1], b: lit },
    { s: stats[2], b: anchor(bs, 0.68, 0.92, 0.4, 0.68, used) },
    { s: stats[3], b: anchor(bs, 0.34, 0.6, 0.56, 0.8, used) },
  ];
  for (const sp of spots) if (sp.b) used.push(sp.b);

  return (
    <section aria-label="What AERA runs" className="relative overflow-hidden">
      <div className="relative mx-auto flex min-h-[calc(100svh-76px)] max-w-[1240px] flex-col px-4 pt-10 md:px-6 md:pt-12">
        <div className="lo-head relative z-20 text-center">
          <p className="text-on-canvas-dim text-[clamp(13px,1.3vw,16px)]">A business that</p>
          <h1 className="mt-1 text-[clamp(52px,12vw,170px)] leading-[0.92] font-light tracking-[-0.045em] text-white">
            runs itself.
          </h1>
        </div>
        <div className="relative z-10 grow">
          <div className="lo-model">
            <svg viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`} aria-hidden="true" className="block w-full">
              {bs.map((b) => <Box key={`${b.i}-${b.j}`} b={b} lit={b === lit} />)}
            </svg>
            {spots.filter((p) => p.b).map((p) => (
              <span key={p.s.label} className="lo-pill" style={{ left: `${p.b!.xf * 100}%`, top: `${p.b!.yf * 100}%` }}>
                <span className={`lo-dot ${p.s.bad ? "lo-dot-bad" : ""}`} />
                <span className="font-mono text-[13px]">{p.s.value}</span>
                <span className="text-muted-foreground text-[12.5px]">{p.s.label}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
