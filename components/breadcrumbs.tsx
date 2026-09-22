"use client";

import { usePathname } from "next/navigation";

import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  chat: "Conversation",
  data: "Supply data",
  demand: "Demand",
  inventory: "Stock",
  sourcing: "Supply options",
  logistics: "Logistics",
  simulation: "Costing",
  execution: "Execution",
  agents: "Agent team",
  log: "Log",
  reports: "Reports",
  uploads: "Upload data",
  contacts: "Contacts",
  disruptions: "Handling",
};

/** Segments that aren't pages of their own — shown, but not clickable. */
const NOT_A_PAGE = new Set(["data", "disruptions"]);

export function Breadcrumbs() {
  const pathname = usePathname();
  const parts = pathname.split("/").filter(Boolean);

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          {parts.length === 0 ? (
            <BreadcrumbPage>Decision queue</BreadcrumbPage>
          ) : (
            <BreadcrumbLink href="/">Queue</BreadcrumbLink>
          )}
        </BreadcrumbItem>

        {parts.map((part, i) => {
          const last = i === parts.length - 1;
          const href = "/" + parts.slice(0, i + 1).join("/");
          const label = LABELS[part] ?? (part.length > 14 ? part.slice(0, 10) + "…" : part);
          return (
            <span key={href} className="contents">
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                {last || NOT_A_PAGE.has(part) ? (
                  <BreadcrumbPage className={last ? "" : "text-muted-foreground"}>
                    {label}
                  </BreadcrumbPage>
                ) : (
                  <BreadcrumbLink href={href}>{label}</BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </span>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
