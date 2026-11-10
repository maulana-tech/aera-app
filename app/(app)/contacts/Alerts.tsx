"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { NotificationsPayload } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

const CHANNELS = [
  { key: "email", label: "Email", hint: "One message per contact below, with the report attached." },
  { key: "slack", label: "Slack", hint: "One message to the team's channel." },
  { key: "telegram", label: "Telegram", hint: "A person or a group the bot is in." },
  { key: "webhook", label: "Webhook", hint: "JSON, for Teams via Power Automate, n8n, a ticket queue." },
] as const;

const when = (t: string) =>
  new Date(t).toLocaleString("en-GB", {
    timeZone: "UTC", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });

export function Alerts({ data }: { data: NotificationsPayload }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [link, setLink] = useState("");
  const anyReady = Object.values(data.channels).some((c) => c.ready);

  async function connect() {
    setBusy(true);
    setError("");
    setResult("");
    setLink("");
    try {
      const res = await fetch("/api/aera/notifications/connect", { method: "POST" });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      // This used to window.open() the link here and say "sign in, then come
      // back". It does not work: by the time the fetch resolves the click is
      // over, so the browser treats the popup as unsolicited and blocks it -
      // and because window.open(..., "noopener") returns null whether it was
      // blocked or not, the code could not tell, and the only copy of the URL
      // was thrown away. The button went dead and the message lied about it.
      // So the link is rendered instead, and the second click opens it.
      setLink(d.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const res = await fetch("/api/aera/notifications/test", { method: "POST" });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      setResult(`${d.queued} queued · ${d.delivery}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-sm font-medium">Channels</h2>
        <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-relaxed">
          When a run finishes, is held, or fails, the people below whose kinds match are
          told, and so is every team channel that is set up. Every figure in the message comes
          from the record. Channels are set up in <span className="font-mono">.secrets/notify.env</span>{" "}
          on the server (ENV.md, Alerts).
        </p>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {CHANNELS.map((c) => {
          const s = data.channels[c.key];
          return (
            <li key={c.key} className="rounded-lg border px-4 py-3">
              <div className="flex items-center gap-2">
                <p className="text-sm">{c.label}</p>
                <StatusBadge status={s.ready ? "done" : "off"}>{s.ready ? "set up" : "not set up"}</StatusBadge>
              </div>
              <p className="text-muted-foreground mt-1 text-xs">{c.hint}</p>
              {c.key === "email" && s.via && (
                <p className="text-muted-foreground mt-1 text-xs">
                  {s.via === "composio" ? "Through Composio, from a Gmail mailbox" : "Over SMTP"}
                  {s.sender && <> · from <span className="font-mono">{s.sender}</span></>}
                </p>
              )}
              {!s.ready && (
                <p className="text-muted-foreground mt-1 break-words font-mono text-[10px]">
                  needs {s.missing.join(", ")}
                </p>
              )}
              {c.key === "email" && s.via === "composio" && s.connectable && data.may_change && (
                <div className="mt-2 space-y-2">
                  <Button type="button" variant="outline" size="sm"
                    disabled={busy} onClick={connect}>
                    {busy ? "Asking Composio…" : link ? "Get a fresh link" : "Connect Gmail"}
                  </Button>
                  {link && (
                    <p className="text-xs leading-relaxed">
                      <a href={link} target="_blank" rel="noopener noreferrer"
                        className="font-medium underline underline-offset-4">
                        Open the Google sign-in page
                      </a>
                      <span className="text-muted-foreground">
                        {" "}— whoever signs in there is the mailbox AERA sends from. Come back
                        and refresh this page afterwards. The link expires in a few minutes.
                      </span>
                    </p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {data.may_change && (
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" variant="outline" size="sm" disabled={busy || !anyReady} onClick={test}>
            {busy ? "Sending…" : "Send a test alert"}
          </Button>
          {!anyReady && <p className="text-muted-foreground text-xs">Set up a channel first.</p>}
          {result && <p className="text-muted-foreground text-xs">{result}</p>}
          {error && <p className="text-destructive text-xs">{error}</p>}
        </div>
      )}
    </section>
  );
}

/* What went out and to whom, newest first: alerts, reports sent by email and
 * approved messages to vendors and customers. */
export function RecentAlerts({ recent }: { recent: NotificationsPayload["recent"] }) {
  return (
    <section>
      <h2 className="text-sm font-medium">Recent alerts</h2>
      {recent.length === 0 ? (
        <p className="text-muted-foreground mt-2 rounded-lg border border-dashed p-4 text-sm">
          Nothing sent yet.
        </p>
      ) : (
        <ul className="mt-2 divide-y rounded-lg border">
          {recent.slice(0, 15).map((n) => (
            <li key={n.id} className="px-4 py-2.5">
              <div className="flex min-w-0 items-center gap-2">
                <StatusBadge status={n.status} />
                <p className="min-w-0 flex-1 truncate text-sm">{n.subject}</p>
              </div>
              <p className="text-muted-foreground mt-0.5 truncate font-mono text-[10px]">
                {n.kind === "outreach" ? "to a partner · " : ""}
                {n.channel}
                {n.channel === "email" && ` · ${n.address}`} · {when(n.created_at)} UTC
                {n.attempts > 1 && ` · ${n.attempts} attempts`}
                {n.attachments && n.attachments.length > 0 &&
                  ` · ${n.attachments.map((a) => a.format.toUpperCase()).join(" + ")} attached`}
              </p>
              {n.error && n.status !== "sent" && (
                <p className="text-muted-foreground mt-0.5 break-words text-[11px]">{n.error}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
