import type { Offering, Profile } from "@/app/lib";

/* Profile defaults, shared by the server pages and the client editor. */

export function emptyProfile(): Profile {
  return {
    name: "", mission: "", language: "en", offerings: [], customers: "",
    channels: ["web_checkout", "email"], goals: [],
    team: { preset: "auto", include: [], exclude: [], extra_roles: [] },
    constraints: {
      autonomous_spend_usd: { per_payment: 5, per_day: 20 },
      inference_max_usd_per_day: 3, min_price_usd: 0,
      forbidden: [], approval_required: ["refund", "new_vendor"],
    },
    revenue_split: [], privacy: { sensitive: [], tee_only: true }, kill_switch: false,
  };
}

/** A partial profile (a model's draft, an older version) with every field present. */
export function completeProfile(raw: Partial<Profile> | null | undefined): Profile {
  const e = emptyProfile();
  const r = raw ?? {};
  return {
    ...e, ...r,
    offerings: (r.offerings ?? []).map((o) => ({ ...emptyOffering(), ...o, inputs: o.inputs ?? [] })),
    channels: r.channels ?? e.channels,
    goals: r.goals ?? [],
    team: { ...e.team, ...(r.team ?? {}) },
    constraints: {
      ...e.constraints, ...(r.constraints ?? {}),
      autonomous_spend_usd: { ...e.constraints.autonomous_spend_usd, ...(r.constraints?.autonomous_spend_usd ?? {}) },
      forbidden: r.constraints?.forbidden ?? [],
      approval_required: r.constraints?.approval_required ?? e.constraints.approval_required,
    },
    revenue_split: r.revenue_split ?? [],
    privacy: { ...e.privacy, ...(r.privacy ?? {}) },
  };
}

export const emptyOffering = (): Offering => ({
  id: "", title: "", description: "", price_usd: 10, delivery: "pdf", sla_hours: 24, inputs: [],
});

