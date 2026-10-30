"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Check, ChevronsUpDown, Circle, Database, FlaskConical } from "lucide-react";

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar,
} from "@/components/ui/sidebar";

export type Connection = {
  env: string;
  sap_ready: boolean;
  model_ready: boolean;
  /** Where the tools read enterprise data from. Absent on an older service. */
  data_mode?: "live" | "demo";
  /** Whether a SAP key is configured at all, regardless of the mode. */
  sap_key_set?: boolean;
};

/* The two data modes, as the sidebar says them.
 *
 * This is not cosmetic. A SAP sandbox whose quota is spent does not fail
 * quietly: every tool raises, and a handling finishes with no action at all.
 * The same event, on the same uploaded data, runs to completion with SAP off.
 * So the switch is the answer to "the sandbox died ten minutes before we
 * present" - and the mode it chooses is enforced on the server, in the one
 * gate every tool already asks (clients/sap_s4.available()). */
const MODES = [
  {
    id: "live" as const,
    label: "Live mode",
    icon: Database,
    blurb: "Tools read SAP S/4HANA. Uploads fill only what SAP has no source for.",
  },
  {
    id: "demo" as const,
    label: "Demo mode",
    icon: FlaskConical,
    blurb: "No SAP call at all. Tools read your uploads and the modelled fixtures — and every figure still carries its origin.",
  },
];

/** Stands in for sidebar-07's team switcher: what matters here isn't which team,
 *  but whether the system is actually connected to anything. */
export function ConnectionStatus({ c, mayChange = false }: { c?: Connection; mayChange?: boolean }) {
  const { isMobile } = useSidebar();
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const mode = c?.data_mode ?? "live";
  const demo = mode === "demo";
  // In demo mode the tools are deliberately not reaching SAP, so "not
  // connected" would be a lie: it is connected to the data it was told to use.
  const ready = demo ? !!c?.model_ready : !!c?.sap_ready && !!c?.model_ready;
  const partial = !demo && !!c?.sap_ready !== !!c?.model_ready;

  async function choose(next: "live" | "demo") {
    if (next === mode || busy) return;
    setBusy(next);
    setError("");
    try {
      const res = await fetch("/api/sigap/mode", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ mode: next }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "could not switch");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not switch");
    } finally {
      setBusy("");
    }
  }

  const dot = demo
    ? "fill-sky-500 text-sky-500"
    : ready
    ? "fill-emerald-500 text-emerald-500"
    : partial
      ? "fill-amber-500 text-amber-500"
      : "fill-muted-foreground/40 text-muted-foreground/40";

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
              <div className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg text-[11px] font-bold">
                SG
              </div>
              <div className="grid flex-1 text-left leading-tight">
                <span className="truncate font-semibold tracking-tight">SIGAP</span>
                <span className="text-muted-foreground flex items-center gap-1 truncate text-xs">
                  <Circle className={`size-2 ${dot}`} />
                  {demo ? "demo data" : ready ? "connected" : partial ? "partly connected" : "not connected"}
                </span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-60 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="start"
            sideOffset={4}
          >
            <DropdownMenuLabel className="text-muted-foreground text-xs">
              Data source
            </DropdownMenuLabel>
            {MODES.map((m) => {
              const on = m.id === mode;
              return (
                <DropdownMenuItem
                  key={m.id}
                  disabled={!mayChange || !!busy}
                  onSelect={(e) => {
                    e.preventDefault();
                    void choose(m.id);
                  }}
                  className="items-start gap-2 py-2 disabled:opacity-100"
                >
                  <m.icon className={`mt-0.5 size-4 shrink-0 ${on ? "" : "text-muted-foreground"}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className={on ? "font-medium" : ""}>{m.label}</span>
                      {busy === m.id && (
                        <span className="text-muted-foreground text-[10px]">switching…</span>
                      )}
                    </div>
                    <p className="text-muted-foreground mt-0.5 text-xs leading-snug whitespace-normal">
                      {m.blurb}
                    </p>
                  </div>
                  {on && <Check className="mt-0.5 size-4 shrink-0" />}
                </DropdownMenuItem>
              );
            })}
            {!mayChange && (
              <p className="text-muted-foreground px-2 pb-1.5 text-xs leading-relaxed">
                Only an admin or a procurement lead can change this.
              </p>
            )}
            {error && <p className="text-destructive px-2 pb-1.5 text-xs">{error}</p>}

            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-muted-foreground text-xs">
              Environment {c?.env ?? "unknown"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled className="opacity-100">
              <Circle className={`size-2 ${c?.sap_ready ? "fill-emerald-500 text-emerald-500" : "fill-amber-500 text-amber-500"}`} />
              <span className="flex-1">SAP data</span>
              <span className="text-muted-foreground font-mono text-[10px]">
                {c?.sap_ready ? "ready" : demo ? "off in demo" : c?.sap_key_set ? "key set, not answering" : "not set"}
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="opacity-100">
              <Circle className={`size-2 ${c?.model_ready ? "fill-emerald-500 text-emerald-500" : "fill-amber-500 text-amber-500"}`} />
              <span className="flex-1">Reasoning engine</span>
              <span className="text-muted-foreground font-mono text-[10px]">
                {c?.model_ready ? "ready" : "not set"}
              </span>
            </DropdownMenuItem>
            {!ready && (
              <>
                <DropdownMenuSeparator />
                <p className="text-muted-foreground px-2 py-1.5 text-xs leading-relaxed">
                  Until it is connected, the system makes no decisions at all.
                </p>
              </>
            )}
            {demo && (
              <>
                <DropdownMenuSeparator />
                <p className="text-muted-foreground px-2 py-1.5 text-xs leading-relaxed">
                  Nothing is invented in demo mode. The figures come from your
                  uploads and the shipped fixtures, and each one still says
                  whether it is uploaded, derived or modelled.
                </p>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
