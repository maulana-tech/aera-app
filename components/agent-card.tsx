import { Crown, ShieldBan } from "lucide-react";
import Link from "next/link";

import type { Agent } from "@/app/lib";
import { Badge } from "@/components/ui/badge";

/* ========================================================================== *
 * Authentic bloub.vercel.app SVG Avatar Engine (Grok-style bot shapes & eyes)
 * ========================================================================== */

const TAU = Math.PI * 2;
const SCALE = 100;
const ANGLES = Array.from({ length: 64 }, (_, i) => (i / 64) * TAU);
const COS = ANGLES.map(Math.cos);
const SIN = ANGLES.map(Math.sin);

const round2 = (n: number) => Math.round(n * 100) / 100;
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const deg2rad = (d: number) => (d * Math.PI) / 180;

type Point = { x: number; y: number };
type EyeSpec = { w: number; h: number; tilt?: number; open?: number };
type Gaze = { yaw: number; pitch: number; roll: number };
type ExpressionDef = {
  gaze: Gaze;
  split: number;
  eyes: [EyeSpec, EyeSpec];
};

function normalizeRadii(radii: number[], target = 1): number[] {
  const max = Math.max(...radii);
  if (max <= 0) return radii;
  const k = target / max;
  return radii.map((r) => r * k);
}

function superellipseRadii(p: number, a = 1, b = 1): number[] {
  return ANGLES.map((_, i) =>
    (Math.abs((COS[i] ?? 0) / a) ** p + Math.abs((SIN[i] ?? 0) / b) ** p) ** (-1 / p),
  );
}

function raycastPolygon(poly: Point[], cx: number, cy: number): number[] {
  const out = Array<number>(64).fill(0);
  const len = poly.length;
  for (let i = 0; i < 64; i++) {
    const dx = COS[i] ?? 0;
    const dy = SIN[i] ?? 0;
    let best = 0;
    for (let j = 0; j < len; j++) {
      const p1 = poly[j]!;
      const p2 = poly[(j + 1) % len]!;
      const ex = p2.x - p1.x;
      const ey = p2.y - p1.y;
      const det = dx * ey - dy * ex;
      if (Math.abs(det) < 1e-9) continue;
      const px = p1.x - cx;
      const py = p1.y - cy;
      const t = (px * ey - py * ex) / det;
      const u = (px * dy - py * dx) / det;
      if (t > best && u >= 0 && u <= 1) best = t;
    }
    out[i] = best;
  }
  return out;
}

function tangentHull(
  x1: number,
  y1: number,
  r1: number,
  x2: number,
  y2: number,
  r2: number,
  steps = 96,
): Point[] {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const dist = Math.hypot(dx, dy) || 1e-6;
  const base = Math.atan2(dy, dx);
  const spread = Math.acos(Math.max(-1, Math.min(1, (r1 - r2) / dist)));
  const pts: Point[] = [];
  for (let i = 0; i <= steps / 2; i++) {
    const a = base + spread + ((TAU - 2 * spread) * i) / (steps / 2);
    pts.push({ x: x1 + Math.cos(a) * r1, y: y1 + Math.sin(a) * r1 });
  }
  for (let i = 0; i <= steps / 2; i++) {
    const a = base - spread + (2 * spread * i) / (steps / 2);
    pts.push({ x: x2 + Math.cos(a) * r2, y: y2 + Math.sin(a) * r2 });
  }
  return pts;
}

