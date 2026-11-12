"use client";

import { CircleCheck, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { usd, type Checkout as CheckoutResult, type Offering, type PublicOrder } from "@/app/lib";
import { Field } from "@/components/profile-editor";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WalletSign } from "@/components/wallet-sign";
import { asNetwork, ftTransferCall } from "@/lib/near-wallet";
import { errorText, get, post } from "@/lib/post";

const STATUS_WORDS: Record<string, string> = {
  awaiting_payment: "Waiting for payment",
  paid: "Paid. The team has it and is starting.",
  working: "The team is working on it.",
  delivered: "Delivered. Check your email.",
  refunded: "Refunded.",
  failed: "Something went wrong; the business has been told and will be in touch.",
};

const STEPS = [
  { key: "awaiting_payment", label: "Ordered" },
  { key: "paid", label: "Paid" },
  { key: "working", label: "Team working" },
  { key: "delivered", label: "Delivered" },
] as const;
const stepIndex = (status: string) => {
  const i = STEPS.findIndex((s) => s.key === status);
  return i < 0 ? 0 : i;
};

function OrderStatus({ id }: { id: string }) {
  const [order, setOrder] = useState<PublicOrder | null>(null);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const o = await get<PublicOrder>(`public/orders/${id}`);
        if (!live) return;
        setOrder(o);
        if (o.status === "delivered" || o.status === "refunded" || o.status === "failed") return;
      } catch {
        // keep polling; a blip is not an answer
      }
      if (live) timer = setTimeout(tick, 4000);
    };
    tick();
    return () => { live = false; clearTimeout(timer); };
  }, [id]);

  const at = order ? stepIndex(order.status) : 0;
  const final = order && (order.status === "delivered" || order.status === "refunded" || order.status === "failed");
  return (
    <div className="rounded-lg border px-4 py-3" aria-live="polite">
      <div className="flex flex-wrap items-center gap-2">
        {final && order.status === "delivered"
          ? <CircleCheck className="size-4 text-ok " />
          : final ? null : <Loader2 className="text-muted-foreground size-4 animate-spin" aria-hidden />}
        <span className="text-sm">{order ? STATUS_WORDS[order.status] ?? order.status : "Checking the order…"}</span>
        {order && <StatusBadge status={order.status} />}
        <span className="text-muted-foreground ml-auto font-mono text-[11px]">{id}</span>
      </div>
      {order && order.status !== "refunded" && order.status !== "failed" && (
        <ol className="mt-3 grid grid-cols-4 gap-1">
          {STEPS.map((s, i) => (
            <li key={s.key} className="min-w-0">
              <span className={`block h-1 rounded-full ${i <= at ? "bg-primary" : "bg-muted"}`} />
              <span className={`mt-1 block truncate text-[11px] ${i <= at ? "text-foreground" : "text-muted-foreground"}`}>{s.label}</span>
            </li>
          ))}
        </ol>
      )}
      {!final && (
        <p className="text-muted-foreground mt-2 text-[11px]">This updates on its own. Keep the order number; you can close the page once it is paid.</p>
      )}
      {order && order.status !== "awaiting_payment" && (
        <a href={`/api/aera/public/orders/${id}/receipt.pdf`} download
          className="mt-2 inline-block text-xs underline underline-offset-2">Download your receipt (PDF)</a>
      )}
    </div>
  );
}

export function Checkout({ offering, network, open, prefill }: {
  offering: Offering; network: string; open: boolean;
  /** inputs Sales gathered in the chat above; the form starts from them */
  prefill?: Record<string, string>;
}) {
  const [inputs, setInputs] = useState<Record<string, string>>(
    Object.fromEntries(offering.inputs.map((k) => [k, prefill?.[k] ?? ""])));
  const [email, setEmail] = useState("");
  const [account, setAccount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CheckoutResult | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // A link from a published sample carries ?src=sample:<slug>, so the order is counted to it.
      const source = new URLSearchParams(window.location.search).get("src") ?? undefined;
      setResult(await post<CheckoutResult>("public/checkout", { offering: offering.id, inputs, email, account, source }));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    const ft = result.pay.ft_transfer_call;
    return (
      <div className="space-y-4">
        <div className="rounded-lg border p-4">
          <p className="text-sm">Order <span className="font-mono">{result.order.id}</span> for <span className="font-mono font-medium">{usd(result.pay.amount_usd)}</span>.</p>
          {ft ? (
            <div className="mt-4 space-y-2">
              <p className="text-muted-foreground text-xs leading-relaxed">
                Pay {usd(result.pay.amount_usd)} in USDC from your NEAR wallet. The payment goes to the business&apos;s
                vault contract <span className="font-mono">{ft.receiver_id}</span>, which records your order on chain.
              </p>
              <WalletSign variant="default" label="Pay with NEAR wallet" network={asNetwork(network)}
                call={ftTransferCall(result.pay.token, ft.receiver_id, ft.amount, ft.msg)} />
            </div>
          ) : (
            <p className="mt-3 rounded-md border border-border bg-raised px-3 py-2 text-xs text-warn ">
              SIMULATED payment: this business has no vault configured, so you pay nothing and no money moves. The owner marks
              the order paid from their dashboard, and the team starts on it then. The status below changes when they do.
            </p>
          )}
        </div>
        <OrderStatus id={result.order.id} />
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {offering.inputs.length > 0 && (
        <p className="text-muted-foreground text-xs">What the team needs from you to do the work. Plain words are fine.</p>
      )}
      {offering.inputs.map((k) => (
        <Field key={k} label={`${k.charAt(0).toUpperCase()}${k.slice(1).replace(/_/g, " ")} (required)`}>
          <Input value={inputs[k] ?? ""} required maxLength={500} onChange={(e) => setInputs({ ...inputs, [k]: e.target.value })} />
        </Field>
      ))}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Email (for delivery)" hint={offering.delivery === "service" ? "Where the business tells you it is done." : "Where the result is sent. Without one, watch the status on this page."}>
          <Input type="email" value={email} autoComplete="email" onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
        </Field>
        <Field label="NEAR account (optional)" hint={network === "mainnet" ? "The account you will pay from, e.g. you.near." : "The account you will pay from, e.g. you.testnet."}>
          <Input value={account} onChange={(e) => setAccount(e.target.value.trim())} placeholder={network === "mainnet" ? "you.near" : "you.testnet"} />
        </Field>
      </div>
      {error && <p className="text-sm text-bad ">{error}</p>}
      <Button type="submit" disabled={busy || !open}>
        {busy && <Loader2 className="animate-spin" />}
        Order for {usd(offering.price_usd)}
      </Button>
      {!open && <p className="text-muted-foreground text-xs">The business is not taking orders right now.</p>}
    </form>
  );
}
