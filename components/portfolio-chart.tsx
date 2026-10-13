"use client";

import { line, scaleBand, scaleLinear } from "d3";
import { useState, type MouseEvent } from "react";

import type { PortfolioChartData } from "@/app/lib";
import { ChartTooltip } from "@/components/chart-tooltip";
import { Legend, type LegendItem } from "@/components/chart-legend";
import { num } from "@/lib/chart";
import { useChartWidth } from "@/hooks/use-chart-width";

/* Who carries the book, and how few suppliers it takes to make most of it.
 *
 * A Pareto, because concentration is a relationship rather than a ranking. One
 * supplier's own share says how big it is; the running total says how much the
 * company is exposed to if the top of the list moves together. Neither number
 * answers that alone, and a table of eighteen rows asks the reader to add them
 * up by hand.
 *
 * Both series are percentages of the same book, so they share one axis. The
 * conventional Pareto gives the bars a scale and the line a second one, which
 * puts two quantities both called "%" at two different heights: anyone who
 * compares a bar with the line above it is then reading something untrue. Here
 * a bar and the curve point over it are one number read twice. The cost is
 * that the bars sit low, and the empty upper left is not a defect to be
 * filled in — most of these suppliers are small, which is the finding.
 *
 * One hue throughout. Bars and curve are told apart by shape, never by a
 * second colour, and no series is labelled inside the plot: the legend above
 * names them, so no label lands on the data at one card width and beside it at
 * another.
 */

type Item = PortfolioChartData["items"][number];

const PAD = { top: 30, right: 18, bottom: 58, left: 38 };
const PH = 300;