function roundedNgonRadii(sides: number, outer: number, corner: number, rotDeg = 0): number[] {
  const rot = deg2rad(rotDeg);
  const verts = Array.from({ length: sides }, (_, i) => {
    const a = rot + (i / sides) * TAU;
    return { x: Math.cos(a) * (outer - corner), y: Math.sin(a) * (outer - corner) };
  });
  const poly: Point[] = [];
  const normalAngle = (a: Point, b: Point) => {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const d = Math.hypot(dx, dy) || 1;
    return Math.atan2(-dx / d, dy / d);
  };
  for (let i = 0; i < sides; i++) {
    const prev = verts[(i - 1 + sides) % sides]!;
    const cur = verts[i]!;
    const next = verts[(i + 1) % sides]!;
    const a0 = normalAngle(prev, cur);
    let da = normalAngle(cur, next) - a0;
    while (da > Math.PI) da -= TAU;
    while (da < -Math.PI) da += TAU;
    for (let s = 0; s <= 10; s++) {
      const a = a0 + (da * s) / 10;
      poly.push({ x: cur.x + Math.cos(a) * corner, y: cur.y + Math.sin(a) * corner });
    }
  }
  return raycastPolygon(poly, 0, 0);
}

function unionCirclesRadii(circles: { x: number; y: number; r: number }[]): number[] {
  const out = Array<number>(64).fill(0);
  for (let i = 0; i < 64; i++) {
    const dx = COS[i] ?? 0;
    const dy = SIN[i] ?? 0;
    let best = 0;
    for (const c of circles) {
      const b = dx * c.x + dy * c.y;
      const disc = b * b - (c.x * c.x + c.y * c.y - c.r * c.r);
      if (disc < 0) continue;
      const t = b + Math.sqrt(disc);
      if (t > best) best = t;
    }
    out[i] = best;
  }
  return out;
}

const EGG_RADII = [
  0.8369, 0.8424, 0.8497, 0.8585, 0.8674, 0.8775, 0.8878, 0.8983,
  0.9089, 0.9185, 0.9288, 0.9374, 0.9445, 0.9504, 0.9543, 0.9559,
  0.9555, 0.9519, 0.9466, 0.9389, 0.9302, 0.9193, 0.9085, 0.8969,
  0.8852, 0.8734, 0.8625, 0.8513, 0.8411, 0.8325, 0.8243, 0.8179,
  0.8137, 0.8112, 0.8102, 0.8128, 0.8178, 0.8262, 0.8374, 0.8518,
  0.8702, 0.8922, 0.9169, 0.9446, 0.9741, 1.0023, 1.0267, 1.0433,
  1.0481, 1.0393, 1.0216, 0.997, 0.9697, 0.9418, 0.9169, 0.8949,
  0.876, 0.8604, 0.849, 0.8394, 0.8337, 0.8314, 0.8305, 0.8326,
];

const SHAPES = {
  cercle: Array<number>(64).fill(1),
  galet: normalizeRadii(
    ANGLES.map((a) => 1 + 0.075 * Math.cos(2 * a + 0.5) + 0.035 * Math.cos(3 * a + 2.1)),
    1.02,
  ),
  squircle: normalizeRadii(superellipseRadii(4.2), 1.15),
  capsule: raycastPolygon(tangentHull(-0.42, 0, 0.62, 0.42, 0, 0.62), 0, 0),
  triangle: roundedNgonRadii(3, 1.12, 0.34, -90),
  hexagone: roundedNgonRadii(6, 1.04, 0.26, 0),
  pentagone: roundedNgonRadii(5, 1.08, 0.28, -90),
  diamond: roundedNgonRadii(4, 1.12, 0.3, 0),
  nuage: normalizeRadii(
    unionCirclesRadii([
      { x: -0.44, y: 0.2, r: 0.54 },
      { x: 0.46, y: 0.2, r: 0.5 },
      { x: 0.02, y: 0.3, r: 0.6 },
      { x: -0.24, y: -0.3, r: 0.48 },
      { x: 0.3, y: -0.24, r: 0.44 },
    ]),
    1.02,
  ),
  goutte: normalizeRadii(raycastPolygon(tangentHull(0, 0.28, 0.66, 0, -0.96, 0.05), 0, 0), 1.04),
  octogone: roundedNgonRadii(8, 1.06, 0.24, 22.5),
  egg: EGG_RADII,
} as const;

type ShapeId = keyof typeof SHAPES;

