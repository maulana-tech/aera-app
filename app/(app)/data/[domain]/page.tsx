import { permanentRedirect } from "next/navigation";

/* Each domain used to have its own table page, which meant every specialist
 * had two pages: an empty profile and the table showing their actual work.
 * They are one page now. A domain name is the code of the agent who owns it,
 * so the old links still resolve. */
export default async function DomainRedirect({
  params,
}: { params: Promise<{ domain: string }> }) {
  permanentRedirect(`/agents/${(await params).domain}`);
}
