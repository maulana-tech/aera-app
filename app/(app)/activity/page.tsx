import { api, apiResult, type ActivityPayload, type Health } from "@/app/lib";
import { PageHeader } from "@/components/shell";
import { TeamLive } from "@/components/team-live";

export const dynamic = "force-dynamic";

/* Everything the team did, in plain words, newest first, each line linking to its evidence. */
export default async function ActivityPage() {
  const [res, health] = await Promise.all([apiResult<ActivityPayload>("activity?limit=100"), api<Health>("health")]);
  return (
    <main className="w-full max-w-5xl px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Activity"
        lead="What the team is doing right now and everything it did, without asking it: orders that came in, who took on which task, what was written and delivered, money in and out, and what the Guardian stopped. Read from the record; nothing here is written by a model."
      />
      <div className="mt-8">
        {res.data
          ? <TeamLive initial={res.data} network={health?.network ?? "testnet"} limit={100} />
          : <p className="text-muted-foreground text-sm">{res.error}</p>}
      </div>
    </main>
  );
}
