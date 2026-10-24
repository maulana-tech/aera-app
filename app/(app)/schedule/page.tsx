import { apiResult, type SchedulePayload } from "@/app/lib";
import { JobList } from "./Jobs";
import { PageHeader } from "@/components/shell";

export const dynamic = "force-dynamic";

export default async function SchedulePage() {
  const { data, error } = await apiResult<SchedulePayload>("schedule");

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Schedule" lead={<>
          What SIGAP does on its own. The watchers raise an event when something lands near a
          port or a plant, and an event starts a handling that spends model credit. The outbox
          delivers alerts, the sender moves approved actions into SAP, and the digest goes out
          every morning. Times are Jakarta time (WIB).
        </>} />

      {data ? (
        <JobList data={data} />
      ) : (
        <p className="text-muted-foreground mt-8 rounded-lg border border-dashed p-6 text-sm">
          {error ?? "The agent service did not answer."}
        </p>
      )}
    </main>
  );
}
