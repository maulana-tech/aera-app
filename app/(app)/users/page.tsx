import { apiResult, me, mayManage, usd, when } from "@/app/lib";
import { PageHeader, Section } from "@/components/shell";
import { AddUser, RemoveUser, ROLE_HELP } from "./Users";

export const dynamic = "force-dynamic";

type UsersPayload = {
  users: { id: string; email: string; name: string; role: string; created_at: string; limit_usd: number }[];
  roles: Record<string, number>;
  may_change: boolean;
};

export default async function Users() {
  const [res, user] = await Promise.all([apiResult<UsersPayload>("users"), me()]);
  const data = res.data;
  const owner = mayManage(user);
  const users = data?.users ?? [];
  const alone = users.length <= 1;
  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader title="Accounts"
        lead="Who can sign in, and how much each may approve. Limits are checked by the agent service from the session, never from the page. Add at least one approver, so a payment above the team's limit has someone other than the owner to sign it." />
      {!data && <p className="text-muted-foreground mt-6 text-sm">{res.error}</p>}
      <Section title="Roles" note="Anything above a person's limit waits for someone with a higher one.">
        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {Object.entries(data?.roles ?? {}).map(([r, limit]) => (
            <div key={r} className="rounded-lg border px-3 py-2">
              <p className="text-sm font-medium capitalize">{r}</p>
              <p className="text-muted-foreground font-mono text-[11px]">{limit ? `approves up to ${usd(limit)}` : "approves nothing"}</p>
              {ROLE_HELP[r] && <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{ROLE_HELP[r]}</p>}
            </div>
          ))}
        </div>
      </Section>
      <Section title={`Accounts (${users.length})`}
        note={alone ? (owner ? "Only you so far. Add an approver below." : "Ask the owner to add the people who decide.") : undefined}>
        <div className="divide-y rounded-lg border">
          {users.map((u) => (
            <div key={u.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{u.name} <span className="text-muted-foreground font-normal">{u.email}</span>
                  {u.email === user?.email && <span className="text-muted-foreground ml-1.5 text-xs font-normal">(you)</span>}</p>
                <p className="text-muted-foreground text-xs"><span className="capitalize">{u.role}</span> · {u.limit_usd ? `approves up to ${usd(u.limit_usd)}` : "approves nothing"}{u.created_at ? ` · added ${when(u.created_at, { time: false })}` : ""}</p>
              </div>
              {owner && u.email !== user?.email && <RemoveUser id={u.id} name={u.name} />}
            </div>
          ))}
        </div>
      </Section>
      {owner ? (
        <Section title="Add an account">
          <AddUser roles={Object.keys(data?.roles ?? {})} />
        </Section>
      ) : (
        <p className="text-muted-foreground mt-8 text-xs">Only an owner or admin adds or removes accounts.</p>
      )}
    </main>
  );
}
