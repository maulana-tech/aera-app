"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/** True when the visitor asked the system for less motion. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const q = window.matchMedia("(prefers-reduced-motion: reduce)");
    const set = () => setReduced(q.matches);
    set();
    q.addEventListener("change", set);
    return () => q.removeEventListener("change", set);
  }, []);
  return reduced;
}

/** True once the element has scrolled into view (and stays true). */
export function useInView<T extends Element>(margin = "0px 0px -4% 0px") {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    const io = new IntersectionObserver(([e]) => { if (e?.isIntersecting) { setSeen(true); io.disconnect(); } },
      { rootMargin: margin });
    io.observe(el);
    return () => io.disconnect();
  }, [margin, seen]);
  return [ref, seen] as const;
}

/** Fades and lifts its children in once, when they scroll into view.
 *  Progressive: the server renders it visible; only an element that is below the fold when the page loads is
 *  hidden (by attribute, in CSS) and brought in when it scrolls into view. No JavaScript, or reduced motion, and
 *  everything simply shows. */
export function Reveal({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (el.getBoundingClientRect().top < window.innerHeight) return;      // already on screen: leave it be
    el.dataset.reveal = "hidden";
    const io = new IntersectionObserver(([e]) => {
      if (e?.isIntersecting) { el.dataset.reveal = "shown"; io.disconnect(); }
    }, { rootMargin: "0px 0px -4% 0px" });
    io.observe(el);
    return () => { io.disconnect(); el.dataset.reveal = "shown"; };
  }, []);
  return <div ref={ref} style={{ transitionDelay: `${delay}ms` }} className={cn("reveal", className)}>{children}</div>;
}

/** A figure that counts up from zero when it scrolls into view. */
export function CountUp({ value, format }: { value: number | null; format: "usd" | "int" }) {
  const [ref, seen] = useInView<HTMLSpanElement>();
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (value == null || !seen || reduced) return;
    const start = performance.now();
    const ms = 1100;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms);
      setShown(value * (1 - Math.pow(1 - k, 3)));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, seen, reduced]);
  const n = reduced && value != null ? value : shown;
  const text = value == null ? "-"
    : format === "usd" ? `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : Math.round(n).toLocaleString("en-US");
  return <span ref={ref}>{text}</span>;
}
