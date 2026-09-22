"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertTriangle, BookOpen, Inbox, Radar, ShieldCheck } from "lucide-react";

import { NavPengguna } from "@/components/nav-pengguna";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarRail,
} from "@/components/ui/sidebar";

const MENU = [
  { judul: "Antrean keputusan", href: "/", icon: Inbox },
  { judul: "Risiko laten", href: "/risiko", icon: Radar, segera: true },
  { judul: "Aturan lokal", href: "/aturan", icon: ShieldCheck, segera: true },
  { judul: "Catatan tindakan", href: "/catatan", icon: BookOpen, segera: true },
];

export function AppSidebar({
  pengguna,
  ...props
}: { pengguna?: { nama: string; peran: string; email: string } } & React.ComponentProps<typeof Sidebar>) {
  const jalur = usePathname();

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/">
                <div className="bg-primary text-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
                  <AlertTriangle className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">SIGAP</span>
                  <span className="truncate text-xs">Respons gangguan pasokan</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Kerja harian</SidebarGroupLabel>
          <SidebarMenu>
            {MENU.map((m) => (
              <SidebarMenuItem key={m.href}>
                {m.segera ? (
                  // Ikon dan teks HARUS jadi anak langsung — SidebarMenuButton
                  // menata anak langsungnya, bungkus apa pun merusak barisnya.
                  <SidebarMenuButton
                    disabled
                    tooltip={`${m.judul} — belum ada`}
                    className="cursor-not-allowed opacity-45"
                  >
                    <m.icon />
                    <span>{m.judul}</span>
                  </SidebarMenuButton>
                ) : (
                  <SidebarMenuButton asChild tooltip={m.judul} isActive={jalur === m.href}>
                    <Link href={m.href}>
                      <m.icon />
                      <span>{m.judul}</span>
                    </Link>
                  </SidebarMenuButton>
                )}
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <NavPengguna pengguna={pengguna} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
