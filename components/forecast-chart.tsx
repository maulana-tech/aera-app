"use client";

import {
  area,
  bisector,
  curveMonotoneX,
  line,
  scaleLinear,
  scaleTime,
  timeWeek,
} from "d3";
import { useState, type MouseEvent } from "react";

import { ChartTooltip } from "@/components/chart-tooltip";
import { Legend, type LegendItem } from "@/components/chart-legend";
import { num, parseDay, shortDay } from "@/lib/chart";
import { useChartWidth } from "@/hooks/use-chart-width";

export type ForecastPoint = { on: string; point: number; lower: number; upper: number };
export type Observed = { on: string; qty: number; mean: number };

/* A forecast is a range, so the chart has to draw one.
 *
 * d3 does the geometry — the time scale, the linear scale, the line and area
 * generators, and the bisector that finds the point under the cursor. React
 * renders the SVG. There is no `d3.select` anywhere here: the moment d3 owns
 * the DOM, React stops being able to reconcile against it, and the two fight
 * over the same nodes.
 *
 * The x axis is a real time scale rather than a point index, so a skipped day
 * shows as a gap the width of a day instead of being silently closed up, and
 * the ticks come from d3's calendar rather than a hand-picked modulo.
 *
 * One hue throughout. Observed and forecast are told apart by shape, never by
 * a second colour, because identity carried by colour alone fails for a
 * colour-blind reader: bars for the days that happened, a solid line through
 * them, a dashed line for what has not. The band is the same hue at low
 * opacity, so it reads as the same quantity rather than a second series.
 *
 * No series is labelled inside the plot. A label that sits on the data at one
 * card width and on top of it at another is worse than no label, so every
 * series is named in the legend above instead. The only thing left inside is
 * "today", which marks a moment rather than a quantity.
 *
 * The planned rate is a dashed rule in the border token, not a series colour.
 * It is a threshold, not data, and the whole point of the chart is that the
 * forecast sits above it.
 */

const PAD = { top: 30, right: 18, bottom: 32, left: 52 };
const DAY = 86_400_000;

type Pt = {
  t: Date;
  kind: "observed" | "forecast";
  /** the trailing mean — the line the eye follows */
  v: number;
  /** that day's actual withdrawal; a forecast has no separate figure */
  raw: number;
  lower?: number;
  upper?: number;
};

