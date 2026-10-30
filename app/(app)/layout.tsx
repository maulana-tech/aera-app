import { AppSidebar } from "@/components/app-sidebar";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { NotificationToast } from "@/components/notification-toast";
import { ThemeToggle } from "@/components/theme";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { api, me } from "@/app/lib";
import { redirect } from "next/navigation";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // `mode` is a separate read because /health is public: whether you may
  // CHANGE the data source depends on who you are, and that belongs behind
  // the session, not in an unauthenticated payload.
  const [user, health, mode] = await Promise.all([
    me(),
    api<{
      env: string; sap_ready: boolean; model_ready: boolean;
      data_mode?: "live" | "demo"; sap_key_set?: boolean;
    }>("health"),
    api<{ mode: "live" | "demo"; may_change: boolean }>("mode"),
  ]);
  // Every route but /health needs a session now, so a page without one shows
  // nothing but errors. When the service answers and says who you are not,
  // the login page is the only useful thing to show. When it does not answer
  // at all, stay: the pages say the service is down, which is the real news.
  if (health && !user) redirect("/login");

  return (
    <SidebarProvider>
      <AppSidebar
        user={user ?? undefined}
        connection={health ?? undefined}
        mayChangeMode={!!mode?.may_change}
      />
      <SidebarInset>
        <header className="bg-background/80 sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-3 backdrop-blur md:px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <div className="min-w-0 flex-1">
            <Breadcrumbs />
          </div>
          <div className="ml-auto shrink-0">
            <ThemeToggle />
          </div>
        </header>
        {children}
      </SidebarInset>
      <NotificationToast />
    </SidebarProvider>
  );
}
