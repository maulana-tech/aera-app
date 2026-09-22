"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/** Refresh the page while a handling is still running.
 *  This product is about agents working on their own — the user should not
 *  have to hit reload to find out how far along they are. */
export function AutoRefresh({ active, every = 4000 }: { active: boolean; every?: number }) {
  const router = useRouter();
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (!active || !visible) return;
    const t = setInterval(() => router.refresh(), every);
    return () => clearInterval(t);
  }, [active, visible, every, router]);

  useEffect(() => {
    const onChange = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);

  if (!active) return null;
  return (
    <span className="text-muted-foreground flex items-center gap-1.5 font-mono text-[11px]">
      <span className="relative flex size-1.5">
        <span className="bg-sky-500 absolute inline-flex size-full animate-ping rounded-full opacity-75" />
        <span className="bg-sky-500 relative inline-flex size-1.5 rounded-full" />
      </span>
      watching
    </span>
  );
}
