"use client";

import Link from "next/link";

import {
  ClipboardCheck, FileText, Inbox, LayoutDashboard, MessagesSquare,
  ScrollText, Settings2, Users,
} from "lucide-react";

import { AeraMark } from "@/components/aera-mark";
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

// One entry per agent who publishes work of their own. The roster page sits
// at the top of the list rather than beside it, so there is a single way in.
const AGENTS: NavItem[] = [
  {
    title: "Agent team",
    href: "/agents",
    icon: Users,
    children: [
      { title: "All agents", href: "/agents" },
      { title: "Impact", href: "/agents/impact", owner: "Elsa" },
      { title: "Demand", href: "/agents/demand", owner: "Dara" },
      { title: "Stock", href: "/agents/inventory", owner: "Iris" },
      { title: "Sourcing", href: "/agents/sourcing", owner: "Clint" },
      { title: "Procurement", href: "/agents/procurement", owner: "Prita" },
      { title: "Logistics", href: "/agents/logistics", owner: "Milo" },
      { title: "Rules", href: "/agents/compliance", owner: "Kira" },
      { title: "Costing", href: "/agents/simulation", owner: "Tara" },
      { title: "Execution", href: "/agents/execution", owner: "Bram" },
      { title: "Latent risk", href: "/agents/exposure", owner: "Vega" },
    ],
  },
];

const RECORDS: NavItem[] = [
  { title: "Data audit", href: "/audit", icon: ClipboardCheck },
  { title: "Log", href: "/log", icon: ScrollText },
  { title: "Reports", href: "/reports", icon: FileText },
];

const SETTINGS: NavItem[] = [
  {
    title: "Settings",
    href: "/settings",
    icon: Settings2,
    children: [
      { title: "MCP", href: "/mcp" },
      { title: "Skills", href: "/skills" },
      { title: "Upload data", href: "/uploads" },
      { title: "Contacts", href: "/contacts" },
      { title: "Models", href: "/models" },
      { title: "Schedule", href: "/schedule" },
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
        <Link
          href="/"
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
        <NavMain items={WORK} />
        <NavMain label="Agents" items={AGENTS} />
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
