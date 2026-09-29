"use client";

import Conversation from "@/app/(app)/agents/[code]/Conversation";

/* The open conversation lives in the address bar, which is what survives a
 * refresh. replaceState rather than router.replace on purpose: the router would
 * re-render the server page and remount the transcript mid-conversation, and
 * all that is actually needed here is for the URL to be right if the tab is
 * reloaded or the link is shared.
 */
export default function ChatSurface(props: {
  code: string;
  name: string;
  work: string;
  examples: string[];
  signedIn: boolean;
  threadId: string | null;
}) {
  return (
    <Conversation
      {...props}
      rail
      onOpen={(id) =>
        window.history.replaceState(null, "", id ? `/chat?c=${id}` : "/chat")
      }
    />
  );
}
