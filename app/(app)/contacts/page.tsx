import { api, apiResult, type Contact, type NotificationsPayload } from "@/app/lib";
import { PageHeader } from "@/components/shell";
import { Alerts, RecentAlerts } from "./Alerts";
import { AddContact, ContactList } from "./Manage";

export const dynamic = "force-dynamic";

export default async function ContactsPage() {
  const [d, alerts] = await Promise.all([
    api<{ contacts: Contact[] }>("contacts"),
    apiResult<NotificationsPayload>("notifications"),
  ]);
  const mayChange = alerts.data?.may_change ?? false;

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Contacts"
        lead="Who is told when a disruption hits. This product works off events. The
              recommendation has to come to people, not wait to be opened."
      />

      <div className="mt-8 grid gap-10 xl:grid-cols-2 xl:gap-12">
        <div className="min-w-0 space-y-10">
          {alerts.data ? (
            <Alerts data={alerts.data} />
          ) : (
            <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              {alerts.error ?? "The agent service did not answer."}
            </p>
          )}
          <section>
            <h2 className="text-sm font-medium">
              Recipients ({d?.contacts.length ?? 0})
            </h2>
            <ContactList contacts={d?.contacts ?? []} canDelete={mayChange} />
          </section>
        </div>
        <div className="min-w-0 space-y-10">
          {mayChange ? (
            <AddContact />
          ) : (
            <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Only an admin or a procurement lead can add or remove a contact: a contact receives
              what was decided and what it is worth.
            </p>
          )}
          {alerts.data && <RecentAlerts recent={alerts.data.recent} />}
        </div>
      </div>
    </main>
  );
}
