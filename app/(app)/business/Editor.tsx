"use client";

import { Loader2, Pencil } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Profile, TeamDiff } from "@/app/lib";
import {
  BasicsFields, Field, LimitsFields, OfferingsFields, Problems,
} from "@/components/profile-editor";
import { DiffView } from "@/components/team-list";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorText, post } from "@/lib/post";

/** Edit the profile in force. Saving writes a new version; the team is NOT
 *  changed silently: the Composer's proposal comes back as a diff, and a
 *  person applies it here or on the Team page. */
export function Editor({ profile }: { profile: Profile }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [p, setP] = useState<Profile>(profile);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ version: number; problems: string[]; team_diff: TeamDiff; team_applied: boolean } | null>(null);
  const [applying, setApplying] = useState(false);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const r = await post<{ version: number; problems: string[]; team_diff: TeamDiff; team_applied: boolean }>(
        "business", { profile: p, note });
      setSaved(r);
      router.refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function applyTeam() {
    setApplying(true);
    setError(null);
    try {
      await post("team/apply", {});
      setSaved(saved && { ...saved, team_applied: true });
      router.refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setApplying(false);
    }
  }

  if (!open) {
    return (
      <Button variant="outline" size="sm" onClick={() => { setP(profile); setOpen(true); setSaved(null); }}>
        <Pencil /> Edit the profile
      </Button>
    );
  }

  return (
    <div className="space-y-10 rounded-lg border p-4 md:p-6">
      <section>
        <h3 className="mb-4 text-sm font-medium">The business</h3>
        <BasicsFields p={p} set={setP} />
      </section>
      <section>
        <h3 className="mb-4 text-sm font-medium">Offerings</h3>
        <OfferingsFields p={p} set={setP} />
      </section>
      <section>
        <h3 className="mb-4 text-sm font-medium">Limits and rules</h3>
        <LimitsFields p={p} set={setP} />
      </section>

      <div className="space-y-3 border-t pt-4">
        <Field label="What changed, for the version history (optional)">
          <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
        </Field>
        <div className="flex flex-wrap gap-2">
          <Button onClick={save} disabled={busy || !p.name.trim()}>
            {busy && <Loader2 className="animate-spin" />}
            Save a new version
          </Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>Close</Button>
        </div>
        {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
      </div>

      {saved && (
        <div className="space-y-4 border-t pt-4">
          <p className="text-sm">Saved as version <span className="font-mono">{saved.version}</span>.</p>
          <Problems problems={saved.problems} />
          <h4 className="text-sm font-medium">What the Composer proposes for the team</h4>
          <DiffView diff={saved.team_diff} />
          {saved.team_applied ? (
            <p className="text-muted-foreground text-xs">Applied. <Link href="/agents" className="underline">See the team</Link>.</p>
          ) : (saved.team_diff.add.length + saved.team_diff.remove.length + saved.team_diff.change.length) > 0 && (
            <Button size="sm" onClick={applyTeam} disabled={applying}>
              {applying && <Loader2 className="animate-spin" />}
              Apply this team change
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
