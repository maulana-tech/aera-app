"use client";

import Link from "next/link";

import {
  Briefcase, Inbox, Landmark, LayoutDashboard, MessagesSquare, ReceiptText,
  Settings2, ShoppingBag, Users,
} from "lucide-react";

import { AeraMark } from "@/components/aera-mark";
import { NavMain, type NavItem } from "@/components/nav-main";
import { NavUser } from "@/components/nav-user";
import { ConnectionStatus, type Connection } from "@/components/connection-status";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail,
} from "@/components/ui/sidebar";

const RUN: NavItem[] = [
  { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { title: "Work", href: "/work", icon: Inbox },
  { title: "Orders", href: "/orders", icon: ShoppingBag },
  { title: "Team", href: "/agents", icon: Users },
  { title: "Business", href: "/business", icon: Briefcase },
];

const MONEY: NavItem[] = [
  { title: "Treasury", href: "/treasury", icon: Landmark },
  { title: "Ledger", href: "/ledger", icon: ReceiptText },
  { title: "Chat", href: "/chat", icon: MessagesSquare },
];

const SETTINGS: NavItem[] = [
  {
    title: "Settings",
    href: "/settings",
    icon: Settings2,
    children: [
      { title: "Models", href: "/models" },
      { title: "MCP", href: "/mcp" },
      { title: "Skills", href: "/skills" },
      { title: "Schedule", href: "/schedule" },
      { title: "Contacts", href: "/contacts" },
      { title: "Log", href: "/log" },
    ],
  },
];

export function AppSidebar({
  user, connection, ...props
}: {
  user?: { name: string; role: string; email: string; limit_usd?: number };
  connection?: Connection;
} & React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <Link
          href="/dashboard"
          className="flex items-center gap-2 rounded-md px-2 py-1.5 outline-none transition-colors hover:bg-sidebar-accent focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <AeraMark className="size-6 shrink-0" />
          <span className="truncate text-sm font-semibold tracking-[-0.03em] group-data-[collapsible=icon]:hidden">
            AERA
          </span>
        </Link>
        <ConnectionStatus c={connection} />
      </SidebarHeader>

      <SidebarContent>
        <NavMain items={RUN} />
        <NavMain items={MONEY} />
        <NavMain items={SETTINGS} />
      </SidebarContent>

      <SidebarFooter>
        <NavUser user={user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
