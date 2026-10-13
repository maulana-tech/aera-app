"use client";

import { scaleTime, timeWeek } from "d3";
import { useState, type MouseEvent } from "react";

import type { ArrivalChartData } from "@/app/lib";
import { ChartTooltip } from "@/components/chart-tooltip";
import { Legend, type LegendItem } from "@/components/chart-legend";
import { parseDay, shortDay } from "@/lib/chart";
import { useChartWidth } from "@/hooks/use-chart-width";

/* Booked arrival against the arrival the system now expects.
 *
 * A dumbbell, because each row is a pair of dates for one shipment and the
 * thing being argued about is the distance between them. Two bars would need
 * two scales to be legible; a connector makes the slip the length it actually
 * is, on the one date axis everything else on the page is measured in.
 *
 * The open circle is the date on the purchase order and the filled one is the
 * date the system expects now — filled against hollow, which reads at every
 * level of vision, where a second hue would not.
 *
 * Rows arrive sorted by slip, so the longest connector is at the top and the
 * eye ranks them without reading a number. The date axis is still real, so the
 * chart answers "when" as well as "how late", which is the question this page
 * exists for.
 */

const ROW = 23;
const DOT = 4.5;
const DAY = 86_400_000;

export function ArrivalChart({ data }: { data: ArrivalChartData }) {
  const [over, setOver] = useState<number | null>(null);
  const { ref, width } = useChartWidth();
  const { items, total, today } = data;
  if (items.length === 0) return null;

  const wide = width >= 640;
  const PAD = { top: 30, right: wide ? 58 : 46, bottom: 32, left: wide ? 168 : 108 };
  const H = PAD.top + items.length * ROW + PAD.bottom;

  const todayD = parseDay(today);
  const rows = items.map((i) => ({ ...i, booked: parseDay(i.booked), revised: parseDay(i.revised) }));
  // Padding either side, and today inside the domain even when every shipment
  // on the chart is still ahead of it — otherwise the rule that says where now
  // is would fall outside the box and never be drawn.
  const lo = new Date(
    Math.min(todayD.getTime(), ...rows.map((d) => d.booked.getTime())) - 3 * DAY,
  );
  const hi = new Date(
    Math.max(todayD.getTime(), ...rows.map((d) => d.revised.getTime())) + 3 * DAY,
  );
  const x = scaleTime().domain([lo, hi]).range([PAD.left, width - PAD.right]);
  const dateTicks = x
    .ticks(timeWeek.every(width < 560 ? 2 : 1)!)
    .filter((d) => d.getTime() >= lo.getTime() && d.getTime() <= hi.getTime());
  const hovered = over === null ? null : rows[over];

  const legend: LegendItem[] = [
    { label: "Booked on the PO", mark: "open" },
    { label: "Expected now", mark: "dot" },
    { label: "Slip", mark: "line" },
    { label: "Today", mark: "rule" },
  ];

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const py = ((e.clientY - r.top) / r.height) * H;
    const i = Math.floor((py - PAD.top) / ROW);
    setOver(i >= 0 && i < rows.length ? i : null);
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
          aria-label={`Booked against revised arrival for the ${rows.length} largest slips of ${total} lines`}
          onMouseMove={onMove}
          onMouseLeave={() => setOver(null)}
        >
          <line
            x1={x(todayD)} x2={x(todayD)} y1={PAD.top - 14} y2={H - PAD.bottom}
            stroke="var(--viz-rule)" strokeWidth="1.5" strokeDasharray="5 4"
          />
          <text
            x={x(todayD)} y={12} textAnchor="middle"
            className="fill-muted-foreground" fontSize="10" fontFamily="var(--font-mono)"
          >
            today
          </text>

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

          {rows.map((d, i) => {
            const cy = PAD.top + i * ROW + ROW / 2;
            const dim = over !== null && over !== i;
            return (
              <g key={d.reference} opacity={dim ? 0.5 : 1}>
                {over === i && (
                  <rect
                    x={0} y={PAD.top + i * ROW} width={width} height={ROW}
                    className="fill-muted" opacity="0.55"
                  />
                )}

                <text
                  x={PAD.left - 14} y={cy + 3.5} textAnchor="end"
                  fontSize="11" fontFamily="var(--font-mono)" className="fill-foreground"
                >
                  {d.reference}
                  {wide && (
                    <tspan
                      fontSize="10" className="fill-muted-foreground"
                      fontFamily="var(--font-mono)" dx="6"
                    >
                      {d.material}
                    </tspan>
                  )}
                </text>

                <line
                  x1={x(d.booked)} x2={x(d.revised)} y1={cy} y2={cy}
                  stroke="var(--viz-series)" strokeWidth="3"
                  strokeLinecap="round" opacity="0.5"
                />
                <circle
                  cx={x(d.booked)} cy={cy} r={DOT}
                  fill="var(--background)" stroke="var(--viz-series)" strokeWidth="2"
                />
                <circle cx={x(d.revised)} cy={cy} r={DOT} fill="var(--viz-series)" />

                <text
                  x={width - PAD.right + 10} y={cy + 3.5}
                  fontSize="11" fontFamily="var(--font-mono)" className="fill-foreground"
                >
                  {d.slip > 0 ? `+${d.slip}` : d.slip}
                </text>
              </g>
            );
          })}
        </svg>

        {hovered && over !== null && (
          <ChartTooltip
            x={(x(hovered.revised) / width) * 100}
            y={((PAD.top + over * ROW + ROW / 2) / H) * 100}
            title={hovered.reference}
            subtitle={hovered.material}
            rows={[
              { label: "Booked", value: shortDay(hovered.booked) },
              { label: "Expected now", value: shortDay(hovered.revised) },
              {
                label: "Slip",
                value: `${hovered.slip > 0 ? "+" : ""}${hovered.slip} days`,
              },
              { label: "Origin", value: hovered.port, quiet: true },
              { label: "Status", value: hovered.status.replace(/_/g, " "), quiet: true },
            ]}
            footer={
              hovered.slip > 0
                ? "The connector is the slip: the distance between what was booked and what is now expected."
                : undefined
            }
          />
        )}
      </div>

      <p className="text-muted-foreground mt-2 border-t pt-2 font-mono text-[10px] leading-relaxed">
        {rows.length} worst of {total} lines · arrival dates, days slip
      </p>
    </div>
  );
}
