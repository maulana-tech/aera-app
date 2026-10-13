import { cn } from "@/lib/utils";

/* A legend reads faster than a sentence, and it keeps the SVG itself free of
 * floating labels that land on top of the data at some widths and not others.
 *
 * Each mark is drawn the way the chart draws it, so the reader matches a shape
 * rather than a colour. That matters here: every series is one hue on purpose,
 * and a legend that told them apart by hue would fail the reader this design
 * was written for.
 */

export type Mark = "line" | "dash" | "rule" | "area" | "bar" | "hatch" | "dot" | "open";

export type LegendItem = { label: string; mark: Mark };

export function Legend({
  items, className,
}: {
  items: LegendItem[];
  className?: string;
}) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", className)}>
      {items.map((it) => (
        <li
          key={it.label}
          className="text-muted-foreground flex items-center gap-1.5 text-[11px] leading-none"
        >
          <Swatch mark={it.mark} />
          <span>{it.label}</span>
        </li>
      ))}
    </ul>
  );
}

function Swatch({ mark }: { mark: Mark }) {
  const series = "var(--viz-series)";
  const rule = "var(--viz-rule)";

  switch (mark) {
    case "line":
      return (
        <svg width="16" height="8" aria-hidden>
          <line x1="0" y1="4" x2="16" y2="4" stroke={series} strokeWidth="2" />
        </svg>
      );
    case "dash":
      return (
        <svg width="16" height="8" aria-hidden>
          <line
            x1="0" y1="4" x2="16" y2="4"
            stroke={series} strokeWidth="2" strokeDasharray="5 3"
          />
        </svg>
      );
    case "rule":
      return (
        <svg width="16" height="8" aria-hidden>
          <line
            x1="0" y1="4" x2="16" y2="4"
            stroke={rule} strokeWidth="1.5" strokeDasharray="4 3"
          />
        </svg>
      );
    case "area":
      return (
        <svg width="16" height="8" aria-hidden>
          <rect width="16" height="8" rx="1" fill={series} opacity="0.16" />
        </svg>
      );
    case "bar":
      return (
        <svg width="16" height="8" aria-hidden>
          <rect width="16" height="8" rx="4" fill={series} opacity="0.3" />
        </svg>
      );
    /* Texture rather than a second colour: critical against safe is a ΔE 4.1
     * pair under deuteranopia, far below the floor of 8. Same recipe the
     * dashboard's bar chart uses, so the mark means the same thing twice. */
    case "hatch":
      return (
        <span
          aria-hidden
          className="inline-block h-2 w-4 rounded-full"
          style={{
            background:
              "repeating-linear-gradient(45deg, var(--viz-series) 0 2px, transparent 2px 5px)",
            boxShadow: "inset 0 0 0 1px var(--viz-series)",
          }}
        />
      );
    case "dot":
      return (
        <svg width="16" height="8" aria-hidden>
          <circle cx="8" cy="4" r="4" fill={series} />
        </svg>
      );
    case "open":
      return (
        <svg width="16" height="8" aria-hidden>
          <circle cx="8" cy="4" r="3.5" fill="var(--background)" stroke={series} strokeWidth="2" />
        </svg>
      );
    default:
      return null;
  }
}
