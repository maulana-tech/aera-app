"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { ScheduledJob, SchedulePayload } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";

const wib = (t: string | null) =>
  t
    ? new Date(t).toLocaleString("en-GB", {
        timeZone: "UTC", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
      }) + " UTC"
    : "never";

function state(j: ScheduledJob): { status: string; label: string } {
  if (j.running) return { status: "running", label: "running" };
  if (j.off) return { status: "off", label: j.off === "switched off" ? "off" : `off · ${j.off}` };
  if (j.last_status) return { status: j.last_status, label: j.last_status };
  return { status: "pending", label: "not run yet" };
}

export function JobList({ data }: { data: SchedulePayload }) {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function post(path: string, body?: object) {
    setBusy(path);
    setError("");
    try {
      const res = await fetch(`/api/aera/schedule/${path}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body ?? {}),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error ?? "failed");
      // A job started by hand finishes on its own time; give it a moment.
      if (path.endsWith("/run")) await new Promise((r) => setTimeout(r, 1500));
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="mt-8 space-y-6">
      {(!data.enabled || !data.watch) && (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          {!data.enabled
            ? "Nothing runs on its own here: AERA_SCHEDULE=0. A job can still be run by hand."
            : "The watchers are off here (AERA_WATCH=0), so no feed raises an event on its own. Alerts, the sender and the digest still run."}
        </p>
      )}
      {!data.may_change && (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          Only an admin or a procurement lead can run or switch a job.
        </p>
      )}

      <ul className="divide-y rounded-lg border">
        {data.jobs.map((j) => {
          const s = state(j);
          return (
            <li key={j.name} className="grid gap-3 px-4 py-4 md:grid-cols-[1fr_auto] md:items-start">
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium">{j.what}</p>
                  <StatusBadge status={s.status}>{s.label}</StatusBadge>
                </div>
                <p className="text-muted-foreground font-mono text-[11px]">
                  {j.name} · {j.cadence}
                  {j.signal && " · raises events"}
                </p>
                <p className="text-muted-foreground font-mono text-[11px]">
                  last {wib(j.last_started)}
                  {j.next_at && ` · next ${wib(j.next_at)}`}
                  {j.runs > 0 && ` · ${j.runs} run${j.runs > 1 ? "s" : ""}`}
                  {j.failures > 0 && `, ${j.failures} failed`}
                </p>
                {j.last_detail && (
                  <p className={`text-xs break-words ${j.last_status === "failed" ? "text-destructive" : "text-muted-foreground"}`}>
                    {j.last_detail}
                  </p>
                )}
              </div>
              {data.may_change && (
                <div className="flex shrink-0 gap-2">
                  <Button
                    type="button" variant="outline" size="sm" disabled={busy !== "" || j.running}
                    onClick={() => post(`${j.name}/run`)}
                  >
                    {busy === `${j.name}/run` ? "Starting…" : "Run now"}
                  </Button>
                  <Button
                    type="button" variant="ghost" size="sm" disabled={busy !== ""}
                    onClick={() => post(`${j.name}/enabled`, { enabled: !j.enabled })}
                  >
                    {j.enabled ? "Switch off" : "Switch on"}
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {error && <p className="text-destructive text-xs">{error}</p>}
    </div>
  );
}
