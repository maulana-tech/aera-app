import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { publicApi, usd, when, withB, type PublicSample } from "@/app/lib";
import { Markdown } from "@/components/markdown";
import { PublicShell } from "@/components/public-shell";
import { Button } from "@/components/ui/button";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  // Not publicApi: that would count a read for the metadata as well as for the page.
  return { title: slug.replace(/-/g, " "), description: "A free sample, published by the team." };
}

export default async function SamplePage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ b?: string }> }) {
  const { slug } = await params;
  const { b } = await searchParams;
  const s = await publicApi<PublicSample>(`samples/${slug}`, b);
  if (!s) notFound();
  const o = s.offering;
  const cta = (
    <div className="bg-raised rounded-lg p-4">
      <p className="text-[14px] font-medium">{o.title ?? "The full version"}{o.price_usd != null && <span className="font-mono"> · {usd(o.price_usd)}</span>}</p>
      {o.description && <p className="text-muted-foreground mt-1 text-[13px] leading-relaxed">{o.description}</p>}
      <Button asChild size="sm" className="mt-3"><Link href={withB(s.checkout, b)}>Order yours</Link></Button>
    </div>
  );
  return (
    <PublicShell business={s.business}>
      <p className="text-muted-foreground font-mono text-[11px]">Free sample · {when(s.published_at)}</p>
      <div className="mt-3">{cta}</div>
      <article className="mt-6"><Markdown>{s.text}</Markdown></article>
      <div className="mt-8">{cta}</div>
      <p className="text-muted-foreground mt-6 text-[12px]"><Link href={withB("/samples", b)} className="hover:underline">← all samples</Link></p>
    </PublicShell>
  );
}
