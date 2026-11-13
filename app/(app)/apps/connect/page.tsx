import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { apiResult, type AppsPayload } from "@/app/lib";
import { Empty, PageHeader } from "@/components/shell";
import { Catalogue } from "./Catalogue";

export const dynamic = "force-dynamic";

export default async function ConnectPage() {
  const res = await apiResult<AppsPayload>("apps");
  const d = res.data;
  const added = new Set((d?.apps ?? []).map((a) => a.toolkit));
  const ready = [...new Set((d?.connections ?? []).map((c) => c.toolkit))].filter((t) => !added.has(t));
  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Connect a tool"
        lead={<>
          Every app Composio can connect, most used first. Connect one with its own sign-in, and it is added to AERA
          straight away; then choose which agents may use which of its tools under{" "}
          <Link href="/apps" className="text-brand underline-offset-2 hover:underline">Apps</Link>.
          What an agent reads there is labelled as outside data; anything that would change something waits for you.
        </>}
        aside={<Link href="/apps" className="text-muted-foreground hover:text-fg inline-flex items-center gap-1 text-[13px]"><ArrowLeft className="size-3.5" /> Your apps</Link>} />
      {!d ? (
        <p className="text-muted-foreground mt-8 rounded-lg border border-dashed p-6 text-sm">{res.error}</p>
      ) : !d.configured ? (
        <div className="mt-8">
          <Empty what="Composio is not set up on this business"
            why="Tools are connected through a Composio project. Its API key goes in aera/agent/.secrets/notify.env as COMPOSIO_API_KEY; restart the agent service and the catalogue appears here."
            fix="COMPOSIO_API_KEY=ak_..." />
        </div>
      ) : (
        <Catalogue mayChange={d.may_change} ready={ready} added={[...added]} />
      )}
    </main>
  );
}
