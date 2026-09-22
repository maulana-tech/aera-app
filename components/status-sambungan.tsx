"use client";

import { ChevronsUpDown, Circle } from "lucide-react";

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar,
} from "@/components/ui/sidebar";

export type Sambungan = { lingkungan: string; sap_siap: boolean; model_siap: boolean };

/** Pengganti team switcher di sidebar-07: di sini yang penting bukan tim mana,
 *  tapi apakah sistemnya benar-benar tersambung. */
export function StatusSambungan({ s }: { s?: Sambungan }) {
  const { isMobile } = useSidebar();
  const siap = !!s?.sap_siap && !!s?.model_siap;
  const sebagian = !!s?.sap_siap !== !!s?.model_siap;

  const warna = siap
    ? "fill-emerald-500 text-emerald-500"
    : sebagian
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
                  <Circle className={`size-2 ${warna}`} />
                  {siap ? "tersambung" : sebagian ? "sebagian" : "belum tersambung"}
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
              Lingkungan {s?.lingkungan ?? "—"}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled className="opacity-100">
              <Circle className={`size-2 ${s?.sap_siap ? "fill-emerald-500 text-emerald-500" : "fill-amber-500 text-amber-500"}`} />
              <span className="flex-1">Data SAP</span>
              <span className="text-muted-foreground font-mono text-[10px]">
                {s?.sap_siap ? "siap" : "belum"}
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem disabled className="opacity-100">
              <Circle className={`size-2 ${s?.model_siap ? "fill-emerald-500 text-emerald-500" : "fill-amber-500 text-amber-500"}`} />
              <span className="flex-1">Mesin penalaran</span>
              <span className="text-muted-foreground font-mono text-[10px]">
                {s?.model_siap ? "siap" : "belum"}
              </span>
            </DropdownMenuItem>
            {!siap && (
              <>
                <DropdownMenuSeparator />
                <p className="text-muted-foreground px-2 py-1.5 text-xs leading-relaxed">
                  Selama belum tersambung, sistem tidak membuat keputusan apa pun.
                </p>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
