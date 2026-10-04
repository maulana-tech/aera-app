"use client";

import { scaleLinear } from "d3";
import { useState, type MouseEvent } from "react";

import type { OffersChartData } from "@/app/lib";
import { ChartTooltip } from "@/components/chart-tooltip";
import { Legend, type LegendItem } from "@/components/chart-legend";
import { num } from "@/lib/chart";
import { useChartWidth } from "@/hooks/use-chart-width";

/* Which supplier to buy from, as one picture instead of two tables.
 *
 * Price and lead time are different units, and every way of putting them
 * together lies a little: one shared axis adds rupiah to days, two axes let a
 * bar and a line wear the same label and mean different things. So neither
 * appears directly. The vertical axis is how much dearer an offer is than the
 * cheapest one on file, which is a single percentage with a real zero at the
 * bottom; the horizontal axis is days, whose zero is the offer that ships
 * immediately. The bottom-left corner is then the answer — cheap and quick —
 * and every offer is read by how far it sits from it.
 *
 * The curve joins the offers nothing else beats on both axes at once. Anything
 * below and to the right of a point on it is a worse choice on paper, which is
 * the whole argument the comparison has to settle. Offers past their validity
 * date are drawn hollow: still evidence of what was quoted, not a price anyone
 * can take.
 *
 * Prices are read off the tick labels and the tooltip, never off the height of
 * a dot. Two offers a hair apart in price are drawn a hair apart, and if they
 * land on each other their labels are pushed apart instead — the dots stay
 * where the data puts them.
 */

type Item = OffersChartData["points"][number];

const PAD = { top: 34, right: 26, bottom: 56, left: 54 };
const PH = 300;

/** How far a label is nudged before it is allowed to sit on another one. */
const LIFT = [-7, -19, -31, 5, 17, 29];

