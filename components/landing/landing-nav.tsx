"use client";

import { ArrowRight, Check, Copy, Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AeraMark } from "@/components/aera-mark";
import { cn } from "@/lib/utils";

const LINKS = [["how", "How it works"], ["playground", "Try the Guardian"], ["team", "The team"], ["proof", "Proof"]] as const;

/** The landing header: the section in view is marked, and on a phone the links fold into a menu. */
export function LandingNav({ primary, signedIn }: { primary: { href: string; label: string }; signedIn: boolean }) {
  const [active, setActive] = useState<string>("");
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) setActive(e.target.id);
    }, { rootMargin: "-45% 0px -50% 0px" });
    for (const [id] of LINKS) { const el = document.getElementById(id); if (el) io.observe(el); }
    return () => { window.removeEventListener("scroll", onScroll); io.disconnect(); };
  }, []);

  return (
    <header className={cn("sticky top-0 z-30 border-b transition-colors",
      scrolled || open ? "border-white/10 bg-[color-mix(in_oklab,var(--canvas)_90%,transparent)] backdrop-blur" : "border-transparent")}>
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-3 px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2.5 text-white">
          <AeraMark className="size-6" />
          <span className="text-[19px] tracking-[-0.02em]">aera</span>
        </Link>
        <nav className="ml-6 hidden items-center gap-1 text-[13.5px] md:flex">
          {LINKS.map(([id, label]) => (
            <a key={id} href={`#${id}`}
              className={cn("rounded-md px-3 py-1.5 transition-colors", active === id ? "bg-white/15 text-white" : "text-white/80 hover:bg-white/10 hover:text-white")}>
              {label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {!signedIn && (
            <Link href="/login" className="hidden rounded-md px-3 py-1.5 text-[13.5px] text-white/90 hover:bg-white/10 sm:inline-flex">Sign in</Link>
          )}
          <Link href={primary.href}
            className="text-brand hidden h-9 items-center gap-1.5 rounded-md bg-white px-3.5 text-[13.5px] shadow-soft hover:bg-white/90 sm:inline-flex">
            {primary.label} <ArrowRight className="size-3.5" />
          </Link>
          <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Menu"
            className="inline-flex size-9 items-center justify-center rounded-md text-white hover:bg-white/10 md:hidden">
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>
      {open && (
        <nav className="animate-in fade-in slide-in-from-top-1 border-t border-white/10 px-4 pt-2 pb-4 md:hidden">
          {LINKS.map(([id, label]) => (
            <a key={id} href={`#${id}`} onClick={() => setOpen(false)} className="block rounded-md px-3 py-2.5 text-[15px] text-white/90 hover:bg-white/10">{label}</a>
          ))}
          <Link href="/samples" className="block rounded-md px-3 py-2.5 text-[15px] text-white/90 hover:bg-white/10">Free samples</Link>
          <Link href={primary.href} className="text-brand mt-2 flex h-11 items-center justify-center gap-1.5 rounded-lg bg-white text-[15px]">
            {primary.label} <ArrowRight className="size-4" />
          </Link>
          {!signedIn && <Link href="/login" className="mt-2 block text-center text-[14px] text-white/80">Sign in</Link>}
        </nav>
      )}
    </header>
  );
}

/** A transaction hash you can copy, with its NearBlocks link. */
export function CopyHash({ hash }: { hash: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="mt-4 inline-flex items-center gap-1">
      <a href={`https://testnet.nearblocks.io/txns/${hash}`} target="_blank" rel="noopener noreferrer"
        className="text-brand inline-flex items-center gap-1.5 font-mono text-[12px] underline-offset-2 hover:underline">
        {hash.slice(0, 10)}… on NearBlocks <ArrowRight className="size-3" />
      </a>
      <button type="button" aria-label="Copy the transaction hash"
        onClick={async () => { try { await navigator.clipboard.writeText(hash); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* no clipboard */ } }}
        className="text-muted-foreground hover:text-fg hover:bg-raised inline-flex size-7 items-center justify-center rounded-md">
        {copied ? <Check className="text-ok size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </span>
  );
}
