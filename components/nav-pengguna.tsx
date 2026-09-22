"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ChevronsUpDown, LogIn, LogOut } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu, SidebarMenuButton, SidebarMenuItem, useSidebar,
} from "@/components/ui/sidebar";

const PERAN: Record<string, string> = {
  planner: "hanya membaca",
  buyer: "sampai Rp 500 juta",
  procurement_lead: "sampai Rp 10 miliar",
  admin: "sampai Rp 10 miliar",
};

export function NavPengguna({
  pengguna,
}: { pengguna?: { nama: string; peran: string; email: string } }) {
  const { isMobile } = useSidebar();
  const r = useRouter();
  const [sibuk, setSibuk] = useState(false);

  if (!pengguna) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton onClick={() => r.push("/masuk")} tooltip="Masuk">
            <LogIn />
            <span>Masuk</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  async function keluar() {
    setSibuk(true);
    await fetch("/api/masuk", { method: "DELETE" });
    r.push("/");
    r.refresh();
  }

  const inisial = pengguna.nama.split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent">
              <Avatar className="h-8 w-8 rounded-lg">
                <AvatarFallback className="rounded-lg">{inisial}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{pengguna.nama}</span>
                <span className="truncate text-xs">{PERAN[pengguna.peran] ?? pengguna.peran}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="font-normal">
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{pengguna.nama}</span>
                <span className="truncate text-xs font-mono">{pengguna.email}</span>
                <span className="mt-1 truncate text-xs text-muted-foreground">
                  Wewenang: {PERAN[pengguna.peran] ?? pengguna.peran}
                </span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={keluar} disabled={sibuk}>
              <LogOut />
              {sibuk ? "Keluar…" : "Keluar"}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
