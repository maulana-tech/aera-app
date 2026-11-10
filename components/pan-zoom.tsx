"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";


/* A pan + zoom viewport: scroll to zoom toward the cursor, drag the background
 * to pan. The content is transformed with a single CSS transform, so React
 * still owns every node and edge — d3 never touches the DOM. Node buttons keep
 * their own click (pointerdown on a node does not start a pan). */
const MIN_S = 0.3;
const MAX_S = 2.5;

function ZoomBtn({ onClick, label, children }: { onClick: () => void; label: string; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="bg-card hover:bg-muted text-muted-foreground hover:text-foreground flex size-7 items-center justify-center border-b last:border-b-0"
    >
      {children}
    </button>
  );
}

export function PanZoom({
  innerW, innerH, onBackgroundClick, children, height = 480, fit = false,
}: {
  innerW: number; innerH: number; onBackgroundClick: () => void; children: ReactNode;
  /** The viewport's height in CSS pixels. */
  height?: number;
  /** Start (and reset) zoomed out until the whole canvas is in view. */
  fit?: boolean;
}) {
  const vpRef = useRef<HTMLDivElement | null>(null);
  const [view, setView] = useState({ s: 1, x: 24, y: 8 });
  const [isPanning, setIsPanning] = useState(false);
  const pan = useRef<{ x: number; y: number; ox: number; oy: number; moved: boolean } | null>(null);

  const home = useCallback(() => {
    const el = vpRef.current;
    if (!fit || !el) return { s: 1, x: 24, y: 8 };
    const s = Math.max(MIN_S, Math.min(1, (el.clientWidth - 48) / innerW, (height - 24) / innerH));
    return { s, x: Math.max(24, (el.clientWidth - innerW * s) / 2), y: Math.max(8, (height - innerH * s) / 2) };
  }, [fit, innerW, innerH, height]);
  const reset = useCallback(() => setView(home()), [home]);
  // Fitted once the viewport has a size, which the observer's first report gives.
  useEffect(() => {
    const el = vpRef.current;
    if (!fit || !el) return;
    const ro = new ResizeObserver(() => { setView(home()); ro.disconnect(); });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit, home]);
  const zoomBy = useCallback((factor: number) => setView((v) => {
    const el = vpRef.current;
    const cx = el ? el.clientWidth / 2 : 0;
    const cy = el ? el.clientHeight / 2 : 0;
    const s = Math.min(MAX_S, Math.max(MIN_S, v.s * factor));
    const k = s / v.s;
    return { s, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k };
  }), []);

  // Wheel-zoom toward the cursor. Attached natively so preventDefault works
  // (React's onWheel is passive and cannot stop the page from scrolling).
  useEffect(() => {
    const el = vpRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      setView((v) => {
        const s = Math.min(MAX_S, Math.max(MIN_S, v.s * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
        const k = s / v.s;
        return { s, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("button")) return; // a node, not the canvas
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    pan.current = { x: e.clientX, y: e.clientY, ox: view.x, oy: view.y, moved: false };
    setIsPanning(true);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const p = pan.current;
    if (!p) return;
    const dx = e.clientX - p.x;
    const dy = e.clientY - p.y;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) p.moved = true;
    setView((v) => ({ ...v, x: p.ox + dx, y: p.oy + dy }));
  };
  const onPointerUp = () => {
    const p = pan.current;
    pan.current = null;
    setIsPanning(false);
    if (p && !p.moved) onBackgroundClick(); // a click on empty canvas clears selection
  };

  return (
    <div
      ref={vpRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
      className="bg-muted/20 relative w-full touch-none overflow-hidden rounded-lg border"
      style={{ height, cursor: isPanning ? "grabbing" : "grab" }}
    >
      <div
        className="absolute left-0 top-0 origin-top-left"
        style={{ width: innerW, height: innerH, transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})` }}
      >
        {children}
      </div>

      {/* zoom controls */}
      <div className="absolute right-2 top-2 flex flex-col overflow-hidden rounded-md border shadow-sm">
        <ZoomBtn onClick={() => zoomBy(1.2)} label="Zoom in"><Plus className="size-3.5" /></ZoomBtn>
        <ZoomBtn onClick={() => zoomBy(1 / 1.2)} label="Zoom out"><Minus className="size-3.5" /></ZoomBtn>
        <ZoomBtn onClick={reset} label="Reset view"><Maximize2 className="size-3.5" /></ZoomBtn>
      </div>
      <p className="text-muted-foreground pointer-events-none absolute bottom-2 left-2 text-[10px]">
        scroll to zoom · drag to pan · {Math.round(view.s * 100)}%
      </p>
    </div>
  );
}
