import type { Metadata } from "next";
import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { PublicShell } from "@/components/public-shell";

export const metadata: Metadata = {
  title: "Get a NEAR AI key",
  description: "How to get a NEAR AI Cloud API key for your AERA business, and where to put it.",
};

/* Written from NEAR AI's own pages as read on 2026-11-13: cloud.near.ai (sign-in) and
 * docs.near.ai/cloud/quickstart (setup steps, test call). Where those pages say nothing (prices, free credit,
 * payment methods, whether a key is shown once), this page says nothing either. */

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-4">
      <span className="bg-brand grid size-8 shrink-0 place-items-center rounded-full font-mono text-[12px] text-white">{n}</span>
      <div className="min-w-0 flex-1 pb-6">
        <h2 className="text-fg text-[16px]">{title}</h2>
        <div className="text-body mt-1.5 space-y-2 text-[14px] leading-relaxed">{children}</div>
      </div>
    </li>
  );
}

const ext = "text-brand inline-flex items-center gap-1 underline-offset-2 hover:underline";

export default function NearAiKeyGuide() {
  return (
    <PublicShell business="aera">
      <p className="text-muted-foreground font-mono text-[12px]">Guide</p>
      <h1 className="text-fg mt-2 text-[26px] leading-tight tracking-tight">Get a NEAR AI key for your business</h1>
      <p className="text-body mt-3 text-[15px] leading-relaxed">
        Your agents think on NEAR AI Cloud, inside trusted execution environments. A business can start on AERA&apos;s
        shared key with a small daily allowance; with your own key the allowance is gone and you pay NEAR AI directly
        for what your agents use.
      </p>

      <ol className="mt-8">
        <Step n={1} title="Sign in to NEAR AI Cloud">
          <p>
            Open <a href="https://cloud.near.ai" target="_blank" rel="noopener noreferrer" className={ext}>cloud.near.ai <ExternalLink className="size-3" /></a>.
            Signing in and signing up are the same page: choose <b>Sign in with Google</b>, <b>Sign in with GitHub</b> or <b>Sign in with NEAR</b>.
          </p>
        </Step>
        <Step n={2} title="Add credits">
          <p>
            In the console, open the <b>Credits</b> section and add credits for what you expect your agents to use.
            NEAR AI describes top-ups and pay-as-you-go; its pages do not list prices here, so check the console for current amounts.
          </p>
        </Step>
        <Step n={3} title="Create an API key">
          <p>Open the <b>API Keys</b> section and generate a new key. Copy it somewhere safe right away.</p>
          <p className="text-muted-foreground text-[13px]">
            Never share it publicly or commit it to a repository. If it leaks, regenerate it from the same dashboard.
          </p>
        </Step>
        <Step n={4} title="Check that it works (optional)">
          <p>From a terminal, with your key in place of <span className="font-mono text-[13px]">YOUR_API_KEY</span>:</p>
          <pre className="bg-inset text-fg overflow-x-auto rounded-lg border p-3 font-mono text-[12px] leading-relaxed">{`curl https://cloud-api.near.ai/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{"model": "zai-org/GLM-5.1-FP8",
       "messages": [{"role": "user", "content": "Hello, NEAR AI!"}]}'`}</pre>
          <p className="text-muted-foreground text-[13px]">An answer back means the key and its credits are good. (This example is the one in NEAR AI&apos;s quickstart.)</p>
        </Step>
        <Step n={5} title="Give it to your business">
          <p>
            <b>New business:</b> on <Link href="/login?mode=business" className={ext}>Create your business</Link>, choose
            <b> Use my own NEAR AI key</b> and paste it.
          </p>
          <p>
            <b>Already running on AERA&apos;s key:</b> sign in as the owner, open <b>Models</b>, paste the key under
            <b> NEAR AI key</b> and save. Your business restarts on it in a few seconds; the daily allowance no longer applies.
          </p>
          <p className="text-muted-foreground text-[13px]">
            The key is stored for your business only, readable by its own agent service and nothing else on this install, and is never shown back in the app.
          </p>
        </Step>
      </ol>

      <p className="text-muted-foreground border-t pt-4 text-[12.5px] leading-relaxed">
        From NEAR AI&apos;s own pages:{" "}
        <a href="https://docs.near.ai/cloud/quickstart/" target="_blank" rel="noopener noreferrer" className={ext}>quickstart <ExternalLink className="size-3" /></a>
        {" · "}
        <a href="https://docs.near.ai/" target="_blank" rel="noopener noreferrer" className={ext}>docs <ExternalLink className="size-3" /></a>.
        If their console has moved things since, follow it over this page.
      </p>
    </PublicShell>
  );
}
