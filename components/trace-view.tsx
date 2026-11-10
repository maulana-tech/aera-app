"use client";

import { useRef, useState } from "react";

import { TraceCalls } from "@/components/trace-calls";
import { TraceNodeDetail } from "@/components/trace-node-detail";
import { TraceTopology } from "@/components/trace-topology";
import type { Trace } from "@/app/lib";

/** The graph, the node drawer and the call list share one selection. A node
 *  clicked in the graph lights its path and opens in the drawer; "show in the
 *  step list" closes the drawer and leaves the list narrowed to that node. */
export default function TraceView({ trace, focusSeq }: { trace: Trace; focusSeq: number | null }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const list = useRef<HTMLElement | null>(null);

  const pick = (id: string | null) => { setSelected(id); setDrawer(!!id); };

  return (
    <>
      <section className="mt-6">
        <h2 className="mb-1 text-sm font-semibold">Topology</h2>
        <p className="text-muted-foreground mb-3 text-xs">
          Who asked whom, which tool each called, and where every figure was read from. Click a
          node to open its details: its numbers, what it connects to, and every step through it.
        </p>
        <TraceTopology trace={trace} selected={selected} onSelect={pick} />
      </section>
      <section ref={list} className="mt-8 scroll-mt-4">
        <h2 className="mb-3 text-sm font-semibold">Every step, in order</h2>
        <TraceCalls
          trace={trace}
          runId={trace.run.id}
          nodeFilter={selected}
          onClearNode={() => pick(null)}
          focusSeq={focusSeq}
        />
      </section>

      <TraceNodeDetail
        trace={trace}
        nodeId={drawer ? selected : null}
        runId={trace.run.id}
        onSelect={pick}
        onClose={() => pick(null)}
        onShowInList={() => {
          setDrawer(false);
          // After the drawer has slid out, so the scroll is not fighting its focus trap.
          setTimeout(() => list.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 250);
        }}
      />
    </>
  );
}