type Fc = { t: Date; point: number; lower: number; upper: number };

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
  // Both are needed: the index picks the row, `cursor` places the tooltip.
  // Anchoring the tooltip to the line instead made pointing anywhere in the
  // band look dead, because the card appeared far above where the pointer was.
  const [at, setAt] = useState<number | null>(null);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const { ref, width } = useChartWidth();

  const obs = observed.map((o) => ({ ...o, t: parseDay(o.on) }));
  const fc = points.map((p) => ({ ...p, t: parseDay(p.on) }));

  const all: Pt[] = [
    ...obs.map((o) => ({
      t: o.t, kind: "observed" as const, v: o.mean, raw: o.qty,
    })),
    ...fc.map((p) => ({
      t: p.t, kind: "forecast" as const, v: p.point, raw: p.point,
      lower: p.lower, upper: p.upper,
    })),
  ];
  if (all.length === 0) return null;

  // Tall enough to read the band, capped so the card never pushes the table
  // below it off the screen on a wide monitor.
  const H = Math.round(Math.min(440, Math.max(280, width * 0.3)));
  const t0 = all[0].t;
  const t1 = all[all.length - 1].t;
  const plotH = H - PAD.top - PAD.bottom;

  // The leading `0` keeps the max honest when one series is empty: Math.max of
  // an empty list is -Infinity, and a domain built on that draws nothing
  // without complaining about it.
  const peak = Math.max(
    0,
    ...points.map((p) => p.upper),
    ...observed.map((o) => o.qty),
    plannedRate ?? 0,
  );

  const x = scaleTime().domain([t0, t1]).range([PAD.left, width - PAD.right]);
  // `.nice()` rounds the top up to a round number so the top gridline is a
  // value someone would actually say, and the band never pokes past it.
  const y = scaleLinear().domain([0, peak]).nice(5).range([H - PAD.top, PAD.top]);

  // Today anchors both the band and the forecast line. Uncertainty is zero
  // where the record stops and only grows after it, so the band is drawn
  // tapering from a point rather than opening at full width on day one.
  const last = obs[obs.length - 1];
  const fcSeries: Fc[] = [
    ...(last
      ? [{ t: last.t, point: last.mean, lower: last.mean, upper: last.mean }]
      : []),
    ...fc.map((p) => ({ t: p.t, point: p.point, lower: p.lower, upper: p.upper })),
  ];

  const obsPath =
    line<(typeof obs)[number]>()
      .x((d) => x(d.t))
      .y((d) => y(d.mean))(obs) ?? "";
  const fcPath =
    line<Fc>()
      .curve(curveMonotoneX)
      .x((d) => x(d.t))
      .y((d) => y(d.point))(fcSeries) ?? "";
  const bandPath =
    area<Fc>()
      .curve(curveMonotoneX)
      .x((d) => x(d.t))
      .y0((d) => y(d.lower))
      .y1((d) => y(d.upper))(fcSeries) ?? "";

  // Withdrawals are a quantity per day, so they read as bars rather than a
  // second line: a line through the same points would have to be told apart
  // from the mean by weight alone, and the two would cross constantly.
  const dayPx = (x(new Date(t0.getTime() + DAY)) - x(t0)) || 4;
  const barW = Math.max(2, Math.min(dayPx * 0.62, 22));

  const yTicks = y.ticks(5);
  // A tick a week, so the eye can count horizon rather than guess it. Narrow
  // cards get every other week, because eight labels in 300px overlap.
  const dateTicks = x
    .ticks(timeWeek.every(width < 520 ? 2 : 1)!)
    .filter((d) => d.getTime() >= t0.getTime() && d.getTime() <= t1.getTime());

  const findAt = (px: number) => {
    // Pixel → instant → the row nearest it. The bisector walks the sorted
    // series once, and the two candidates around the insertion point are the
    // only ones that can be closest.
    const probe = x.invert(px);
    const i = bisector<Pt, Date>((d) => d.t).left(all, probe);
    if (i <= 0) return 0;
    if (i >= all.length) return all.length - 1;
    return Math.abs(all[i].t.getTime() - probe.getTime()) <
      Math.abs(all[i - 1].t.getTime() - probe.getTime())
      ? i
      : i - 1;
  };

  const hovered = at === null ? null : all[at];
  const hoveredObs = at !== null && at < obs.length ? obs[at] : null;
  const hoveredBand =
    hovered && hovered.lower !== undefined && hovered.upper !== undefined
      ? { lower: hovered.lower, upper: hovered.upper }
      : null;

  const legend: LegendItem[] = [
    { label: "Daily withdrawn", mark: "bar" },
    { label: `${windowDays}-day mean`, mark: "line" },
    { label: "Forecast", mark: "dash" },
    { label: `${confidence}% range`, mark: "area" },
    ...(plannedRate !== null
      ? [{ label: `Planned ${plannedRate} ${unit}/day`, mark: "rule" as const }]
      : []),
  ];

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const cx = Math.max(
      PAD.left,
      Math.min(width - PAD.right, ((e.clientX - r.left) / r.width) * width),
    );
    const cy = Math.max(
      PAD.top,
      Math.min(H - PAD.bottom, ((e.clientY - r.top) / r.height) * H),
    );
    setAt(findAt(cx));
    setCursor({ x: cx, y: cy });
  };

  return (
    <div ref={ref} className="viz">
      <Legend items={legend} className="mb-2.5" />

      {/* The tooltip is positioned against the plot box alone. If it hung off
       * the outer div the percentages would be off by the legend and caption. */}
      <div className="relative">
        <svg
          width={width}
          height={H}
          viewBox={`0 0 ${width} ${H}`}
          className="block"
          role="img"
          aria-label={`${obs.length} days observed and ${fc.length} forecast, ${unit} per day`}
          onMouseMove={onMove}
          onMouseLeave={() => {
            setAt(null);
            setCursor(null);
          }}
        >
          {/* The days after the record stops are shaded, so the split between
           * what happened and what is estimated survives being printed. */}
          {last && (
            <rect
              x={x(last.t)}
              y={PAD.top}
              width={Math.max(0, width - PAD.right - x(last.t))}
              height={plotH}
              fill="var(--viz-series)"
              opacity="0.05"
            />
          )}

          {yTicks.map((t) => (
            <g key={t}>
              <line
                x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)}
                stroke="var(--viz-rule)" strokeWidth="1"
                opacity={t === 0 ? 0.5 : 0.2}
              />
              <text
                x={PAD.left - 9} y={y(t) + 3.5} textAnchor="end"
                className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
              >
                {num(t)}
              </text>
            </g>
          ))}

          <line
            x1={PAD.left} x2={width - PAD.right}
            y1={H - PAD.bottom} y2={H - PAD.bottom}
            stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
          />
          {dateTicks.map((d) => (
            <g key={d.toISOString()}>
              <line
                x1={x(d)} x2={x(d)} y1={H - PAD.bottom} y2={H - PAD.bottom + 4}
                stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
              />
              <text
                x={x(d)} y={H - PAD.bottom + 17} textAnchor="middle"
                className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
              >
                {shortDay(d)}
              </text>
            </g>
          ))}

          {obs.map((d) => (
            <rect
              key={d.on}
              x={x(d.t) - barW / 2}
              y={y(d.qty)}
              width={barW}
              height={Math.max(0, y(0) - y(d.qty))}
              fill="var(--viz-series)"
              opacity={at === null ? 0.3 : hoveredObs === d ? 0.6 : 0.16}
            />
          ))}

          <path d={bandPath} fill="var(--viz-series)" opacity="0.16" />

          {plannedRate !== null && (
            <line
              x1={PAD.left} x2={width - PAD.right}
              y1={y(plannedRate)} y2={y(plannedRate)}
              stroke="var(--viz-rule)" strokeWidth="1.5" strokeDasharray="5 4"
            />
          )}

          <path d={obsPath} fill="none" stroke="var(--viz-series)" strokeWidth="2" />
          <path
            d={fcPath} fill="none" stroke="var(--viz-series)" strokeWidth="2"
            strokeDasharray="6 4"
          />

          {/* Where the record stops and the estimate starts. The label lives in
           * the top margin so it never lands on the line it is naming. */}
          {last && (
            <>
              <line
                x1={x(last.t)} x2={x(last.t)} y1={PAD.top - 14} y2={H - PAD.bottom}
                stroke="var(--viz-rule)" strokeWidth="1" opacity="0.7"
              />
              <text
                x={x(last.t)} y={12} textAnchor="middle"
                className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
              >
                today
              </text>
            </>
          )}

          <text
            x={PAD.left - 9} y={12} textAnchor="end"
            className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
          >
            {unit}
          </text>

          {hovered && cursor && (
            <>
              <line
                x1={x(hovered.t)} x2={x(hovered.t)}
                y1={PAD.top} y2={H - PAD.bottom}
                stroke="var(--viz-series)" strokeWidth="1" opacity="0.45"
              />
              <circle cx={x(hovered.t)} cy={y(hovered.v)} r="4" fill="var(--viz-series)" />
            </>
          )}
        </svg>

        {hovered && cursor && (
          <ChartTooltip
            x={(cursor.x / width) * 100}
            y={(cursor.y / H) * 100}
            title={shortDay(hovered.t)}
            subtitle={hovered.kind === "observed" ? "withdrawn" : "forecast"}
            rows={[
              {
                label: hovered.kind === "observed" ? `${windowDays}d mean` : "Expected",
                value: `${hovered.v} ${unit}`,
              },
              ...(hovered.kind === "observed"
                ? [{ label: "That day", value: `${hovered.raw} ${unit}`, quiet: true }]
                : []),
              ...(hoveredBand
                ? [{
                    label: `${confidence}% range`,
                    value: `${hoveredBand.lower} to ${hoveredBand.upper}`,
                    quiet: true,
                  }]
                : []),
              ...(plannedRate !== null
                ? [{
                    label: "Against plan",
                    value: `${((hovered.v / plannedRate - 1) * 100).toFixed(1)}%`,
                  }]
                : []),
            ]}
            footer={
              hovered.kind === "forecast"
                ? "Forecast, not a record. The band widens with the horizon."
                : undefined
            }
          />
        )}
      </div>

      <p className="text-muted-foreground mt-2 border-t pt-2 font-mono text-[10px] leading-relaxed">
        {unit}/day · {obs.length} days observed, {fc.length} forecast
      </p>
    </div>
  );
}
