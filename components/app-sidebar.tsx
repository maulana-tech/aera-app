"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertTriangle, Inbox, Users } from "lucide-react";

import { NavPengguna } from "@/components/nav-pengguna";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupLabel,
  SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem, SidebarRail,
} from "@/components/ui/sidebar";

const MENU = [
  { judul: "Antrean keputusan", href: "/", icon: Inbox },
  { judul: "Tim agent", href: "/agent", icon: Users },
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
                <div className="grid flex-1 text-left leading-tight">
                  <span className="truncate font-semibold">SIGAP</span>
                  <span className="text-muted-foreground truncate text-xs">Gangguan pasokan</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          
          <SidebarMenu>
            {MENU.map((m) => (
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
      </SidebarContent>

      <SidebarFooter>
        <NavPengguna pengguna={pengguna} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