const eye = (w: number, h: number, tilt = 0, open = 1): EyeSpec => ({ w, h, tilt, open });
const symEyes = (w: number, h: number, tilt = 0, open = 1): [EyeSpec, EyeSpec] => [
  eye(w, h, tilt, open),
  eye(w, h, -tilt, open),
];

const EXPRESSIONS: Record<string, ExpressionDef> = {
  neutre: { gaze: { yaw: 28.49, pitch: 28.62, roll: -13 }, split: 15.46, eyes: symEyes(0.186, 0.412) },
  attentif: { gaze: { yaw: 14, pitch: 12, roll: -6 }, split: 16, eyes: symEyes(0.21, 0.44) },
  surpris: { gaze: { yaw: 10, pitch: -5, roll: -4 }, split: 19, eyes: symEyes(0.42, 0.46) },
  excite: { gaze: { yaw: 14, pitch: 18, roll: -8 }, split: 19.5, eyes: symEyes(0.34, 0.5, -10) },
  heureux: { gaze: { yaw: 15, pitch: 12, roll: -8 }, split: 17, eyes: symEyes(0.27, 0.19, 14) },
  hilare: { gaze: { yaw: 12, pitch: 16, roll: -6 }, split: 18, eyes: symEyes(0.33, 0.15, 20) },
  colere: { gaze: { yaw: 10, pitch: 10, roll: -4 }, split: 17, eyes: symEyes(0.33, 0.16, 28) },
  triste: { gaze: { yaw: 12, pitch: -13, roll: -5 }, split: 16, eyes: symEyes(0.22, 0.4, -26) },
  effraye: { gaze: { yaw: -14, pitch: 12, roll: 6 }, split: 19, eyes: symEyes(0.34, 0.52) },
  mefiant: { gaze: { yaw: 18, pitch: 8, roll: -8 }, split: 16, eyes: [eye(0.21, 0.42), eye(0.23, 0.16)] },
  confus: { gaze: { yaw: -16, pitch: 6, roll: 10 }, split: 16.5, eyes: [eye(0.2, 0.44, -18), eye(0.28, 0.18, 14)] },
  curieux: { gaze: { yaw: 20, pitch: -9, roll: -15 }, split: 16.5, eyes: [eye(0.24, 0.46, -8), eye(0.2, 0.38, -8)] },
  fier: { gaze: { yaw: 16, pitch: 17, roll: -9 }, split: 17, eyes: symEyes(0.3, 0.17, 18) },
  timide: { gaze: { yaw: -19, pitch: -14, roll: -7 }, split: 14, eyes: symEyes(0.18, 0.32) },
  blase: { gaze: { yaw: -20, pitch: 4, roll: 5 }, split: 16, eyes: symEyes(0.3, 0.14) },
  somnolent: { gaze: { yaw: 14, pitch: -8, roll: -6 }, split: 16, eyes: symEyes(0.21, 0.42, 0, 0.48) },
};

function sampleRadius(radii: readonly number[], angle: number): number {
  const n = radii.length;
  const pos = (((angle / TAU) % 1) + 1) % 1 * n;
  const idx = Math.floor(pos);
  return lerp(radii[idx % n] ?? 1, radii[(idx + 1) % n] ?? 1, pos - idx);
}

function contourPoints(radii: readonly number[], rot = 0, scale = SCALE): Point[] {
  const c = Math.cos(rot);
  const s = Math.sin(rot);
  return Array.from({ length: 64 }, (_, i) => {
    const r = radii[i] ?? 1;
    const x0 = r * (COS[i] ?? 0);
    const y0 = r * (SIN[i] ?? 0);
    return {
      x: (x0 * c - y0 * s) * scale,
      y: (x0 * s + y0 * c) * scale,
    };
  });
}

