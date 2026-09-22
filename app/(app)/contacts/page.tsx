import { api, me, type Contact } from "@/app/lib";
import { AddContact, ContactList } from "./Manage";

export const dynamic = "force-dynamic";

export default async function ContactsPage() {
  const [d, user] = await Promise.all([
    api<{ contacts: Contact[] }>("contacts"),
    me(),
  ]);

  return (
    <main className="w-full px-6 py-8">
      <header className="border-b pb-5">
        <p className="text-muted-foreground font-mono text-xs uppercase tracking-[0.18em]">
          SIGAP · Settings
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Contacts</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Who Bram reaches when a disruption hits. This product works off events — the
          recommendation has to come to people, not wait to be opened.
        </p>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        {user ? (
          <AddContact />
        ) : (
          <p className="text-muted-foreground rounded-xl border border-dashed p-6 text-sm">
            Sign in to add a contact.
          </p>
        )}
        <aside>
          <h2 className="text-muted-foreground font-mono text-[11px] uppercase tracking-[0.15em]">
            Recipients · {d?.contacts.length ?? 0}
          </h2>
          <ContactList contacts={d?.contacts ?? []} canDelete={!!user} />
          <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
            Email delivery is not wired up yet. This list is what will be used once a mail
            service is connected.
          </p>
        </aside>
      </div>
    </main>
  );
}