export function PortfolioChart({ data }: { data: PortfolioChartData }) {
  const [over, setOver] = useState<number | null>(null);
  const { ref, width } = useChartWidth();
  const { items, rule_pct, active, cover_n, total } = data;
  if (items.length === 0) return null;

  const H = PAD.top + PH + PAD.bottom;
  const floorY = PAD.top + PH;

  const x = scaleBand<string>()
    .domain(items.map((d) => d.supplier))
    .range([PAD.left, width - PAD.right])
    .padding(0.3);
  const y = scaleLinear().domain([0, 100]).range([floorY, PAD.top]);
  const yTicks = y.ticks(5);
  const step = x.step();
  const half = (step - x.bandwidth()) / 2;

  const centre = (d: Item) => (x(d.supplier) ?? 0) + x.bandwidth() / 2;
  const path = line<Item>()
    .x((d) => centre(d))
    .y((d) => y(d.cumulative))(items) ?? "";

  const hovered = over === null ? null : items[over];

  const legend: LegendItem[] = [
    { label: "Share of the book", mark: "bar" },
    { label: "Cumulative share", mark: "line" },
    { label: `${num(rule_pct)}% of the book`, mark: "rule" },
  ];

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * width;
    // Nearest supplier rather than the bar under the cursor, so the tooltip
    // does not vanish in the padding between two bars.
    let best = 0;
    let nearest = Infinity;
    items.forEach((d, i) => {
      const gap = Math.abs(px - centre(d));
      if (gap < nearest) {
        nearest = gap;
        best = i;
      }
    });
    setOver(nearest <= step / 2 ? best : null);
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
          aria-label={`Purchase-order volume by supplier. ${items.length} of ${active} `
            + `suppliers holding orders are drawn; ${cover_n} of them carry `
            + `${rule_pct} percent of the book.`}
          onMouseMove={onMove}
          onMouseLeave={() => setOver(null)}
        >
          {/* The unit sits in the corner rather than beside each tick, the way
              the demand chart keeps its tonnes out of the way of the numbers. */}
          <text
            x={PAD.left} y={PAD.top - 14}
            fontSize="10" fontFamily="var(--font-mono)"
            className="fill-muted-foreground"
          >
            % of book
          </text>

          {yTicks
            .filter((t) => t !== 0 && t !== rule_pct)
            .map((t) => (
              <line
                key={`g${t}`}
                x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)}
                stroke="var(--viz-rule)" strokeWidth="1" opacity="0.2"
              />
            ))}

          {over !== null && (
            <rect
              x={(x(items[over].supplier) ?? 0) - half}
              y={PAD.top} width={step} height={PH}
              className="fill-muted" opacity="0.55"
            />
          )}

          {items.map((d) => {
            const top = y(d.share);
            return (
              <rect
                key={d.supplier}
                x={x(d.supplier) ?? 0}
                y={top}
                width={x.bandwidth()}
                height={Math.max(2, floorY - top)}
                rx={2}
                fill="var(--viz-series)"
                opacity={over === null || hovered === d ? 1 : 0.45}
              />
            );
          })}

          <line
            x1={PAD.left} x2={width - PAD.right} y1={floorY} y2={floorY}
            stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
          />

          {/* The threshold takes the place of the gridline it would otherwise
              be drawn on top of, so one line sits at that value rather than a
              dashed rule laid over a solid one. */}
          <line
            x1={PAD.left} x2={width - PAD.right}
            y1={y(rule_pct)} y2={y(rule_pct)}
            stroke="var(--viz-rule)" strokeWidth="1.5" strokeDasharray="5 4"
          />

          <path
            d={path} fill="none"
            stroke="var(--viz-series)" strokeWidth="2" strokeLinejoin="round"
          />

          {yTicks.map((t) => (
            <text
              key={`y${t}`}
              x={PAD.left - 8} y={y(t) + 3.5} textAnchor="end"
              fontSize="10" fontFamily="var(--font-mono)"
              className="fill-muted-foreground"
            >
              {num(t)}
            </text>
          ))}

          {items.map((d) => (
            <g key={`x-${d.supplier}`}>
              <line
                x1={centre(d)} x2={centre(d)} y1={floorY} y2={floorY + 4}
                stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
              />
              {/* Eight characters do not fit under a band at any width we can
                  measure, so they lean. The anchor is the tick: the text runs
                  down and to the left of it, staying below the axis. */}
              <text
                x={centre(d)} y={floorY + 15} textAnchor="end"
                fontSize="9.5" fontFamily="var(--font-mono)"
                className="fill-muted-foreground"
                transform={`rotate(-45 ${centre(d)} ${floorY + 15})`}
              >
                {d.supplier}
              </text>
            </g>
          ))}
        </svg>

        {hovered && over !== null && (
          <ChartTooltip
            x={(centre(hovered) / width) * 100}
            y={(y(hovered.cumulative) / H) * 100}
            title={hovered.name}
            subtitle={`${hovered.supplier} · ${hovered.country}`}
            rows={[
              { label: "Share of the book", value: `${num(hovered.share)}%` },
              { label: "Cumulative", value: `${num(hovered.cumulative)}%` },
              {
                label: "Volume",
                value:
                  `${(hovered.volume ?? 0).toLocaleString("en-US", {
                    maximumFractionDigits: 1,
                  })} ${hovered.unit ?? ""}`.trim(),
                quiet: true,
              },
              {
                label: "Purchase orders",
                value: `${hovered.orders} · ${hovered.late} late`,
                quiet: true,
              },
              {
                label: "Average slip",
                value: hovered.slip == null ? "—" : `${num(hovered.slip)} days`,
                quiet: true,
              },
              {
                label: "TKDN certificate",
                value: hovered.tkdn == null ? "none on record" : `${num(hovered.tkdn)}%`,
                quiet: true,
              },
            ]}
          />
        )}
      </div>

      <p className="text-muted-foreground mt-2 border-t pt-2 font-mono text-[10px] leading-relaxed">
        {items.length} of {active} suppliers holding orders · {cover_n} carry{" "}
        {num(rule_pct)}% of the book · {total} on the approved list
      </p>
    </div>
  );
}
