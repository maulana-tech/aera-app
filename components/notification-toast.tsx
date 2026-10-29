"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowRight, MessageSquare, Sparkles, X } from "lucide-react";
import { AgentBadge } from "@/components/agent-card";
import { Button } from "@/components/ui/button";

export type AIOutputNotification = {
  id: string;
  agentName: string;
  conversationId: string;
  preview?: string;
  timestamp: number;
};

type StoredPending = {
  conversationId: string;
  agentCode: string;
  agentName: string;
  startedAt: number;
};

const STORAGE_KEY = "sigap:pending_ai_task";
const EVENT_START = "sigap:ai-output-start";
const EVENT_DONE = "sigap:ai-output-done";

/**
 * Register that an AI query is actively generating.
 * Persists to localStorage so navigation across pages won't lose track of it.
 */
export function trackAIGeneration(task: {
  conversationId: string;
  agentCode?: string;
  agentName: string;
}) {
  if (typeof window === "undefined") return;
  const payload: StoredPending = {
    conversationId: task.conversationId,
    agentCode: task.agentCode || "supervisor",
    agentName: task.agentName,
    startedAt: Date.now(),
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {}
  window.dispatchEvent(new CustomEvent(EVENT_START, { detail: payload }));
}

/**
 * Notify that the AI output is ready.
 */
export function notifyAIOutputReady(task: {
  conversationId: string;
  agentName: string;
  preview?: string;
}) {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
  window.dispatchEvent(
    new CustomEvent(EVENT_DONE, {
      detail: task,
    })
  );
}

function playChime() {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime);
    osc.frequency.setValueAtTime(880, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch {}
}

const DURATION_MS = 15000;

export function NotificationToast() {
  const [notification, setNotification] = useState<AIOutputNotification | null>(
    null
  );
  const [isHovered, setIsHovered] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  // Check if current page is the conversation page
  const isConversationPage =
    pathname === "/chat" || pathname.startsWith("/chat");

  // Automatically dismiss the toast if user enters the conversation page
  useEffect(() => {
    if (isConversationPage && notification) {
      setNotification(null);
    }
  }, [isConversationPage, notification]);

  // Show notification if user is NOT on conversation page
  const triggerNotification = useCallback(
    (detail: {
      conversationId: string;
      agentName: string;
      preview?: string;
    }) => {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {}

      // Only show if user is NOT currently looking at the conversation
      const currentPath = window.location.pathname;
      const isCurrentlyInChat =
        currentPath === "/chat" || currentPath.startsWith("/chat");

      if (isCurrentlyInChat) {
        return;
      }

      setNotification({
        id: `${detail.conversationId}-${Date.now()}`,
        agentName: detail.agentName || "Arya",
        conversationId: detail.conversationId,
        preview: detail.preview,
        timestamp: Date.now(),
      });
      playChime();
    },
    []
  );

  // Listen for direct completion / start events
  useEffect(() => {
    const onDone = (e: Event) => {
      const custom = e as CustomEvent<{
        conversationId: string;
        agentName: string;
        preview?: string;
      }>;
      if (custom.detail) {
        triggerNotification(custom.detail);
      }
    };

    window.addEventListener(EVENT_DONE, onDone);
    return () => {
      window.removeEventListener(EVENT_DONE, onDone);
    };
  }, [triggerNotification]);

  // Global background poller: polls whenever an AI task was started,
  // even if the user completely navigated away from the conversation page.
  useEffect(() => {
    const interval = setInterval(async () => {
      let stored: StoredPending | null = null;
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) stored = JSON.parse(raw);
      } catch {
        return;
      }

      if (!stored) return;

      // Expire after 3 minutes
      if (Date.now() - stored.startedAt > 180000) {
        try {
          localStorage.removeItem(STORAGE_KEY);
        } catch {}
        return;
      }

      let targetCid = stored.conversationId;

      // If conversationId was 'new', resolve it from the latest thread
      if (!targetCid || targetCid === "new") {
        try {
          const listRes = await fetch(
            `/api/sigap/agents/${stored.agentCode}/conversations`,
            { cache: "no-store" }
          );
          if (listRes.ok) {
            const listData = await listRes.json();
            const convs = listData.conversations ?? [];
            if (convs.length > 0) {
              targetCid = convs[0].id;
              stored.conversationId = targetCid;
              try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
              } catch {}
            }
          }
        } catch {
          return;
        }
      }

      if (!targetCid || targetCid === "new") return;

      // Check if the conversation has completed
      try {
        const convRes = await fetch(`/api/sigap/conversations/${targetCid}`, {
          cache: "no-store",
        });
        if (!convRes.ok) return;

        const convData = await convRes.json();
        const msgs = convData.messages ?? [];
        const lastMsg = msgs[msgs.length - 1];

        if (lastMsg && (lastMsg.role === "agent" || lastMsg.from === "agent")) {
          const body = lastMsg.body ?? lastMsg.reply;
          const answerText =
            typeof body === "string"
              ? body
              : body?.answer || "Response ready";

          triggerNotification({
            conversationId: targetCid,
            agentName: stored.agentName,
            preview: answerText,
          });
        }
      } catch {
        // ignore network error
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [triggerNotification]);

  // Auto-dismiss countdown (pauses on hover)
  useEffect(() => {
    if (!notification || isHovered) return;
    const timer = setTimeout(() => {
      setNotification(null);
    }, DURATION_MS);
    return () => clearTimeout(timer);
  }, [notification, isHovered]);

  if (!notification || isConversationPage) return null;

  return (
    <div
      className="fixed bottom-5 right-5 z-[9999] max-w-sm w-[360px] animate-in slide-in-from-bottom-5 fade-in duration-300 pointer-events-auto"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="rounded-xl border border-border/80 bg-background/95 p-4 shadow-2xl backdrop-blur-md transition-all">
        {/* Header */}
        <div className="flex items-center justify-between gap-2.5">
          <div className="flex items-center gap-2">
            <AgentBadge nickname={notification.agentName} size="xs" showTooltip={false} />
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold tracking-tight text-foreground">
                {notification.agentName}
              </span>
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <span className="text-[11px] font-mono text-muted-foreground/80">
              Just now
            </span>
            <button
              onClick={() => setNotification(null)}
              className="text-muted-foreground hover:text-foreground ml-1 rounded-md p-1 transition-colors hover:bg-muted"
              aria-label="Dismiss notification"
            >
              <X className="size-3.5" />
            </button>
          </div>
        </div>

        {/* Title & Preview */}
        <div className="mt-2.5">
          <p className="text-xs font-medium text-foreground flex items-center gap-1.5">
            <Sparkles className="size-3 text-amber-500" />
            Response ready
          </p>
          {notification.preview && (
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
              {notification.preview.replace(/^#+\s+/g, "")}
            </p>
          )}
        </div>

        {/* Action Button */}
        <div className="mt-3.5 pt-2 border-t flex justify-end">
          <Button
            size="sm"
            className="h-8 gap-1.5 px-3 text-xs w-full justify-center"
            onClick={() => {
              setNotification(null);
              router.push(`/chat?c=${notification.conversationId}`);
            }}
          >
            <MessageSquare className="size-3.5" />
            <span>View response</span>
            <ArrowRight className="size-3.5 ml-auto" />
          </Button>
        </div>
      </div>
    </div>
  );
}
