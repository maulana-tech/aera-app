"use client";

import { ChevronDown, LogIn, LogOut, Menu } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { AeraMark } from "@/components/aera-mark";
import { CanvasChip, Dot, type Tone } from "@/components/dort";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export type Connection = {
  env: string;
  model_ready: boolean;
  private_mode?: boolean;
  rail?: "vault" | "simulated";
  network?: string;
};

type User = { name: string; role: string; email: string; limit_usd?: number };

const ROUTES = [
  { title: "Dashboard", href: "/dashboard" },
  { title: "Work", href: "/work" },
  { title: "Orders", href: "/orders" },
  { title: "Documents", href: "/documents" },
  { title: "Team", href: "/agents" },
  { title: "Business", href: "/business" },
  { title: "Treasury", href: "/treasury" },
  { title: "Ledger", href: "/ledger" },
  { title: "Chat", href: "/chat" },
];

const SETTINGS = [
  { title: "Models", href: "/models", note: "which model each agent thinks with" },
  { title: "MCP", href: "/mcp", note: "outside tools the team may call" },
  { title: "Skills", href: "/skills", note: "playbooks the agents follow" },
  { title: "Schedule", href: "/schedule", note: "what runs on its own, and when" },
  { title: "Contacts", href: "/contacts", note: "customers, vendors, payout details" },
  { title: "Accounts", href: "/users", note: "people and what they may approve" },
  { title: "Log", href: "/log", note: "every step, tool call and decision" },
];

const isActive = (pathname: string, href: string) => pathname === href || pathname.startsWith(href + "/");

/** One route tile: white when it is where you are, see-through on the blue otherwise. */
function tile(on: boolean) {
  return cn(
    "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-3.5 text-[14px] transition-colors outline-none focus-visible:ring-2 focus-visible:ring-white/60",
    on ? "bg-white text-brand shadow-soft" : "text-white/90 hover:bg-white/10 hover:text-white",
  );
}

/** What a role may approve (core/identity.py ROLE_LIMITS); the service checks it again. */
const authority = (u: User) =>
  !u.limit_usd ? `${u.role} · read only` : `${u.role} · up to $${u.limit_usd.toLocaleString("en-US")}`;

function SystemStatus({ c }: { c?: Connection }) {
  const ready = !!c?.model_ready;
  const vault = c?.rail === "vault";
  const tone: Tone = !c ? "bad" : ready && vault ? "ok" : "warn";
  const label = !c ? "service down" : `${vault ? `vault · ${c.network}` : "simulated"} · ${ready ? "models ready" : "models off"}`;
  const rows: { name: string; value: string; tone: Tone }[] = [
    { name: "Money rail", value: vault ? `vault · ${c?.network}` : "SIMULATED", tone: vault ? "ok" : "warn" },
    { name: "Private AI", value: c?.private_mode ? "TEE only" : "off", tone: c?.private_mode ? "ok" : "warn" },
    { name: "Models", value: ready ? "ready" : "not connected", tone: ready ? "ok" : "warn" },
  ];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-white/60">
        <CanvasChip tone={tone} className="hover:bg-white/15">
          <span className="hidden lg:inline">{label}</span>
          <span className="lg:hidden">status</span>
          <ChevronDown className="size-3.5 opacity-80" />
        </CanvasChip>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={8} className="w-72">
        <DropdownMenuLabel className="text-muted-foreground text-xs font-normal">
          Environment {c?.env ?? "unknown"}
        </DropdownMenuLabel>
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

function UserMenu({ user }: { user?: User }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  if (!user) {
    return (
      <Link href="/login" className={tile(false)}>
        <LogIn className="size-4" /> Sign in
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
        className="flex size-9 shrink-0 items-center justify-center rounded-md bg-white text-[12px] font-medium text-brand shadow-soft outline-none focus-visible:ring-2 focus-visible:ring-white/60"
      >
        {initials}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={8} className="w-64">
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

export function TopNav({ user, connection, stopped }: { user?: User; connection?: Connection; stopped?: boolean }) {
  const pathname = usePathname();
  const inSettings = SETTINGS.some((s) => isActive(pathname, s.href));
  const current = SETTINGS.find((s) => isActive(pathname, s.href));

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-2 px-3 md:gap-4 md:px-4">
      <Link href="/dashboard" className="flex shrink-0 items-center gap-2 rounded-md px-1.5 py-1 text-white outline-none focus-visible:ring-2 focus-visible:ring-white/60">
        <AeraMark className="size-6" />
        <span className="hidden text-[19px] tracking-[-0.02em] sm:inline">aera</span>
      </Link>

      {/* Small screens: one menu tile naming where you are, holding every page. */}
      <div className="flex min-w-0 flex-1 lg:hidden">
        <DropdownMenu>
          <DropdownMenuTrigger className={cn(tile(true), "min-w-0")}>
            <Menu className="size-4" />
            <span className="truncate">{[...ROUTES, ...SETTINGS].find((r) => isActive(pathname, r.href))?.title ?? "Menu"}</span>
            <ChevronDown className="size-3.5 opacity-70" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" sideOffset={8} className="max-h-[75dvh] w-64">
            {ROUTES.map((r) => (
              <DropdownMenuItem key={r.href} asChild className={cn(isActive(pathname, r.href) && "bg-accent")}>
                <Link href={r.href} className="text-[14px]">{r.title}</Link>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-muted-foreground text-xs font-normal">Settings</DropdownMenuLabel>
            {SETTINGS.map((s) => (
              <DropdownMenuItem key={s.href} asChild className={cn(isActive(pathname, s.href) && "bg-accent")}>
                <Link href={s.href} className="text-[14px]">{s.title}</Link>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <nav aria-label="Main" className="rail-x hidden min-w-0 flex-1 items-center gap-1 lg:flex">
        {ROUTES.map((r) => (
          <Link key={r.href} href={r.href} className={tile(isActive(pathname, r.href))} aria-current={isActive(pathname, r.href) ? "page" : undefined}>
            {r.title}
          </Link>
        ))}
        <DropdownMenu>
          <DropdownMenuTrigger className={tile(inSettings)}>
            {current ? current.title : "Settings"}
            <ChevronDown className="size-3.5 opacity-70" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" sideOffset={8} className="w-72">
            {SETTINGS.map((s) => (
              <DropdownMenuItem key={s.href} asChild className={cn("items-start", isActive(pathname, s.href) && "bg-accent")}>
                <Link href={s.href} className="flex flex-col gap-0.5">
                  <span className="text-[13px]">{s.title}</span>
                  <span className="text-muted-foreground text-[11.5px]">{s.note}</span>
                </Link>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </nav>

      <div className="flex shrink-0 items-center gap-2">
        {stopped && (
          <Link href="/business" title="The kill switch is on: nothing is sent and no money moves">
            <CanvasChip tone="bad" className="bg-white text-[#b71e1e] border-white">stopped</CanvasChip>
          </Link>
        )}
        <SystemStatus c={connection} />
        <UserMenu user={user} />
      </div>
    </header>
  );
}
