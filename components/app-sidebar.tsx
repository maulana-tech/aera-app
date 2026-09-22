"use client";

import {
  Database, FileText, Inbox, LayoutDashboard, MessagesSquare,
  ScrollText, Settings2, Users,
} from "lucide-react";

import { NavMain, type NavItem } from "@/components/nav-main";
import { NavUser } from "@/components/nav-user";
import { ConnectionStatus, type Connection } from "@/components/connection-status";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail,
} from "@/components/ui/sidebar";

const WORK: NavItem[] = [
  { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { title: "Decision queue", href: "/", icon: Inbox },
  { title: "Conversation", href: "/chat", icon: MessagesSquare },
];

const DATA: NavItem[] = [
  {
    title: "Supply data",
    href: "/data",
    icon: Database,
    children: [
      { title: "Demand", href: "/data/demand", owner: "Dara" },
      { title: "Stock", href: "/data/inventory", owner: "Iris" },
      { title: "Supply options", href: "/data/sourcing", owner: "Clint" },
      { title: "Logistics", href: "/data/logistics", owner: "Milo" },
      { title: "Costing", href: "/data/simulation", owner: "Tara" },
      { title: "Execution", href: "/data/execution", owner: "Bram" },
    ],
  },
  { title: "Agent team", href: "/agents", icon: Users },
];

const RECORDS: NavItem[] = [
  { title: "Log", href: "/log", icon: ScrollText },
  { title: "Reports", href: "/reports", icon: FileText },
];

const SETTINGS: NavItem[] = [
  {
    title: "Settings",
    href: "/settings",
    icon: Settings2,
    children: [
      { title: "Upload data", href: "/uploads" },
      { title: "Contacts", href: "/contacts" },
    ],
  },
];

export function AppSidebar({
  user, connection, ...props
}: {
  user?: { name: string; role: string; email: string };
  connection?: Connection;
} & React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <ConnectionStatus c={connection} />
      </SidebarHeader>

      <SidebarContent>
        <NavMain items={WORK} />
        <NavMain label="Data" items={DATA} />
        <NavMain label="Records" items={RECORDS} />
        <NavMain items={SETTINGS} />
      </SidebarContent>

      <SidebarFooter>
        <NavUser user={user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
