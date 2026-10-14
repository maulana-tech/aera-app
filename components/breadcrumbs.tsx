"use client";

import { usePathname } from "next/navigation";

import {
  Breadcrumb, BreadcrumbEllipsis, BreadcrumbItem, BreadcrumbLink, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { cn } from "@/lib/utils";

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
  audit: "Data audit",
  log: "Log",
  reports: "Reports",
  uploads: "Upload data",
  contacts: "Contacts",
  disruptions: "Handling",
};

/** Segments that are not pages of their own. Shown, but not clickable. */
const NOT_A_PAGE = new Set(["data", "disruptions"]);

export function Breadcrumbs() {
  const pathname = usePathname();
  const parts = pathname.split("/").filter(Boolean);
  const deep = parts.length > 1;

  return (
    <Breadcrumb className="min-w-0">
      <BreadcrumbList className="flex-nowrap">
        <BreadcrumbItem className={cn(deep && "hidden md:inline-flex")}>
          {parts.length === 0 ? (
            <BreadcrumbPage>Decision queue</BreadcrumbPage>
          ) : (
            <BreadcrumbLink href="/">Queue</BreadcrumbLink>
          )}
        </BreadcrumbItem>

        {deep && (
          <span className="contents md:hidden">
            <BreadcrumbItem>
              <BreadcrumbEllipsis className="size-4" />
            </BreadcrumbItem>
            <BreadcrumbSeparator />
          </span>
        )}

        {parts.map((part, i) => {
          const last = i === parts.length - 1;
          const href = "/" + parts.slice(0, i + 1).join("/");
          const label = LABELS[part] ?? (part.length > 14 ? part.slice(0, 10) + "…" : part);
          return (
            <span
              key={href}
              className={cn("contents", !last && deep && "hidden md:contents")}
            >
              <BreadcrumbSeparator className={cn(!last && deep && "hidden md:inline-flex")} />
              <BreadcrumbItem className={cn(last && "min-w-0")}>
                {last || NOT_A_PAGE.has(part) ? (
                  <BreadcrumbPage
                    className={cn(
                      last ? "truncate font-medium text-foreground" : "text-muted-foreground",
                    )}
                  >
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
