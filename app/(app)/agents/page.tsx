import { apiResult, type TeamPayload } from "@/app/lib";
import { PageHeader } from "@/components/shell";
import { TeamBoard } from "./TeamBoard";

export const dynamic = "force-dynamic";

export default async function TeamPage() {
  const team = await apiResult<TeamPayload>("team");

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Team"
        lead="Composed from the business profile. Supervisor receives every piece of work and delegates; specialists never call each other. Guardian rules on anything that leaves the business and its block is final. Treasurer is the only one who can touch the vault. Those three locks are in code, not in a prompt."
      />
      {team.data ? (
        <TeamBoard data={team.data} />
      ) : (
        <p className="text-muted-foreground mt-6 text-sm">{team.error}</p>
      )}
    </main>
  );
}
