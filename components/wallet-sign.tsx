"use client";

import { Check, Copy, ExternalLink, Loader2, Terminal, Wallet } from "lucide-react";
import { useState } from "react";

import { explorer } from "@/app/lib";
import { Button } from "@/components/ui/button";
import {
  cliCommand, connectWallet, signAndSend, type ContractCall, type Network,
} from "@/lib/near-wallet";
import { errorText } from "@/lib/post";

/** A button that signs one contract call from the person's own wallet. When no
 *  wallet can be reached it says why and hands over the exact near-cli-rs
 *  command that does the same thing, so the action is never a dead end. */
export function WalletSign({
  call, network, label, variant = "outline", onSigned, disabled,
}: {
  call: ContractCall;
  network: Network;
  label: string;
  variant?: "default" | "outline" | "destructive" | "secondary";
  onSigned?: (txHash: string) => void;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [tx, setTx] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCli, setShowCli] = useState(false);

  async function sign() {
    setBusy(true);
    setError(null);
    try {
      await connectWallet(network);
      const hash = await signAndSend(call, network);
      setTx(hash);
      onSigned?.(hash);
    } catch (e) {
      setError(errorText(e));
      setShowCli(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-w-0 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant={variant} onClick={sign} disabled={busy || disabled || !!tx}>
          {busy ? <Loader2 className="animate-spin" /> : tx ? <Check /> : <Wallet />}
          {tx ? "Signed" : label}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setShowCli((v) => !v)} aria-expanded={showCli}>
          <Terminal />
          CLI
        </Button>
        {tx && (
          <a href={explorer(network, "txns", tx)} target="_blank" rel="noopener noreferrer"
             className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 font-mono text-[11px] underline underline-offset-2">
            {tx.slice(0, 10)}… <ExternalLink className="size-3" />
          </a>
        )}
      </div>
      {error && (
        <p className="text-xs text-warn ">
          The wallet could not sign: {error}. Run the command below instead.
        </p>
      )}
      {showCli && <CliCommand command={cliCommand(call, network)} />}
    </div>
  );
}

export function CliCommand({ command }: { command: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="bg-muted/50 relative rounded-md border">
      <pre className="overflow-x-auto p-3 pr-10 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-all">
        {command}
      </pre>
      <Button size="icon-xs" variant="ghost" className="absolute top-1.5 right-1.5" aria-label="Copy command"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(command);
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          } catch {
            // clipboard blocked; the text is selectable
          }
        }}>
        {done ? <Check /> : <Copy />}
      </Button>
    </div>
  );
}