export function OffersChart({ data }: { data: OffersChartData }) {
  const [over, setOver] = useState<number | null>(null);
  const { ref, width } = useChartWidth();
  const { material, unit, qty, live, total, points } = data;
  if (points.length === 0) return null;

  const H = PAD.top + PH + PAD.bottom;
  const floorY = PAD.top + PH;

  // Measured against the cheapest offer on file, whatever its validity: the
  // dearest point of the scale is a real number, not a fitted one.
  const floor = Math.min(...points.map((d) => d.price));
  const pct = (d: Item) => (floor > 0 ? (100 * (d.price - floor)) / floor : 0);

  const x = scaleLinear()
    .domain([0, Math.max(...points.map((d) => d.lead)) * 1.12 || 1])
    .range([PAD.left, width - PAD.right])
    .nice();
  const y = scaleLinear()
    .domain([0, Math.max(...points.map(pct)) * 1.18 || 1])
    .range([floorY, PAD.top])
    .nice();

  const cx = (d: Item) => x(d.lead);
  const cy = (d: Item) => y(pct(d));

  // The trade-off curve: cheapest-first among what is still valid, which is the
  // same set as cheapest-first among what nothing dominates.
  const onLine = points
    .filter((d) => d.on_line)
    .sort((a, b) => a.lead - b.lead);
  const curve = onLine
    .map((d, i) => `${i ? "L" : "M"}${cx(d)},${cy(d)}`)
    .join(" ");

  const hovered = over === null ? null : points[over];

  const legend: LegendItem[] = [
    { label: "Offer", mark: "dot" },
    { label: "Past validity", mark: "open" },
    { label: "Trade-off line", mark: "line" },
  ];

  // Labels are annotation, not data: they may be lifted off their dot so two
  // offers a tenth of a percent apart do not overwrite each other.
  const labels: { d: Item; lx: number; ly: number; anchor: "start" | "end" }[] = [];
  for (const d of [...points].sort((a, b) => cy(a) - cy(b))) {
    const anchor = cx(d) > width - PAD.right - 54 ? "end" : "start";
    const lx = anchor === "start" ? cx(d) + 9 : cx(d) - 9;
    const taken = (ly: number) =>
      labels.some((l) => Math.abs(l.lx - lx) < 56 && Math.abs(l.ly - ly) < 11);
    let ly = cy(d) + LIFT[0];
    for (const lift of LIFT.slice(1)) {
      const tryY = cy(d) + lift;
      if (tryY < PAD.top + 6 || tryY > floorY - 3) continue;
      ly = tryY;
      if (!taken(tryY)) break;
    }
    labels.push({ d, lx, ly, anchor });
  }

  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * width;
    const py = ((e.clientY - r.top) / r.height) * H;
    let best = -1;
    let nearest = 20;                      // a dot outside this radius is not hovered
    points.forEach((d, i) => {
      const gap = Math.hypot(cx(d) - px, cy(d) - py);
      if (gap < nearest) {
        nearest = gap;
        best = i;
      }
    });
    setOver(best >= 0 ? best : null);
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
          aria-label={`${points.length} offers on ${material}: price against lead time. `
            + `${live} still valid. Horizontal, days to deliver; vertical, how much `
            + `dearer than the cheapest offer on file.`}
          onMouseMove={onMove}
          onMouseLeave={() => setOver(null)}
        >
          <text
            x={PAD.left} y={PAD.top - 16}
            fontSize="10" fontFamily="var(--font-mono)"
            className="fill-muted-foreground"
          >
            % above the cheapest offer
          </text>

          {y.ticks(5).filter((t) => t !== 0).map((t) => (
            <line
              key={`g${t}`}
              x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)}
              stroke="var(--viz-rule)" strokeWidth="1" opacity="0.2"
            />
          ))}

          {/* Zero on both axes is a real offer: the cheapest, and the one that
              ships immediately. The corner they meet at is the goal. */}
          <line
            x1={PAD.left} x2={width - PAD.right} y1={floorY} y2={floorY}
            stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
          />
          <line
            x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={floorY}
            stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
          />

          <path
            d={curve} fill="none"
            stroke="var(--viz-series)" strokeWidth="1.5"
            strokeDasharray="4 4" strokeLinejoin="round" opacity="0.75"
          />

          {points.map((d) => (
            <circle
              key={d.supplier}
              cx={cx(d)} cy={cy(d)} r={5.5}
              fill={d.live ? "var(--viz-series)" : "none"}
              stroke={d.live ? "var(--background)" : "var(--viz-series)"}
              strokeWidth={d.live ? 1.5 : 2}
              opacity={over === null || hovered === d ? 1 : 0.4}
            />
          ))}

          {labels.map(({ d, lx, ly, anchor }) => (
            <text
              key={`l-${d.supplier}`}
              x={lx} y={ly + 3} textAnchor={anchor}
              fontSize="9.5" fontFamily="var(--font-mono)"
              className="fill-muted-foreground"
            >
              {d.supplier}
            </text>
          ))}

          {y.ticks(5).filter((t) => t !== 0).map((t) => (
            <text
              key={`y${t}`}
              x={PAD.left - 8} y={y(t) + 3.5} textAnchor="end"
              fontSize="10" fontFamily="var(--font-mono)"
              className="fill-muted-foreground"
            >
              {num(t)}%
            </text>
          ))}

          {x.ticks(Math.max(2, Math.floor(width / 70))).map((t) => (
            <g key={`x${t}`}>
              <line
                x1={x(t)} x2={x(t)} y1={floorY} y2={floorY + 4}
                stroke="var(--viz-rule)" strokeWidth="1" opacity="0.5"
              />
              <text
                x={x(t)} y={floorY + 17} textAnchor="middle"
                fontSize="10" fontFamily="var(--font-mono)"
                className="fill-muted-foreground"
              >
                {num(t)}
              </text>
            </g>
          ))}

          <text
            x={width - PAD.right} y={floorY + 34} textAnchor="end"
            fontSize="10" fontFamily="var(--font-mono)"
            className="fill-muted-foreground"
          >
            days to deliver
          </text>
        </svg>

        {hovered && over !== null && (
          <ChartTooltip
            x={(cx(hovered) / width) * 100}
            y={(cy(hovered) / H) * 100}
            title={hovered.name}
            subtitle={`${hovered.supplier} · ${hovered.country}`}
            rows={[
              {
                label: `Rp per ${unit}`,
                value: "Rp " + hovered.price.toLocaleString("en-US"),
              },
              { label: "Lead time", value: `${hovered.lead} days` },
              {
                label: `Total for ${num(qty)} ${unit}`,
                value: "Rp " + Math.round(hovered.price * qty).toLocaleString("en-US"),
                quiet: true,
              },
              {
                label: "Against the cheapest",
                value: `${pct(hovered) >= 0 ? "+" : ""}${num(pct(hovered))}%`,
                quiet: true,
              },
              {
                label: "TKDN certificate",
                value: hovered.tkdn == null ? "none on record" : `${num(hovered.tkdn)}%`,
                quiet: true,
              },
              {
                label: "Validity",
                value: hovered.live ? "still valid" : "past its last valid day",
                quiet: true,
              },
            ]}
          />
        )}
      </div>

      <p className="text-muted-foreground mt-2 border-t pt-2 font-mono text-[10px] leading-relaxed">
        {points.length} offers on {material} for {num(qty)} {unit} · {live} still valid ·{" "}
        {onLine.length} on the trade-off line
        {live < total ? ` · ${total - live} drawn hollow` : ""}
      </p>
    </div>
  );
}
