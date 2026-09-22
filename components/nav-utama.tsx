"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  SidebarGroup, SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem,
} from "@/components/ui/sidebar";

export type Butir = {
  judul: string;
  href: string;
  icon: React.ElementType;
  anak?: { judul: string; href: string; oleh?: string }[];
};

const aktif = (jalur: string, href: string) =>
  href === "/" ? jalur === "/" : jalur === href || jalur.startsWith(href + "/");

export function NavUtama({ label, butir }: { label?: string; butir: Butir[] }) {
  const jalur = usePathname();

  return (
    <SidebarGroup>
      {label && <SidebarGroupLabel>{label}</SidebarGroupLabel>}
      <SidebarMenu>
        {butir.map((b) => {
          if (!b.anak) {
            return (
              <SidebarMenuItem key={b.href}>
                <SidebarMenuButton asChild tooltip={b.judul} isActive={aktif(jalur, b.href)}>
                  <Link href={b.href}>
                    <b.icon />
                    <span>{b.judul}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          }

          const adaYangAktif = b.anak.some((a) => aktif(jalur, a.href));
          return (
            <Collapsible
              key={b.judul}
              asChild
              defaultOpen={adaYangAktif}
              className="group/collapsible"
            >
              <SidebarMenuItem>
                <CollapsibleTrigger asChild>
                  <SidebarMenuButton tooltip={b.judul} isActive={adaYangAktif}>
                    <b.icon />
                    <span>{b.judul}</span>
                    <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                  </SidebarMenuButton>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <SidebarMenuSub>
                    {b.anak.map((a) => (
                      <SidebarMenuSubItem key={a.href}>
                        <SidebarMenuSubButton asChild isActive={aktif(jalur, a.href)}>
                          <Link href={a.href}>
                            <span>{a.judul}</span>
                            {a.oleh && (
                              <span className="text-muted-foreground ml-auto text-[10px]">
                                {a.oleh}
                              </span>
                            )}
                          </Link>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    ))}
                  </SidebarMenuSub>
                </CollapsibleContent>
              </SidebarMenuItem>
            </Collapsible>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  );
}
