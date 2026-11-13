import { api, apiResult, type AppsPayload, type TeamPayload } from "@/app/lib";
import { Empty, PageHeader } from "@/components/shell";
import { AppsManager } from "./AppsManager";

export const dynamic = "force-dynamic";

export default async function AppsPage() {
  const [res, team] = await Promise.all([apiResult<AppsPayload>("apps"), api<TeamPayload>("team")]);
  const agents = (team?.agents ?? []).filter((a) => a.status === "active" && a.code !== "guardian" && a.code !== "treasurer")
    .map((a) => ({ code: a.code, nickname: a.nickname }));
  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Apps" lead={<>
        Connect the apps your business already uses (Slack, Google Sheets, Notion, Calendar, HubSpot and hundreds more)
        through Composio, then choose which agents may use which of their tools. Reads run and are labelled as outside
        data; anything that would change something in an app becomes an action the Guardian checks and you approve.
      </>} />
      {!res.data ? (
        <p className="text-muted-foreground mt-8 rounded-lg border border-dashed p-6 text-sm">{res.error}</p>
      ) : !res.data.configured ? (
        <div className="mt-8">
          <Empty what="Composio is not set up on this business"
            why="Apps are connected through a Composio project. Its API key goes in aera/agent/.secrets/notify.env as COMPOSIO_API_KEY; restart the agent service and this page lists what you can connect."
            fix="COMPOSIO_API_KEY=ak_..." />
        </div>
      ) : (
        <AppsManager data={res.data} agents={agents} />
      )}
    </main>
  );
}
