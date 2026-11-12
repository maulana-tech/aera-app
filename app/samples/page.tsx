import type { Metadata } from "next";
import Link from "next/link";

import { publicApi, when, type PublicSampleRow } from "@/app/lib";
import { PublicShell } from "@/components/public-shell";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Free samples", description: "Free samples of the work, published by the team." };

export default async function Samples() {
  const data = await publicApi<{ business?: string | null; samples: PublicSampleRow[] }>("samples");
  const rows = data?.samples ?? [];
  return (
    <PublicShell business={data?.business}>
      <h1 className="text-[22px]">Free samples</h1>
      <p className="text-muted-foreground mt-1.5 text-[13.5px] leading-relaxed">
        Real work by the team, free to read. Each one links to the paid version.
      </p>
      {rows.length === 0 ? (
        <p className="text-muted-foreground mt-8 text-sm">Nothing is published yet.</p>
      ) : (
        <ul className="mt-6 divide-y rounded-lg border">
          {rows.map((s) => (
            <li key={s.slug}>
              <Link href={`/samples/${s.slug}`} className="hover:bg-muted/40 block px-4 py-3.5">
                <p className="text-[15px] font-medium">{s.title}</p>
                {s.teaser && <p className="text-muted-foreground mt-0.5 text-[13px] leading-relaxed">{s.teaser}</p>}
                <p className="text-muted-foreground mt-1 font-mono text-[11px]">{when(s.published_at)}{s.offering_title ? ` · ${s.offering_title}` : ""}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PublicShell>
  );
}
