"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

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
const PAD = { top: 12, right: 14, bottom: 26, left: 44 };

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
  const [at, setAt] = useState<number | null>(null);

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

  const ticks = [0, 0.5, 1].map((f) => +(top * f).toFixed(1));
  const hovered = at === null ? null : all[at];
  const hoveredBand = at !== null && at >= offset ? points[at - offset] : null;

  return (
    <div className="viz">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Daily consumption, ${observed.length} days observed and ${points.length} forecast`}
        onMouseLeave={() => setAt(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const i = Math.round(((px - PAD.left) / plotW) * (all.length - 1));
          setAt(Math.max(0, Math.min(all.length - 1, i)));
        }}
      >
        {/* Grid stays recessive: it orients, it does not compete. */}
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)}
              stroke="var(--viz-rule)" strokeWidth="1" opacity="0.35"
            />
            <text
              x={PAD.left - 8} y={y(t) + 3} textAnchor="end"
              className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
            >
              {t}
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
          x={PAD.left} y={H - 8} className="fill-muted-foreground"
          fontSize="10" fontFamily="var(--font-mono)"
        >
          {short(all[0].on)}
        </text>
        <text
          x={x(offset - 1)} y={H - 8} textAnchor="middle"
          className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
        >
          today
        </text>
        <text
          x={W - PAD.right} y={H - 8} textAnchor="end"
          className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
        >
          {short(all[all.length - 1].on)}
        </text>
      </svg>

      {/* Reserved line, so pointing at the chart moves nothing. */}
      <div className="mt-2 min-h-[1.75rem] border-t pt-2">
        {hovered ? (
          <p className="text-xs leading-relaxed">
            <span className="font-mono">{short(hovered.on)}</span>
            <span className="text-muted-foreground">
              {hovered.kind === "observed" ? " withdrawn " : " forecast "}
            </span>
            <span className="font-mono font-medium">
              {hovered.v} {unit}
            </span>
            {hovered.kind === "observed" && (
              <span className="text-muted-foreground">
                {" "}({windowDays} day mean, that day {hovered.raw})
              </span>
            )}
            {hoveredBand && (
              <span className="text-muted-foreground">
                {" "}between {hoveredBand.lower} and {hoveredBand.upper} at {confidence}%
              </span>
            )}
          </p>
        ) : (
          <p className="text-muted-foreground font-mono text-[10px]">
            faint line is each day, solid is the {windowDays} day mean, dashed is
            forecast, the band is the {confidence}% interval
          </p>
        )}
      </div>
    </div>
  );
}
