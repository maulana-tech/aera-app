"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";

/* useLayoutEffect warns on the server, where it never runs. Swap it out there
 * so the client can keep measuring before the first paint. */
const useIsoLayoutEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

/** The width of the box the chart sits in, in CSS pixels, kept in step with it.
 *
 * Charts are drawn 1:1 with the page rather than scaled out of a fixed viewBox,
 * because a stretched viewBox scales the type with it: a 10px axis label lands
 * at 22px on a 1600px card, next to a 10px caption that does not scale. Sizing
 * the SVG to its container keeps every label the size it was drawn at.
 *
 * Measured in a layout effect, so the first painted frame already has the real
 * width and the reader never sees the fallback size flash in.
 */
export function useChartWidth(fallback = 720) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);

  useIsoLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => setWidth(el.clientWidth);
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return { ref, width: width || fallback };
}
