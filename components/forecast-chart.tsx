"use client";

import { useState } from "react";

import { ChartTooltip } from "@/components/chart-tooltip";

export type ForecastPoint = { on: string; point: number; lower: number; upper: number };
export type Observed = { on: string; qty: number; mean: number };

/* A forecast is a range, so the chart has to draw one.
 *
 * One hue throughout. Observed and forecast are told apart by line style, never
 * by a second colour, because identity carried by colour alone fails for a
 * colour-blind reader. The band is the same hue at low opacity, so it reads as
 * the same quantity rather than a second series.
 *
 * The planned rate is a dashed rule in the border token, not a series colour.
 * It is a threshold, not data, and the whole point of the chart is that the
 * forecast sits above it.
 */

const W = 720;
const H = 240;
const PAD = { top: 16, right: 14, bottom: 26, left: 44 };

const short = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

export function ForecastChart({
  observed, points, plannedRate, unit, confidence, windowDays = 7,
}: {
  observed: Observed[];
  points: ForecastPoint[];
  plannedRate: number | null;
  unit: string;
  confidence: number;
  windowDays?: number;
}) {
  // Both are needed: `at` picks the column, `cursorY` places the tooltip. Anchoring
  // the tooltip to the line instead made pointing anywhere in the band look dead,
  // because the card appeared far above where the pointer actually was.
  const [at, setAt] = useState<number | null>(null);
  const [cursorY, setCursorY] = useState(0);

  // The trailing mean is the signal. The daily series is context behind it.
  const all = [
    ...observed.map((o) => ({ on: o.on, v: o.mean, raw: o.qty, kind: "observed" as const })),
    ...points.map((p) => ({ on: p.on, v: p.point, raw: p.point, kind: "forecast" as const })),
  ];
  if (all.length === 0) return null;

  const top = Math.max(
    ...points.map((p) => p.upper),
    ...observed.map((o) => o.qty),
    plannedRate ?? 0,
  ) * 1.1;

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (i / Math.max(all.length - 1, 1)) * plotW;
  const y = (v: number) => PAD.top + plotH - (v / (top || 1)) * plotH;

  const dailyPath = observed.map((o, i) => `${i ? "L" : "M"}${x(i)},${y(o.qty)}`).join(" ");
  const obsPath = observed.map((o, i) => `${i ? "L" : "M"}${x(i)},${y(o.mean)}`).join(" ");
  const offset = observed.length;
  // Join the last observed point to the first forecast point so the line is continuous.
  const fcStart = observed.length ? `M${x(offset - 1)},${y(observed[offset - 1].mean)} L` : "M";
  const fcPath = fcStart + points.map((p, i) => `${x(offset + i)},${y(p.point)}`).join(" L");
  const band =
    points.map((p, i) => `${i ? "L" : "M"}${x(offset + i)},${y(p.upper)}`).join(" ") +
    " " +
    points.map((p, i) => `L${x(offset + points.length - 1 - i)},${y(points[points.length - 1 - i].lower)}`).join(" ") +
    " Z";

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => +(top * f).toFixed(1));
  // A tick a week, so the eye can count horizon rather than guess it.
  const dateTicks = all
    .map((d, i) => ({ i, on: d.on }))
    .filter(({ i }) => (offset - 1 - i) % 7 === 0 && i > 0 && i < all.length - 1);
  const hovered = at === null ? null : all[at];
  const hoveredBand = at !== null && at >= offset ? points[at - offset] : null;

  return (
    <div className="viz relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Daily consumption, ${observed.length} days observed and ${points.length} forecast`}
        onMouseLeave={() => setAt(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const py = ((e.clientY - r.top) / r.height) * H;
          const i = Math.round(((px - PAD.left) / plotW) * (all.length - 1));
          setAt(Math.max(0, Math.min(all.length - 1, i)));
          setCursorY(Math.max(PAD.top, Math.min(PAD.top + plotH, py)));
        }}
      >
        {/* The whole plot answers the pointer, not just the 2px line. */}
        <rect
          x={PAD.left} y={PAD.top} width={plotW} height={plotH}
          fill="transparent"
        />

        {/* Grid stays recessive: it orients, it does not compete. */}
        {ticks.map((t, i) => (
          <g key={t}>
            <line
              x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)}
              stroke="var(--viz-rule)" strokeWidth="1"
              opacity={i === 0 ? 0.55 : 0.22}
            />
            <text
              x={PAD.left - 8} y={y(t) + 3} textAnchor="end"
              className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
            >
              {t}
            </text>
          </g>
        ))}
        {dateTicks.map(({ i, on }) => (
          <g key={on}>
            <line
              x1={x(i)} x2={x(i)} y1={PAD.top + plotH} y2={PAD.top + plotH + 4}
              stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
            />
            <text
              x={x(i)} y={H - 8} textAnchor="middle"
              className="fill-muted-foreground" fontSize="9" fontFamily="var(--font-mono)"
            >
              {short(on)}
            </text>
          </g>
        ))}

        <path d={band} fill="var(--viz-series)" opacity="0.16" />

        {plannedRate !== null && (
          <>
            <line
              x1={PAD.left} x2={W - PAD.right} y1={y(plannedRate)} y2={y(plannedRate)}
              stroke="var(--viz-rule)" strokeWidth="1.5" strokeDasharray="5 4"
            />
            <text
              x={PAD.left + 6} y={y(plannedRate) + 13}
              className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
            >
              planned {plannedRate}
            </text>
          </>
        )}

        <path
          d={dailyPath} fill="none" stroke="var(--viz-series)" strokeWidth="1"
          opacity="0.28"
        />
        <path d={obsPath} fill="none" stroke="var(--viz-series)" strokeWidth="2" />
        <path
          d={fcPath} fill="none" stroke="var(--viz-series)" strokeWidth="2"
          strokeDasharray="6 4"
        />

        {/* Where the record stops and the estimate starts. */}
        {observed.length > 0 && (
          <line
            x1={x(offset - 1)} x2={x(offset - 1)} y1={PAD.top} y2={PAD.top + plotH}
            stroke="var(--viz-rule)" strokeWidth="1" opacity="0.6"
          />
        )}

        {at !== null && (
          <>
            <line
              x1={x(at)} x2={x(at)} y1={PAD.top} y2={PAD.top + plotH}
              stroke="var(--viz-series)" strokeWidth="1" opacity="0.5"
            />
            <circle cx={x(at)} cy={y(all[at].v)} r="4" fill="var(--viz-series)" />
          </>
        )}

        <text
          x={x(offset - 1)} y={PAD.top + 10} textAnchor="middle"
          className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
        >
          today
        </text>
      </svg>

      {hovered && (
        <ChartTooltip
          x={(x(at!) / W) * 100}
          y={(cursorY / H) * 100}
          title={short(hovered.on)}
          subtitle={
            hovered.kind === "observed"
              ? `withdrawn, ${windowDays} day mean`
              : `forecast, ${windowDays} day mean`
          }
          rows={[
            { label: hovered.kind === "observed" ? "Mean" : "Expected",
              value: `${hovered.v} ${unit}` },
            ...(hovered.kind === "observed"
              ? [{ label: "That day", value: `${hovered.raw} ${unit}`, quiet: true }]
              : []),
            ...(hoveredBand
              ? [{ label: `${confidence}% range`,
                   value: `${hoveredBand.lower} to ${hoveredBand.upper}`, quiet: true }]
              : []),
            ...(plannedRate !== null
              ? [{ label: "Against plan",
                   value: `${((hovered.v / plannedRate - 1) * 100).toFixed(1)}%` }]
              : []),
          ]}
          footer={
            hovered.kind === "forecast"
              ? "Forecast, not a record. The band widens with the horizon."
              : undefined
          }
        />
      )}

      <p className="text-muted-foreground mt-2 border-t pt-2 font-mono text-[10px] leading-relaxed">
        {unit} per day. Faint line is each day, solid is the {windowDays} day mean,
        dashed is forecast, and the band is the {confidence}% interval
      </p>
    </div>
  );
}
