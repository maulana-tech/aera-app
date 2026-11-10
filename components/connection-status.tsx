"use client";

import { ChevronsUpDown, Circle } from "lucide-react";

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar,
} from "@/components/ui/sidebar";

export type Connection = {
  env: string;
  model_ready: boolean;
  private_mode?: boolean;
  rail?: "vault" | "simulated";
  network?: string;
};

/** Stands in for sidebar-07's team switcher: what matters here isn't which team,
 *  but whether the system can actually reason about anything. */
export function ConnectionStatus({ c }: { c?: Connection }) {
  const { isMobile } = useSidebar();
  const ready = !!c?.model_ready;
  const dot = ready
    ? "fill-emerald-500 text-emerald-500"
    : "fill-muted-foreground/40 text-muted-foreground/40";

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
              <div className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg text-[11px] font-bold">
                AE
              </div>
              <div className="grid flex-1 text-left leading-tight">
                <span className="truncate font-semibold tracking-tight">AERA</span>
                <span className="text-muted-foreground flex items-center gap-1 truncate text-xs">
                  <Circle className={`size-2 ${dot}`} />
                  {ready ? "connected" : "not connected"}
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
              Environment {c?.env ?? "unknown"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled className="opacity-100">
              <Circle className={`size-2 ${c?.rail === "vault" ? "fill-emerald-500 text-emerald-500" : "fill-amber-500 text-amber-500"}`} />
              <span className="flex-1">Money rail</span>
              <span className="text-muted-foreground font-mono text-[10px]">
                {c?.rail === "vault" ? `vault · ${c.network}` : "SIMULATED"}
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="opacity-100">
              <Circle className={`size-2 ${c?.private_mode ? "fill-emerald-500 text-emerald-500" : "fill-amber-500 text-amber-500"}`} />
              <span className="flex-1">Private AI</span>
              <span className="text-muted-foreground font-mono text-[10px]">{c?.private_mode ? "TEE only" : "off"}</span>
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="opacity-100">
              <Circle className={`size-2 ${ready ? "fill-emerald-500 text-emerald-500" : "fill-amber-500 text-amber-500"}`} />
              <span className="flex-1">Reasoning engine</span>
              <span className="text-muted-foreground font-mono text-[10px]">
                {ready ? "ready" : "not set"}
              </span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <p className="text-muted-foreground px-2 py-1.5 text-xs leading-relaxed">
              {ready
                ? "Every agent reasons on a NEAR AI Cloud model; each call carries an attestation proof you can re-check on the run."
                : "Until a model is connected, the team makes no decisions at all: work is held, not guessed."}
            </p>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
