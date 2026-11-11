import { redirect } from "next/navigation";

import { api, me, noBusiness, type BusinessPayload, type Health } from "@/app/lib";
import { Dot } from "@/components/dort";
import { NotificationToast } from "@/components/notification-toast";
import { TopNav } from "@/components/top-nav";

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
    <div className="flex min-h-dvh flex-col">
      <TopNav user={user ?? undefined} connection={health ?? undefined} stopped={stopped} />
      <div className="flex flex-1 flex-col px-2 pb-3 md:px-4 md:pb-4">
        <div className="bg-card-grad flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-white/40 shadow-float">
          {health && !health.model_ready && (
            <div className="bg-raised text-body flex items-start gap-2.5 border-b px-4 py-2.5 text-[12.5px] leading-relaxed md:px-6">
              <Dot tone="warn" className="mt-[7px]" />
              <p>
                The team cannot think yet: the supervisor&apos;s model (<span className="font-mono">{health.model}</span>) cannot be
                called. Work is recorded and held. Add <span className="font-mono">NEARAI_API_KEY</span> to{" "}
                <span className="font-mono">aera/agent/.secrets/near.env</span>, restart the agent service, then use{" "}
                <span className="text-fg font-medium">Run again</span> on held work.
              </p>
            </div>
          )}
          {children}
        </div>
      </div>
      <NotificationToast />
    </div>
  );
}
