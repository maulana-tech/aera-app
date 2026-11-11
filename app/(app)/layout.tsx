import { AppSidebar } from "@/components/app-sidebar";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { NotificationToast } from "@/components/notification-toast";
import { ThemeToggle } from "@/components/theme";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import Link from "next/link";

import { api, me, noBusiness, type BusinessPayload, type Health } from "@/app/lib";
import { redirect } from "next/navigation";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [user, health] = await Promise.all([me(), api<Health>("health")]);
  // Every route but /health needs a session now, so a page without one shows
  // nothing but errors. When the service answers and says who you are not,
  // the login page is the only useful thing to show. When it does not answer
  // at all, stay: the pages say the service is down, which is the real news.
  if (health && !user) redirect("/login");
  const biz = user ? await api<BusinessPayload>("business") : null;
  // A business not yet described reads as switched off; that is not news.
  const stopped = !noBusiness(biz) && !!biz?.profile.kill_switch;

  return (
    <SidebarProvider>
      <AppSidebar
        user={user ?? undefined}
        connection={health ?? undefined}
      />
      <SidebarInset>
        <header className="bg-background/80 sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b px-3 backdrop-blur md:px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <div className="min-w-0 flex-1">
            <Breadcrumbs />
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            {stopped && (
              <Link href="/business" title="The kill switch is on: nothing is sent and no money moves" className="rounded-full bg-rose-600 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-white">
                STOPPED
              </Link>
            )}
            <ThemeToggle />
          </div>
        </header>
        {health && !health.model_ready && (
          <div className="border-b border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-900 md:px-6 dark:text-amber-200">
            The team cannot think yet: the supervisor&apos;s model ({health.model}) cannot be called. Work is recorded and
            held. Add <span className="font-mono">NEARAI_API_KEY</span> to <span className="font-mono">aera/agent/.secrets/near.env</span>,
            restart the agent service, then use <span className="font-medium">Run again</span> on held work.
          </div>
        )}
        {children}
      </SidebarInset>
      <NotificationToast />
    </SidebarProvider>
  );
}
