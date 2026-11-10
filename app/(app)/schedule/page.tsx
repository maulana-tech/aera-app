import { apiResult, type SchedulePayload } from "@/app/lib";
import { JobList } from "./Jobs";
import { PageHeader } from "@/components/shell";

export const dynamic = "force-dynamic";

export default async function SchedulePage() {
  const { data, error } = await apiResult<SchedulePayload>("schedule");

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Schedule" lead={<>
          What AERA does on its own: hands new work to the team, settles payments with the vault,
          verifies TEE attestation proofs, delivers alerts and sends the morning digest. A job that
          starts work spends model credit. Times are UTC.
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
