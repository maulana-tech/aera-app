import { api, me, mayManage, usd } from "@/app/lib";
import { PageHeader, Section } from "@/components/shell";
import { AddUser, RemoveUser } from "./Users";

export const dynamic = "force-dynamic";

type UsersPayload = {
  users: { id: string; email: string; name: string; role: string; created_at: string; limit_usd: number }[];
  roles: Record<string, number>;
  may_change: boolean;
};

export default async function Users() {
  const [data, user] = await Promise.all([api<UsersPayload>("users"), me()]);
  const owner = mayManage(user);
  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Accounts"
        lead="Who can sign in, and how much each may approve. Approval limits are checked by the agent service from the session, never from the page." />
      <Section title="Roles">
        <div className="grid gap-2 sm:grid-cols-5">
          {Object.entries(data?.roles ?? {}).map(([r, limit]) => (
            <div key={r} className="rounded-lg border px-3 py-2">
              <p className="text-sm font-medium capitalize">{r}</p>
              <p className="text-muted-foreground text-xs">{limit ? `approves up to ${usd(limit)}` : "approves nothing"}</p>
            </div>
          ))}
        </div>
      </Section>
      <Section title={`Accounts (${data?.users.length ?? 0})`}>
        <div className="divide-y rounded-lg border">
          {(data?.users ?? []).map((u) => (
            <div key={u.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{u.name} <span className="text-muted-foreground font-normal">{u.email}</span></p>
                <p className="text-muted-foreground text-xs capitalize">{u.role} · up to {usd(u.limit_usd)}</p>
              </div>
              {owner && u.email !== user?.email && <RemoveUser id={u.id} />}
            </div>
          ))}
        </div>
      </Section>
      {owner && (
        <Section title="Add an account">
          <AddUser roles={Object.keys(data?.roles ?? {})} />
        </Section>
      )}
    </main>
  );
}
