import { api, apiResult, mayManage, me, type Contact, type NotificationsPayload } from "@/app/lib";
import { PageHeader } from "@/components/shell";
import { Alerts, RecentAlerts } from "./Alerts";
import { AddContact, ContactList } from "./Manage";

export const dynamic = "force-dynamic";

export default async function ContactsPage() {
  const [d, alerts, user] = await Promise.all([
    api<{ contacts: Contact[] }>("contacts"),
    apiResult<NotificationsPayload>("notifications"),
    me(),
  ]);
  const mayChange = alerts.data?.may_change ?? false;
  const payoutEditable = mayManage(user);

  return (
    <main className="w-full px-4 py-4 md:px-6 md:py-8">
      <PageHeader
        title="Contacts"
        lead="The people and accounts the business deals with: customers, vendors, contributors,
              the team and approvers. A vendor's payout account lives here and only here; the team
              pays what is on record, never an address from a message."
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
              Contacts ({d?.contacts.length ?? 0})
            </h2>
            <ContactList contacts={d?.contacts ?? []} canDelete={mayChange} payoutEditable={payoutEditable} />
          </section>
        </div>
        <div className="min-w-0 space-y-10">
          {mayChange ? (
            <AddContact payoutEditable={payoutEditable} />
          ) : (
            <p className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Only an owner or admin can add or change a contact: a contact may be paid, and may
              receive what was decided and what it is worth.
            </p>
          )}
          {alerts.data && <RecentAlerts recent={alerts.data.recent} />}
        </div>
      </div>
    </main>
  );
}
