"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AlertTriangle, Boxes, Calculator, FileText, Inbox, LayoutDashboard, Mail,
  MessagesSquare, PackageSearch, ScrollText, Ship, TrendingUp, Upload, Users, Zap,
} from "lucide-react";

import { NavPengguna } from "@/components/nav-pengguna";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarRail,
} from "@/components/ui/sidebar";

const GRUP = [
  {
    label: null,
    isi: [
      { judul: "Dasbor", href: "/dasbor", icon: LayoutDashboard },
      { judul: "Antrean keputusan", href: "/", icon: Inbox },
      { judul: "Percakapan", href: "/chat", icon: MessagesSquare },
    ],
  },
  {
    label: "Data",
    isi: [
      { judul: "Permintaan", href: "/data/permintaan", icon: TrendingUp },
      { judul: "Stok", href: "/data/stok", icon: Boxes },
      { judul: "Sumber pasokan", href: "/data/sumber", icon: PackageSearch },
      { judul: "Logistik", href: "/data/logistik", icon: Ship },
      { judul: "Perhitungan", href: "/data/perhitungan", icon: Calculator },
      { judul: "Eksekusi", href: "/data/eksekusi", icon: Zap },
    ],
  },
  {
    label: "Lainnya",
    isi: [
      { judul: "Tim agent", href: "/agent", icon: Users },
      { judul: "Log", href: "/log", icon: ScrollText },
      { judul: "Laporan", href: "/laporan", icon: FileText },
      { judul: "Unggah data", href: "/unggah", icon: Upload },
      { judul: "Kontak", href: "/kontak", icon: Mail },
    ],
  },
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
                <span className="flex-1 truncate text-left font-semibold tracking-tight">SIGAP</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {GRUP.map((g, i) => (
          <SidebarGroup key={g.label ?? i}>
            {g.label && <SidebarGroupLabel>{g.label}</SidebarGroupLabel>}
            <SidebarMenu>
              {g.isi.map((m) => (
                <SidebarMenuItem key={m.href}>
                  <SidebarMenuButton
                    asChild
                    tooltip={m.judul}
                    isActive={m.href === "/" ? jalur === "/" : jalur.startsWith(m.href)}
                  >
                    <Link href={m.href}>
                      <m.icon />
                      <span>{m.judul}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <NavPengguna pengguna={pengguna} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
