"use client";

import { scaleLinear } from "d3";
import { useState, type MouseEvent } from "react";

import type { CoverChartData } from "@/app/lib";
import { ChartTooltip } from "@/components/chart-tooltip";
import { Legend, type LegendItem } from "@/components/chart-legend";
import { num } from "@/lib/chart";
import { useChartWidth } from "@/hooks/use-chart-width";

/* How long the stock lasts, against the floor it is supposed to clear.
 *
 * A bar chart, because days of cover is one number per line and the question is
 * rank: which material runs out first, and how far from the floor it sits. The
 * rows arrive sorted by cover ascending, so the chart reads top-down in the
 * same order as the table and the two can be checked against each other.
 *
 * Only the tightest lines are drawn — the rest of the 53 are a long tail that
 * would compress the bars that matter — and the caption says how many were
 * left out, because a chart that quietly drops rows is worse than no chart.
 *
 * Under-floor bars carry hatching, not a warning colour: they are already on
 * the left of the threshold line, and adding red would tell a colour-blind
 * reader nothing the position does not.
 */

const ROW = 23;
const BAR = 13;

export function CoverChart({ data }: { data: CoverChartData }) {
  const [over, setOver] = useState<number | null>(null);
  const { ref, width } = useChartWidth();
  const { items, threshold, threshold_label, total } = data;
  if (items.length === 0) return null;

  // The plant only earns its place when there is room for it; below that the
  // bar would start so far right there is nothing left to measure.
  const wide = width >= 560;
  const PAD = { top: 14, right: wide ? 58 : 44, bottom: 32, left: wide ? 158 : 104 };
  const H = PAD.top + items.length * ROW + PAD.bottom;

  const max = Math.max(threshold, ...items.map((d) => d.days)) * 1.06 || 1;
  const x = scaleLinear().domain([0, max]).range([PAD.left, width - PAD.right]);
  const xTicks = x.ticks(5);
  const hovered = over === null ? null : items[over];

  const legend: LegendItem[] = [
    { label: "Days of cover", mark: "bar" },
    { label: `Under ${num(threshold)} days`, mark: "hatch" },
    { label: threshold_label, mark: "rule" },
  ];

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const py = ((e.clientY - r.top) / r.height) * H;
    const i = Math.floor((py - PAD.top) / ROW);
    setOver(i >= 0 && i < items.length ? i : null);
  };

  return (
    <div ref={ref} className="viz">
      <Legend items={legend} className="mb-2.5" />

      <div className="relative">
        <svg
          width={width}
          height={H}
          viewBox={`0 0 ${width} ${H}`}
          className="block"
          role="img"
          aria-label={`Days of cover for the ${items.length} tightest of ${total} lines`}
          onMouseMove={onMove}
          onMouseLeave={() => setOver(null)}
        >
          <defs>
            <pattern
              id="cover-hatch"
              width="5" height="5"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="2.5" height="5" fill="var(--viz-series)" />
            </pattern>
          </defs>

          {items.map((d, i) => {
            const cy = PAD.top + i * ROW + ROW / 2;
            const under = d.days < threshold;
            return (
              <g key={`${d.material}-${d.plant}`}>
                {over === i && (
                  <rect
                    x={0} y={PAD.top + i * ROW} width={width} height={ROW}
                    className="fill-muted" opacity="0.55"
                  />
                )}

                <text
                  x={PAD.left - 12} y={cy + 3.5} textAnchor="end"
                  fontSize="11" className="fill-foreground"
                >
                  {d.material}
                  {wide && (
                    <tspan
                      fontSize="10" fontFamily="var(--font-mono)"
                      className="fill-muted-foreground" dx="6"
                    >
                      {d.plant}
                    </tspan>
                  )}
                </text>

                <rect
                  x={PAD.left}
                  y={cy - BAR / 2}
                  width={Math.max(1, x(d.days) - PAD.left)}
                  height={BAR}
                  rx={BAR / 2}
                  fill={under ? "url(#cover-hatch)" : "var(--viz-series)"}
                  stroke={under ? "var(--viz-series)" : "none"}
                  strokeWidth={under ? 1 : 0}
                  opacity={over === null || over === i ? 1 : 0.45}
                />

                <text
                  x={width - PAD.right + 10} y={cy + 3.5}
                  fontSize="11" fontFamily="var(--font-mono)"
                  className="fill-foreground"
                >
                  {num(d.days)}
                </text>
              </g>
            );
          })}

          <line
            x1={x(threshold)} x2={x(threshold)}
            y1={PAD.top - 6} y2={H - PAD.bottom}
            stroke="var(--viz-rule)" strokeWidth="1.5" strokeDasharray="5 4"
          />

          <line
            x1={PAD.left} x2={width - PAD.right}
            y1={H - PAD.bottom} y2={H - PAD.bottom}
            stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
          />
          {xTicks.map((t) => (
            <g key={t}>
              <line
                x1={x(t)} x2={x(t)} y1={H - PAD.bottom} y2={H - PAD.bottom + 4}
                stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
              />
              <text
                x={x(t)} y={H - PAD.bottom + 17} textAnchor="middle"
                className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
              >
                {num(t)}
              </text>
            </g>
          ))}
        </svg>

        {hovered && over !== null && (
          <ChartTooltip
            x={(x(hovered.days) / width) * 100}
            y={((PAD.top + over * ROW + ROW / 2) / H) * 100}
            title={`${hovered.material} at ${hovered.plant}`}
            subtitle={hovered.description}
            rows={[
              { label: "Days of cover", value: `${num(hovered.days)} days` },
              { label: "On hand", value: `${hovered.qty} ${hovered.unit}` },
              { label: "Used", value: `${num(hovered.daily)} ${hovered.unit}/day`, quiet: true },
              { label: "Empty on", value: hovered.depleted_on ?? "—", quiet: true },
              { label: "Floor", value: `${num(threshold)} days`, quiet: true },
            ]}
          />
        )}
      </div>

      <p className="text-muted-foreground mt-2 border-t pt-2 font-mono text-[10px] leading-relaxed">
        {items.length} tightest of {total} lines · sorted by how soon each runs out
      </p>
    </div>
  );
}
