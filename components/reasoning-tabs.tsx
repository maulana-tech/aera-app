"use client";

import { useState, type ReactNode } from "react";

import { ExplorationGraph } from "@/components/exploration-graph";
import { cn } from "@/lib/utils";
import type { ExplorationGraph as Graph } from "@/app/lib";

interface TabProps {
  id: "graph" | "steps";
  currentTab: "graph" | "steps";
  onClick: (id: "graph" | "steps") => void;
  children: ReactNode;
}

function Tab({ id, currentTab, onClick, children }: TabProps) {
  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      className={cn(
        "border-b-2 px-1 pb-2 text-sm transition-colors",
        currentTab === id
          ? "border-foreground text-foreground font-medium"
          : "text-muted-foreground hover:text-foreground border-transparent",
      )}
    >
      {children}
    </button>
  );
}

/* Two views of the same handling, on one tab strip: the step-by-step record
 * (server-rendered, passed in as `reasoning`) and the exploration graph that
 * record filled in. The graph tab leads when the graph was recorded, because it
 * shows the SHAPE of the reasoning — which lead spawned which — that the linear
 * step list cannot. */
export function ReasoningTabs({
  reasoning,
  stepCount,
  graph,
}: {
  reasoning: ReactNode;
  stepCount: number;
  graph: Graph | null;
}) {
  const hasGraph = !!graph && graph.nodes.length > 0;
  const [tab, setTab] = useState<"graph" | "steps">(hasGraph ? "graph" : "steps");

  return (
    <div>
      <div className="mb-5 flex items-center gap-5 border-b">
        <Tab id="graph" currentTab={tab} onClick={setTab}>
          Exploration graph{hasGraph ? ` (${graph!.nodes.length})` : ""}
        </Tab>
        <Tab id="steps" currentTab={tab} onClick={setTab}>
          How it reasoned ({stepCount})
        </Tab>
      </div>
      <div className={cn(tab !== "graph" && "hidden")}>
        <ExplorationGraph graph={graph} />
      </div>
      <div className={cn(tab !== "steps" && "hidden")}>{reasoning}</div>
    </div>
  );
}
