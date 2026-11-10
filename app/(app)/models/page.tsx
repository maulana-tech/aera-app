import { apiResult, type ModelsPayload } from "@/app/lib";
import { ModelChoice } from "./Choose";
import { PageHeader } from "@/components/shell";

export const dynamic = "force-dynamic";

export default async function ModelsPage() {
  const { data, error } = await apiResult<ModelsPayload>("models");

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Models" lead={<>
          Which model each agent thinks with. Kira&apos;s veto, Tara&apos;s figures and every origin
          label are code, not the model, so a cheaper model can make a recommendation worse but
          cannot make an action allowed. A change applies to the next model call, including the
          remaining rounds of a run already going.
        </>} />

      {data ? (
        <ModelChoice data={data} />
      ) : (
        <p className="text-muted-foreground mt-8 rounded-lg border border-dashed p-6 text-sm">
          {error ?? "The agent service did not answer."}
        </p>
      )}
    </main>
  );
}