function splinePath(pts: Point[], tension = 1 / 6): string {
  const n = pts.length;
  if (n < 3) return "";
  const first = pts[0]!;
  let d = `M${round2(first.x)} ${round2(first.y)}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n]!;
    const p1 = pts[i]!;
    const p2 = pts[(i + 1) % n]!;
    const p3 = pts[(i + 2) % n]!;
    const c1x = p1.x + (p2.x - p0.x) * tension;
    const c1y = p1.y + (p2.y - p0.y) * tension;
    const c2x = p2.x - (p3.x - p1.x) * tension;
    const c2y = p2.y - (p3.y - p1.y) * tension;
    d += `C${round2(c1x)} ${round2(c1y)} ${round2(c2x)} ${round2(c2y)} ${round2(p2.x)} ${round2(p2.y)}`;
  }
  return `${d}Z`;
}

function pillPath(w: number, h: number): string {
  const hw = Math.max(w, 0.01) / 2;
  const hh = Math.max(h, 0.01) / 2;
  const r = Math.min(hw, hh);
  return (
    `M${round2(-hw)} ${round2(-hh + r)}` +
    `A${round2(r)} ${round2(r)} 0 0 1 ${round2(-hw + r)} ${round2(-hh)}` +
    `L${round2(hw - r)} ${round2(-hh)}` +
    `A${round2(r)} ${round2(r)} 0 0 1 ${round2(hw)} ${round2(-hh + r)}` +
    `L${round2(hw)} ${round2(hh - r)}` +
    `A${round2(r)} ${round2(r)} 0 0 1 ${round2(hw - r)} ${round2(hh)}` +
    `L${round2(-hw + r)} ${round2(hh)}` +
    `A${round2(r)} ${round2(r)} 0 0 1 ${round2(-hw)} ${round2(hh - r)}Z`
  );
}

type Vec3 = [number, number, number];

function rotatePair(u: Vec3, v: Vec3, rad: number): [Vec3, Vec3] {
  const c = Math.cos(rad);
  const s = Math.sin(rad);
  return [
    [u[0] * c + v[0] * s, u[1] * c + v[1] * s, u[2] * c + v[2] * s],
    [v[0] * c - u[0] * s, v[1] * c - u[1] * s, v[2] * c - u[2] * s],
  ];
}

function projectEyes(gaze: Gaze, scale: number, split: number) {
  let fwd: Vec3 = [0, 0, 1];
  let right: Vec3 = [1, 0, 0];
  let up: Vec3 = [0, 1, 0];
  [fwd, right] = rotatePair(fwd, right, deg2rad(gaze.yaw));
  [up, fwd] = rotatePair(up, fwd, deg2rad(gaze.pitch));
  [right, up] = rotatePair(right, up, deg2rad(gaze.roll));

  const projectOne = (sign: -1 | 1) => {
    const [dir, tang] = rotatePair(fwd, right, deg2rad(split * sign));
    return {
      x: dir[0] * scale,
      y: dir[1] * scale,
      a: tang[0],
      b: tang[1],
      c: up[0],
      d: up[1],
      depth: dir[2],
    };
  };
  return [projectOne(-1), projectOne(1)] as const;
}

type AgentBotStyle = {
  shape: ShapeId;
  expression: keyof typeof EXPRESSIONS;
  color: string;
  rotDeg?: number;
};

/**
 * Each of the 12 SIGAP agents gets a distinct Bloub silhouette, expression, and color
 * tailored to their role on the supply-chain response team.
 */
const AGENT_BOT_STYLES: Record<string, AgentBotStyle> = {
  // 1. Arya (Supervisor / Team Lead) — Classic Grok ink-black sphere, confident leader
  Arya: { shape: "cercle", expression: "attentif", color: "#0a0a0c", rotDeg: 0 },
  // 2. Elsa (Impact) — Orange rounded triangle, wide-eyed alert on disruption impact
  Elsa: { shape: "triangle", expression: "surpris", color: "#f08a24", rotDeg: 0 },
  // 3. Dara (Demand) — Rose-pink cloud, curious head-tilt tracking demand shifts
  Dara: { shape: "nuage", expression: "curieux", color: "#e152b0", rotDeg: -6 },
  // 4. Iris (Inventory / Stock Validity) — Turquoise squircle crate, focused inspector
  Iris: { shape: "squircle", expression: "neutre", color: "#2fbfa0", rotDeg: -8 },
  // 5. Clint (Sourcing) — Emerald capsule, upbeat scout finding replacement sources
  Clint: { shape: "capsule", expression: "heureux", color: "#3ecf8e", rotDeg: -14 },
  // 6. Prita (Procurement) — Violet hexagon, shrewd one-brow-raised quote negotiator
  Prita: { shape: "hexagone", expression: "mefiant", color: "#8b5cf6", rotDeg: 12 },
  // 7. Milo (Logistics) — Ocean-blue droplet, energetic maritime tracker
  Milo: { shape: "goutte", expression: "excite", color: "#3b93f0", rotDeg: 0 },
  // 8. Kira (Compliance / Veto) — Crimson diamond shield, fierce rule enforcer
  Kira: { shape: "diamond", expression: "colere", color: "#e8483f", rotDeg: 0 },
  // 9. Tara (Simulation / Costing) — Amber-gold pebble, proud & precise calculator
  Tara: { shape: "galet", expression: "fier", color: "#f0b429", rotDeg: 15 },
  // 10. Otto (Precedent / Memory) — Warm brown egg, wise seen-it-all historian
  Otto: { shape: "egg", expression: "somnolent", color: "#8b5e3c", rotDeg: -8 },
  // 11. Bram (Execution / SAP) — Electric cyan pentagon, cheerful action executor
  Bram: { shape: "pentagone", expression: "hilare", color: "#06b6d4", rotDeg: 8 },
  // 12. Vega (Exposure / Risk Scanner) — Royal-indigo octagon with large wide-open scanner eyes
  Vega: { shape: "octogone", expression: "effraye", color: "#4f46e5", rotDeg: 0 },
};

const FALLBACK_STYLES: AgentBotStyle[] = Object.values(AGENT_BOT_STYLES);

function renderBloubGeometry(style: AgentBotStyle) {
  const radii = SHAPES[style.shape] ?? SHAPES.cercle;
  const expr = EXPRESSIONS[style.expression] ?? EXPRESSIONS.neutre;
  const rot = deg2rad(style.rotDeg ?? 0);
  const bodyPath = splinePath(contourPoints(radii, rot, SCALE));
  const projected = projectEyes(expr.gaze, SCALE, expr.split);

  const eyes = projected.map((proj, idx) => {
    const spec = expr.eyes[idx]!;
    const rScale = sampleRadius(radii, Math.atan2(proj.y, proj.x) - rot) * 0.78;
    const tiltRad = deg2rad(spec.tilt ?? 0);
    const cosT = Math.cos(tiltRad);
    const sinT = Math.sin(tiltRad);
    const d = proj.a * cosT + proj.c * sinT;
    const f = proj.b * cosT + proj.d * sinT;
    const p = -proj.a * sinT + proj.c * cosT;
    const m = -proj.b * sinT + proj.d * cosT;
    const open = 0.06 + 0.94 * Math.max(0, Math.min(1, spec.open ?? 1));
    const tx = proj.x * rScale;
    const ty = proj.y * rScale;
    return {
      d: pillPath(spec.w * SCALE, spec.h * SCALE),
      matrix: `matrix(${round2(d)},${round2(f * open)},${round2(p)},${round2(m * open)},${round2(tx)},${round2(ty)})`,
    };
  });

  return { bodyPath, eyes, color: style.color };
}

const GEOMETRY_CACHE = new Map<string, ReturnType<typeof renderBloubGeometry>>();

function getBotGeometry(nickname: string) {
  const cached = GEOMETRY_CACHE.get(nickname);
  if (cached) return cached;
  const style =
    AGENT_BOT_STYLES[nickname] ??
    FALLBACK_STYLES[nickname.charCodeAt(0) % FALLBACK_STYLES.length]!;
  const geom = renderBloubGeometry(style);
  GEOMETRY_CACHE.set(nickname, geom);
  return geom;
}

/** Per-agent badge colour, kept exported for any callers that still import hue. */
const HUES = [
  "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  "bg-violet-500/15 text-violet-700 dark:text-violet-400",
  "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  "bg-rose-500/15 text-rose-700 dark:text-rose-400",
  "bg-teal-500/15 text-teal-700 dark:text-teal-400",
];
export const hue = (s: string) => HUES[s.charCodeAt(0) % HUES.length];

export function AgentBadge({
  nickname,
  large,
  size,
  showTooltip,
}: {
  nickname: string;
  large?: boolean;
  size?: "xs" | "sm" | "lg";
  showTooltip?: boolean;
}) {
  const { bodyPath, eyes, color } = getBotGeometry(nickname);
  const isInk = color === "#0a0a0c";
  const isXs = size === "xs";
  const sizeClass = isXs
    ? "size-4"
    : large || size === "lg"
      ? "size-11"
      : "size-8";
  const withTooltip = showTooltip ?? !isXs;

  return (
    <span
      className={`group/badge relative inline-flex shrink-0 items-center justify-center select-none hover:z-30 ${sizeClass}`}
    >
      <svg
        viewBox="-122 -122 244 244"
        className={`size-full overflow-visible drop-shadow-[0_1px_2px_rgba(0,0,0,0.12)] transition-transform duration-200 ease-out ${
          isXs
            ? "group-hover/badge:scale-125 group-hover/menu-sub-item:scale-125"
            : "group-hover/badge:-translate-y-0.5 group-hover/badge:scale-[1.32] group-hover/badge:drop-shadow-[0_4px_8px_rgba(0,0,0,0.2)]"
        }`}
        role="img"
        aria-label={nickname}
      >
        <path
          d={bodyPath}
          fill={color}
          stroke={isInk ? "rgba(255,255,255,0.22)" : "none"}
          strokeWidth={isInk ? 6 : 0}
        />
        {eyes.map((e, i) => (
          <path key={i} d={e.d} transform={e.matrix} fill="#ffffff" />
        ))}
      </svg>

      {withTooltip && (
        <span
          role="tooltip"
          className="bg-foreground text-background pointer-events-none absolute top-full left-1/2 z-50 mt-1.5 -translate-x-1/2 -translate-y-1 rounded-md px-2 py-0.5 text-[11px] font-medium whitespace-nowrap opacity-0 shadow-md transition-all duration-150 ease-out group-hover/badge:translate-y-0 group-hover/badge:opacity-100"
        >
          <span className="border-b-foreground absolute -top-1.5 left-1/2 -translate-x-1/2 border-4 border-transparent" />
          {nickname}
        </span>
      )}
    </span>
  );
}

export function AgentCard({ a }: { a: Agent }) {
  const complete = a.installed === a.tool_count;
  return (
    <Link
      href={`/agents/${a.code}`}
      className="hover:border-foreground/30 hover:bg-muted/30 group block rounded-lg border p-4 transition-colors"
    >
      <div className="flex items-start gap-3">
        <AgentBadge nickname={a.nickname} large />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h3 className="font-medium leading-none">{a.nickname}</h3>
            <span className="text-muted-foreground text-xs">{a.title}</span>
            {a.lead && <Crown className="size-3.5 shrink-0" />}
            {a.veto && (
              <Badge variant="outline" className="h-5 gap-1 px-1.5 font-mono text-[9px]">
                <ShieldBan className="size-2.5" />
                veto
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1.5 line-clamp-2 text-xs leading-relaxed">
            {a.brief}
          </p>
          <p
            className={`mt-2 font-mono text-[10px] ${
              complete ? "text-muted-foreground" : "text-amber-700 dark:text-amber-400"
            }`}
          >
            {a.installed}/{a.tool_count} tools
            {!a.ready && " · no prompt"}
            {a.used_in > 0 && ` · ${a.used_in} disruptions`}
          </p>
        </div>
      </div>
    </Link>
  );
}
