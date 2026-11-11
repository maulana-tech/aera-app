"use client";

import {
  Activity, BookUser, Briefcase, CalendarClock, ChevronDown, ChevronsUpDown, Cpu, FileText, Inbox, KeyRound,
  Landmark, LayoutDashboard, LogIn, LogOut, Menu, MessagesSquare, PanelLeftClose, PanelLeftOpen, Plug,
  ReceiptText, ScrollText, Settings2, ShieldCheck, ShoppingBag, Sparkles, Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { AeraMark } from "@/components/aera-mark";
import { Dot, type Tone } from "@/components/dort";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { NAV_COOKIE } from "@/lib/nav";
import { cn } from "@/lib/utils";

export type Connection = {
  env: string;
  model_ready: boolean;
  private_mode?: boolean;
  rail?: "vault" | "simulated";
  network?: string;
};

type User = { name: string; role: string; email: string; limit_usd?: number };
type Item = { title: string; href: string; icon: React.ElementType; badge?: number };


const isActive = (pathname: string, href: string) => pathname === href || pathname.startsWith(href + "/");

function groups(pending: number): { label: string; items: Item[] }[] {
  return [
    {
      // The overview, then the main feature: ask the Supervisor, and through it the whole team.
      label: "",
      items: [
        { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
        { title: "Chat", href: "/chat", icon: MessagesSquare },
        { title: "Activity", href: "/activity", icon: Activity },
      ],
    },
    {
      label: "Run the business",
      items: [
        { title: "Work", href: "/work", icon: Inbox },
        { title: "Orders", href: "/orders", icon: ShoppingBag },
        { title: "Documents", href: "/documents", icon: FileText },
        { title: "Team", href: "/agents", icon: Users },
        { title: "Business", href: "/business", icon: Briefcase },
      ],
    },
    {
      label: "Money",
      items: [
        { title: "Treasury", href: "/treasury", icon: Landmark, badge: pending },
        { title: "Ledger", href: "/ledger", icon: ReceiptText },
      ],
    },
    {
      label: "Trust",
      items: [{ title: "Trust center", href: "/trust", icon: ShieldCheck }],
    },
  ];
}

const SETTINGS: Item[] = [
  { title: "Models", href: "/models", icon: Cpu },
  { title: "MCP", href: "/mcp", icon: Plug },
  { title: "Skills", href: "/skills", icon: Sparkles },
  { title: "Schedule", href: "/schedule", icon: CalendarClock },
  { title: "Contacts", href: "/contacts", icon: BookUser },
  { title: "Accounts", href: "/users", icon: KeyRound },
  { title: "Log", href: "/log", icon: ScrollText },
];

/** A nav tile on the blue: white when it is where you are, see-through otherwise. */
function NavTile({ item, on, slim, onNavigate }: { item: Item; on: boolean; slim: boolean; onNavigate?: () => void }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      title={slim ? item.title : undefined}
      aria-current={on ? "page" : undefined}
      className={cn(
        "relative flex h-9 items-center gap-3 rounded-md text-[14px] transition-colors outline-none focus-visible:ring-2 focus-visible:ring-white/60",
        slim ? "w-9 justify-center" : "px-3",
        on ? "bg-white text-brand shadow-soft" : "text-white/85 hover:bg-white/10 hover:text-white",
      )}
    >
      <Icon className="size-4 shrink-0" />
      {!slim && <span className="min-w-0 flex-1 truncate">{item.title}</span>}
      {!!item.badge && (
        <span
          aria-label={`${item.badge} waiting`}
          className={cn(
            "flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 font-mono text-[11px]",
            on ? "bg-brand text-white" : "bg-white text-brand",
            slim && "absolute -top-1 -right-1 h-4 min-w-4 px-1 text-[10px]",
          )}
        >
          {item.badge}
        </span>
      )}
    </Link>
  );
}

function SystemStatus({ c, slim }: { c?: Connection; slim: boolean }) {
  const ready = !!c?.model_ready;
  const vault = c?.rail === "vault";
  const tone: Tone = !c ? "bad" : ready && vault ? "ok" : "warn";
  const dot = { ok: "bg-emerald-300", warn: "bg-amber-300", bad: "bg-rose-300" }[tone as "ok" | "warn" | "bad"];
  const rows: { name: string; value: string; tone: Tone }[] = [
    { name: "Money rail", value: vault ? `vault · ${c?.network}` : "SIMULATED", tone: vault ? "ok" : "warn" },
    { name: "Private AI", value: c?.private_mode ? "TEE only" : "off", tone: c?.private_mode ? "ok" : "warn" },
    { name: "Models", value: ready ? "ready" : "not connected", tone: ready ? "ok" : "warn" },
  ];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        title={slim ? "System status" : undefined}
        className={cn(
          "flex items-center gap-2.5 rounded-md border border-white/15 bg-white/10 text-left text-white outline-none hover:bg-white/15 focus-visible:ring-2 focus-visible:ring-white/60",
          slim ? "size-9 justify-center" : "w-full px-3 py-2",
        )}
      >
        <span aria-hidden className={cn("size-2 shrink-0 rounded-full", dot)} />
        {!slim && (
          <>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-[13px]">{!c ? "Service down" : ready ? "Team can think" : "Models off"}</span>
              <span className="block truncate text-[11.5px] text-white/70">{!c ? "agent service not answering" : vault ? `vault · ${c.network}` : "simulated payments"}</span>
            </span>
            <ChevronsUpDown className="size-3.5 shrink-0 opacity-70" />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="start" sideOffset={10} className="w-72">
        <DropdownMenuLabel className="text-muted-foreground text-xs font-normal">Environment {c?.env ?? "unknown"}</DropdownMenuLabel>
        {rows.map((r) => (
          <div key={r.name} className="flex items-center gap-2 px-2 py-1.5 text-[13px]">
            <Dot tone={r.tone} />
            <span className="flex-1">{r.name}</span>
            <span className="text-muted-foreground font-mono text-[11px]">{r.value}</span>
          </div>
        ))}
        <DropdownMenuSeparator />
        <p className="text-muted-foreground px-2 py-1.5 text-xs leading-relaxed">
          {ready
            ? "Every agent reasons on a NEAR AI Cloud model; each call carries an attestation proof you can re-check on the run."
            : "Until a model is connected the team makes no decisions: work is held, not guessed."}
        </p>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** What a role may approve (core/identity.py ROLE_LIMITS); the service checks it again. */
const authority = (u: User) =>
  !u.limit_usd ? `${u.role} · read only` : `${u.role} · up to $${u.limit_usd.toLocaleString("en-US")}`;

function UserMenu({ user, slim }: { user?: User; slim: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  if (!user) {
    return (
      <Link href="/login" className="flex h-9 items-center gap-3 rounded-md px-3 text-[14px] text-white/85 hover:bg-white/10">
        <LogIn className="size-4" /> {!slim && "Sign in"}
      </Link>
    );
  }
  async function signOut() {
    setBusy(true);
    await fetch("/api/login", { method: "DELETE" });
    router.push("/");
    router.refresh();
  }
  const initials = user.name.split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Signed in as ${user.name}`}
        className={cn(
          "flex items-center gap-2.5 rounded-md text-left text-white outline-none hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white/60",
          slim ? "size-9 justify-center" : "w-full p-1.5",
        )}
      >
        <span className="text-brand flex size-8 shrink-0 items-center justify-center rounded-md bg-white text-[12px] font-medium shadow-soft">
          {initials}
        </span>
        {!slim && (
          <>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-[13px]">{user.name}</span>
              <span className="block truncate text-[11.5px] text-white/70">{authority(user)}</span>
            </span>
            <ChevronsUpDown className="size-3.5 shrink-0 opacity-70" />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="end" sideOffset={10} className="w-64">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate text-sm font-medium">{user.name}</span>
          <span className="text-muted-foreground block truncate font-mono text-xs">{user.email}</span>
          <span className="text-muted-foreground mt-1 block text-xs">Authority: {authority(user)}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={signOut} disabled={busy}>
          <LogOut />
          {busy ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

type Props = { user?: User; connection?: Connection; pending?: number; stopped?: boolean };

/** The sidebar's contents, shared by the desktop rail and the phone drawer. */
function NavBody({ user, connection, pending = 0, stopped, slim, onNavigate, onCollapse }: Props & {
  slim: boolean; onNavigate?: () => void; onCollapse?: () => void;
}) {
  const pathname = usePathname();
  const inSettings = SETTINGS.some((s) => isActive(pathname, s.href));
  const [settingsOpen, setSettingsOpen] = useState(inSettings);
  const open = settingsOpen || inSettings;

  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <div className={cn("flex h-10 items-center", slim ? "justify-center" : "justify-between pl-1.5")}>
        <Link href="/dashboard" onClick={onNavigate} className="flex items-center gap-2 rounded-md text-white outline-none focus-visible:ring-2 focus-visible:ring-white/60" title={slim ? "Dashboard" : undefined}>
          <AeraMark className="size-6" />
          {!slim && <span className="text-[19px] tracking-[-0.02em]">aera</span>}
        </Link>
        {onCollapse && !slim && (
          <button type="button" onClick={onCollapse} aria-label="Collapse the sidebar" title="Collapse"
            className="flex size-8 items-center justify-center rounded-md text-white/75 hover:bg-white/10 hover:text-white">
            <PanelLeftClose className="size-4" />
          </button>
        )}
      </div>

      <SystemStatus c={connection} slim={slim} />
      {stopped && (
        <Link href="/business" onClick={onNavigate} title="The kill switch is on: nothing is sent and no money moves"
          className={cn("flex items-center gap-2 rounded-md bg-white text-[13px] text-[#b71e1e] shadow-soft", slim ? "size-9 justify-center" : "px-3 py-2")}>
          <Dot tone="bad" />
          {!slim && "Stopped · kill switch on"}
        </Link>
      )}

      <nav aria-label="Main" className={cn("-mx-1 flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-1 pt-1", slim && "items-center")}>
        {groups(pending).map((g) => (
          <div key={g.label} className={cn("flex flex-col gap-0.5", slim && "items-center")}>
            {g.label && (slim ? <div className="mx-auto mb-1 h-px w-6 bg-white/15" /> : <p className="mb-1 px-3 text-[12px] text-white/60">{g.label}</p>)}
            {g.items.map((it) => (
              <NavTile key={it.href} item={it} on={isActive(pathname, it.href)} slim={slim} onNavigate={onNavigate} />
            ))}
          </div>
        ))}

        <div className={cn("flex flex-col gap-0.5", slim && "items-center")}>
          {slim ? (
            <div className="mx-auto mb-1 h-px w-6 bg-white/15" />
          ) : (
            <button type="button" onClick={() => setSettingsOpen(!open)} aria-expanded={open}
              className={cn("flex h-9 items-center gap-3 rounded-md px-3 text-[14px] outline-none hover:bg-white/10 focus-visible:ring-2 focus-visible:ring-white/60",
                inSettings ? "text-white" : "text-white/85")}>
              <Settings2 className="size-4" />
              <span className="flex-1 text-left">Settings</span>
              <ChevronDown className={cn("size-3.5 opacity-70 transition-transform", open && "rotate-180")} />
            </button>
          )}
          {(slim || open) && (
            <div className={cn("flex flex-col gap-0.5", !slim && "ml-[18px] border-l border-white/15 pl-2")}>
              {SETTINGS.map((it) => (
                <NavTile key={it.href} item={it} on={isActive(pathname, it.href)} slim={slim} onNavigate={onNavigate} />
              ))}
            </div>
          )}
        </div>
      </nav>

      <div className={cn("border-t border-white/15 pt-3", slim && "flex justify-center")}>
        <UserMenu user={user} slim={slim} />
      </div>
    </div>
  );
}

/** Desktop: a rail on the blue canvas that collapses to icons. Phone: a top bar and a drawer. */
export function SideNav({ collapsed: initial = false, ...props }: Props & { collapsed?: boolean }) {
  const [slim, setSlim] = useState(initial);
  const [drawer, setDrawer] = useState(false);
  const pathname = usePathname();
  const current = [...groups(0).flatMap((g) => g.items), ...SETTINGS].find((i) => isActive(pathname, i.href));

  function toggle(next: boolean) {
    setSlim(next);
    document.cookie = `${NAV_COOKIE}=${next ? "slim" : "wide"}; path=/; max-age=31536000; samesite=lax`;
  }

  return (
    <>
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 transition-[width] duration-200 md:block",
          slim ? "w-[68px]" : "w-[248px]",
        )}
      >
        <NavBody {...props} slim={slim} onCollapse={() => toggle(true)} />
        {slim && (
          <button type="button" onClick={() => toggle(false)} aria-label="Expand the sidebar" title="Expand"
            className="absolute top-14 -right-2.5 z-10 flex size-6 items-center justify-center rounded-full bg-white text-brand shadow-soft hover:bg-raised">
            <PanelLeftOpen className="size-3.5" />
          </button>
        )}
      </aside>

      <div className="sticky top-0 z-30 flex h-14 items-center gap-2 px-3 md:hidden">
        <Sheet open={drawer} onOpenChange={setDrawer}>
          <SheetTrigger aria-label="Open the menu"
            className="flex size-9 items-center justify-center rounded-md bg-white text-brand shadow-soft">
            <Menu className="size-4" />
          </SheetTrigger>
          <SheetContent side="left" showCloseButton={false} className="bg-canvas dot-grid w-[280px] gap-0 border-0 p-0 text-white sm:max-w-[280px]">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <NavBody {...props} slim={false} onNavigate={() => setDrawer(false)} />
          </SheetContent>
        </Sheet>
        <AeraMark className="size-5 text-white" />
        <span className="min-w-0 flex-1 truncate text-[15px] text-white">{current?.title ?? "aera"}</span>
        {!!props.pending && (
          <Link href="/treasury" className="text-brand rounded-full bg-white px-2 py-0.5 font-mono text-[11px] shadow-soft">
            {props.pending} waiting
          </Link>
        )}
      </div>
    </>
  );
}
