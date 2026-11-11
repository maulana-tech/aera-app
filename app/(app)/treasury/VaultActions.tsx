"use client";

import { Loader2, LogOut, Wallet } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { WalletSign } from "@/components/wallet-sign";
import {
  asNetwork, connectWallet, connectedAccount, disconnectWallet, vault,
} from "@/lib/near-wallet";
import { errorText } from "@/lib/post";

/** Which wallet is connected, so an approver can see who will sign. */
export function WalletStatus({ network }: { network: string }) {
  const net = asNetwork(network);
  const [account, setAccount] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    connectedAccount(net).then((a) => live && setAccount(a));
    return () => { live = false; };
  }, [net]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      {account ? (
        <>
          <span className="font-mono text-xs">{account}</span>
          <Button size="xs" variant="ghost" onClick={async () => { await disconnectWallet(net).catch(() => {}); setAccount(null); }}>
            <LogOut /> Disconnect
          </Button>
        </>
      ) : (
        <Button size="sm" variant="outline" disabled={busy} onClick={async () => {
          setBusy(true);
          setError(null);
          try { setAccount(await connectWallet(net)); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
        }}>
          {busy ? <Loader2 className="animate-spin" /> : <Wallet />}
          Connect a NEAR wallet ({net})
        </Button>
      )}
      {error && <span className="text-[11px] text-amber-700 dark:text-amber-400">{error}</span>}
    </div>
  );
}

export function ApproveOnChain({ contract, network, requestId }: { contract: string; network: string; requestId: string }) {
  const net = asNetwork(network);
  const [reason, setReason] = useState("");
  return (
    <div className="space-y-2">
      <WalletSign call={vault.approve(contract, requestId)} network={net} label="Approve in wallet" variant="default" />
      <div className="flex flex-wrap items-start gap-2">
        <Input className="max-w-64" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason to reject" />
        <WalletSign call={vault.reject(contract, requestId, reason || "rejected by an approver")} network={net} label="Reject in wallet" />
      </div>
    </div>
  );
}

export function RefundOnChain({ contract, network, orderId, amountBase }: {
  contract: string; network: string; orderId: string; amountBase: string;
}) {
  return <WalletSign call={vault.refund(contract, orderId, amountBase)} network={asNetwork(network)} label="Sign the refund" variant="default" />;
}

/** The owner writes the profile's spending limits to the vault, so the two agree. */
export function SetPolicyOnChain({ contract, network, perTxCap, dailyCap }: {
  contract: string; network: string; perTxCap: string; dailyCap: string;
}) {
  const router = useRouter();
  return (
    <WalletSign call={vault.setPolicy(contract, perTxCap, dailyCap)} network={asNetwork(network)}
      label="Write the profile's limits to the vault" variant="default"
      onSigned={() => setTimeout(() => router.refresh(), 2500)} />
  );
}

export function FreezeOnChain({ contract, network, frozen }: { contract: string; network: string; frozen: boolean }) {
  const net = asNetwork(network);
  return frozen
    ? <WalletSign call={vault.unfreeze(contract)} network={net} label="Unfreeze the vault (owner)" />
    : <WalletSign call={vault.freeze(contract)} network={net} label="Freeze the vault" variant="destructive" />;
}
