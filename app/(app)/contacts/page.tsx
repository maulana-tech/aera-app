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
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Contacts</h1>
        <p className="text-muted-foreground mt-1 max-w-3xl text-sm leading-relaxed">
          Who Bram reaches when a disruption hits. This product works off events. The
          recommendation has to come to people, not wait to be opened.
        </p>
      </header>

      <div className="mt-8 max-w-3xl space-y-10">
        {user ? (
          <AddContact />
        ) : (
          <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
            Sign in to add a contact.
          </p>
        )}
        <section>
          <h2 className="text-sm font-medium">
            Recipients ({d?.contacts.length ?? 0})
          </h2>
          <ContactList contacts={d?.contacts ?? []} canDelete={!!user} />
          <p className="text-muted-foreground mt-3 max-w-xl text-xs leading-relaxed">
            Email delivery is not wired up yet. This list is what will be used once a mail
            service is connected.
          </p>
        </section>
      </div>
    </main>
  );
}
