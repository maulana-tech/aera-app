"use client";

import { ChevronRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AeraMark } from "@/components/aera-mark";

export const REPO = "https://github.com/maulana-tech/aera-app";

const ITEMS = [
  { id: "product", label: "Product" },
  { id: "how-it-works", label: "How it works" },
  { id: "guardian", label: "Guardian" },
  { id: "faq", label: "FAQ" },
] as const;

function GitHubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className={className} fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}
export { GitHubMark };

/** The floating bar: wordmark left, the sections as a centred pill group, the app as a white capsule. */
export function Nav({ cta }: { cta: { href: string; label: string } }) {
  const [active, setActive] = useState<string>("product");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) setActive(e.target.id);
        else setActive((cur) => (cur === e.target.id ? "" : cur));
      }
    }, { rootMargin: "-40% 0px -55% 0px" });
    for (const { id } of ITEMS) { const el = document.getElementById(id); if (el) io.observe(el); }
    return () => io.disconnect();
  }, []);

  return (
    <nav className="sticky top-0 z-50 flex h-[76px] items-center px-4 md:px-6">
      <div className="relative mx-auto flex h-full w-full max-w-[1240px] items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 text-white" aria-label="AERA">
          <AeraMark className="size-7" />
          <span className="text-[21px] tracking-[-0.02em]">aera</span>
        </Link>
        <ul className="ln-nav-menu absolute left-1/2 hidden -translate-x-1/2 items-center gap-0.5 rounded-full p-1 md:flex">
          {ITEMS.map((i) => (
            <li key={i.id}>
              <a href={`#${i.id}`} aria-current={active === i.id ? "true" : undefined}
                className="ln-nav-link flex items-center rounded-full px-3.5 py-1.5 text-[13px]">{i.label}</a>
            </li>
          ))}
          <li>
            <a href={REPO} target="_blank" rel="noopener noreferrer" className="ln-nav-link flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[13px]">
              <GitHubMark className="size-3.5" /> GitHub
            </a>
          </li>
        </ul>
        <div className="flex items-center gap-2">
          {cta.href === "/login" && (
            <Link href="/login?mode=signup" className="hidden h-9 items-center rounded-full px-3.5 text-[13.5px] text-white/90 hover:bg-white/10 sm:inline-flex">Sign up</Link>
          )}
          <Link href={cta.href} className="ln-nav-cta group hidden h-9 items-center gap-2 rounded-full pr-3 pl-2 text-[13.5px] sm:inline-flex">
            <span className="bg-brand grid size-[18px] place-items-center rounded-[5px] text-white transition-transform duration-500 group-hover:scale-110">
              <AeraMark className="size-3" />
            </span>
            {cta.label}
            <ChevronRight className="size-3.5 opacity-70" />
          </Link>
          <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Menu"
            className="grid size-9 place-items-center rounded-full text-white hover:bg-white/10 md:hidden">
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
        <div aria-hidden="true" className="ln-rule pointer-events-none absolute inset-x-0 bottom-0 h-px" />
        <span aria-hidden="true" className="absolute bottom-0 left-0 -mb-[5px] -ml-[4px] text-[10px] leading-none text-white/40">+</span>
        <span aria-hidden="true" className="absolute right-0 bottom-0 -mr-[4px] -mb-[5px] text-[10px] leading-none text-white/40">+</span>
      </div>
      {open && (
        <div className="absolute inset-x-3 top-[72px] rounded-2xl border bg-white p-2 shadow-float md:hidden">
          {ITEMS.map((i) => (
            <a key={i.id} href={`#${i.id}`} onClick={() => setOpen(false)} className="text-fg hover:bg-raised block rounded-xl px-4 py-3 text-[15px]">{i.label}</a>
          ))}
          <a href={REPO} className="text-fg hover:bg-raised block rounded-xl px-4 py-3 text-[15px]">GitHub</a>
          <Link href={cta.href} className="bg-brand mt-1 flex h-11 items-center justify-center rounded-xl text-[15px] text-white">{cta.label}</Link>
          {cta.href === "/login" && <Link href="/login?mode=signup" className="text-brand mt-1 flex h-11 items-center justify-center rounded-xl text-[15px]">Create an account</Link>}
        </div>
      )}
    </nav>
  );
}
