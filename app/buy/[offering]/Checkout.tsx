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
  paid: "Paid. The team has it.",
  working: "The team is working on it.",
  delivered: "Delivered.",
  refunded: "Refunded.",
  failed: "Something went wrong; the business has been told.",
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

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border px-4 py-3">
      {order && order.status !== "awaiting_payment"
        ? <CircleCheck className="size-4 text-emerald-600" />
        : <Loader2 className="text-muted-foreground size-4 animate-spin" />}
      <span className="text-sm">{order ? STATUS_WORDS[order.status] ?? order.status : "Checking the order…"}</span>
      {order && <StatusBadge status={order.status} />}
      <span className="text-muted-foreground ml-auto font-mono text-[11px]">{id}</span>
    </div>
  );
}

export function Checkout({ offering, network, open }: { offering: Offering; network: string; open: boolean }) {
  const [inputs, setInputs] = useState<Record<string, string>>(Object.fromEntries(offering.inputs.map((k) => [k, ""])));
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
      setResult(await post<CheckoutResult>("public/checkout", { offering: offering.id, inputs, email, account }));
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
            <p className="mt-3 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
              Simulated payment: this business has no vault configured, so no money moves. The owner marks
              the order paid from their dashboard, and the team starts on it then.
            </p>
          )}
        </div>
        <OrderStatus id={result.order.id} />
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {offering.inputs.map((k) => (
        <Field key={k} label={k.replace(/_/g, " ")}>
          <Input value={inputs[k] ?? ""} required maxLength={500} onChange={(e) => setInputs({ ...inputs, [k]: e.target.value })} />
        </Field>
      ))}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Email (for delivery)"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></Field>
        <Field label="NEAR account (optional)"><Input value={account} onChange={(e) => setAccount(e.target.value.trim())} placeholder="you.testnet" /></Field>
      </div>
      {error && <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>}
      <Button type="submit" disabled={busy || !open}>
        {busy && <Loader2 className="animate-spin" />}
        Order for {usd(offering.price_usd)}
      </Button>
      {!open && <p className="text-muted-foreground text-xs">The business is not taking orders right now.</p>}
    </form>
  );
}
