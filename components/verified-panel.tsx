"use client";

import { CircleCheck, CircleMinus, CircleX, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { bareModel, when, type Attestation, type Proof, type ProofCheck } from "@/app/lib";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { errorText, get } from "@/lib/post";
import { cn } from "@/lib/utils";

const VERDICT_TONE: Record<string, string> = {
  attested: "done",
  partial: "held",
  pending: "pending",
  failed: "failed",
};

function CheckIcon({ status }: { status: string }) {
  if (status === "pass") return <CircleCheck className="size-3.5 shrink-0 text-ok " aria-label="pass" />;
  if (status === "fail") return <CircleX className="size-3.5 shrink-0 text-bad " aria-label="fail" />;
  return <CircleMinus className="text-muted-foreground size-3.5 shrink-0" aria-label={status} />;
}

/** Each check, with what it established or why it could not. */
export function CheckList({ checks }: { checks: ProofCheck[] }) {
  if (!checks.length) {
    return <p className="text-muted-foreground text-xs">No checks recorded yet: the attest worker has not reached this call.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {checks.map((c, i) => (
        <li key={`${c.name}-${c.scope ?? ""}-${i}`} className="flex items-start gap-2">
          <CheckIcon status={c.status} />
          <div className="min-w-0 flex-1">
            <p className="font-mono text-[11px]">
              {c.name}
              <span className={cn("ml-1.5", c.status === "fail" ? "text-bad " : "text-muted-foreground")}>
                {c.status}
              </span>
              {c.scope && <span className="text-muted-foreground ml-1.5">· {c.scope}</span>}
            </p>
            <p className="text-muted-foreground text-[11px] leading-relaxed break-words">{c.detail}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function VerifyAgain({ model }: { model: string }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Attestation | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await get<Attestation>(`attestation/${bareModel(model)}`));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <Button size="sm" variant="outline" onClick={run} disabled={busy}>
        {busy ? <Loader2 className="animate-spin" /> : <RefreshCw />}
        Verify again
      </Button>
      {error && <p className="text-xs text-bad ">{error}</p>}
      {result && (
        <div className="rounded-md border p-3">
          {result.error !== undefined ? (
            <p className="text-xs text-bad ">{result.error}</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={result.verdict === "attested" ? "done" : result.verdict === "partial" ? "held" : "failed"}>
                  {result.verdict}
                </StatusBadge>
                <span className="text-muted-foreground text-[11px]">live report for {result.model}, fresh nonce:</span>
              </div>
              <p className="mt-1.5 font-mono text-[10px] break-all">{result.nonce}</p>
              <div className="mt-3"><CheckList checks={result.checks} /></div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** Proof that each model call ran inside an attested TEE on NEAR AI Cloud:
 *  per call, who asked, which model answered, and every check behind the
 *  verdict. "Verify again" fetches a new report with a nonce made now, so the
 *  proof is not something the page asks you to take on trust. */
export function VerifiedPanel({ proofs, names = {} }: { proofs: Proof[]; names?: Record<string, string> }) {
  const [open, setOpen] = useState<string | null>(proofs[0]?.id ?? null);
  const models = [...new Set(proofs.map((p) => p.model))];
  const attested = proofs.filter((p) => p.verdict === "attested").length;

  return (
    <div className="rounded-lg border">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
        <p className="inline-flex items-center gap-2 text-sm font-medium">
          <ShieldCheck className="size-4" />
          Verified
        </p>
        <span className="text-muted-foreground font-mono text-[11px]">
          {attested}/{proofs.length} model calls attested
        </span>
      </div>

      {proofs.length === 0 ? (
        <p className="text-muted-foreground px-4 py-4 text-xs leading-relaxed">
          No model call has a proof on record for this run. A run that was held before the team
          reasoned made no model call; one on a model that is not TEE-attested has nothing to prove.
        </p>
      ) : (
        <ul className="divide-y">
          {proofs.map((p) => {
            const isOpen = open === p.id;
            return (
              <li key={p.id}>
                <button type="button" onClick={() => setOpen(isOpen ? null : p.id)} aria-expanded={isOpen}
                  className="hover:bg-muted/40 flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-left">
                  <StatusBadge status={VERDICT_TONE[p.verdict] ?? "off"}>{p.verdict}</StatusBadge>
                  <span className="text-sm">{names[p.agent] ?? p.agent}</span>
                  <span className="text-muted-foreground min-w-0 truncate font-mono text-[11px]">{p.model}</span>
                  <span className="text-muted-foreground ml-auto font-mono text-[10px]">
                    {p.step_seq != null && `step ${p.step_seq} · `}{when(p.created_at, { seconds: true })}
                  </span>
                </button>
                {isOpen && (
                  <div className="space-y-3 px-4 pb-4">
                    <CheckList checks={p.checks} />
                    <dl className="text-muted-foreground grid gap-x-4 gap-y-1 font-mono text-[10px] sm:grid-cols-[auto_1fr]">
                      <dt>chat id</dt><dd className="break-all">{p.chat_id}</dd>
                      {p.signing_address && (<><dt>signed by</dt><dd className="break-all">{p.signing_address}</dd></>)}
                      {p.req_sha256 && (<><dt>sha256(request)</dt><dd className="break-all">{p.req_sha256}</dd></>)}
                      {p.resp_sha256 && (<><dt>sha256(response)</dt><dd className="break-all">{p.resp_sha256}</dd></>)}
                    </dl>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {models.length > 0 && (
        <div className="space-y-4 border-t px-4 py-3">
          {models.map((m) => (
            <div key={m}>
              <p className="text-muted-foreground mb-2 font-mono text-[11px]">{m}</p>
              <VerifyAgain model={m} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
