import { apiResult, type BusinessPayload, type TeamPayload } from "@/app/lib";
import { completeProfile } from "@/lib/profile";
import { PageHeader } from "@/components/shell";
import { Wizard } from "./Wizard";

export const dynamic = "force-dynamic";

export default async function Onboarding() {
  const [biz, team] = await Promise.all([
    apiResult<BusinessPayload>("business"),
    apiResult<TeamPayload>("team"),
  ]);
  if (!biz.data) {
    return (
      <main className="w-full px-4 py-4 md:px-6 md:py-8">
        <PageHeader title="Describe your business" />
        <p className="text-muted-foreground mt-6 text-sm">{biz.error}</p>
      </main>
    );
  }
  const existing = biz.data.version != null && biz.data.profile.name;

  return (
    <main className="w-full max-w-5xl px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title={existing ? `Re-describe ${biz.data.profile.name}` : "Describe your business"}
        lead={existing
          ? "Change what the business sells, its limits or its team. Saving makes a new version; the team picks it up on its next task."
          : "Five short steps. At the end AERA forms a team of AI agents that runs this business within the limits you set."}
      />
      <Wizard
        initial={completeProfile(existing ? biz.data.profile : null)}
        example={biz.data.example}
        library={team.data?.library ?? []}
        mayChange={biz.data.may_change}
      />
    </main>
  );
}
