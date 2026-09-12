export type ItemStatus = "new" | "in_progress" | "handled" | "needs_decision" | "snoozed" | "flagged";
export type DecisionStatus = "pending" | "approved" | "denied" | "trusted" | "expired";

export interface Item {
  id: string; source: string; received_day: number; sender: string; subject: string; vendor?: string | null;
  amount?: number | null; due_date?: string | null; category?: string | null; status: ItemStatus; outcome?: string | null;
  triage_notes?: string | null;
}
export interface Action {
  id: string; item_id?: string | null; tool: string; input: Record<string, unknown>; outcome: string;
  mode: "autonomous" | "approved" | "denied" | "trusted"; policy_reason: string; at: string; sim_day?: number | null;
}
export interface Decision {
  id: string; item_id: string; category: string; tool: string; input: Record<string, unknown>; title: string; summary: string;
  policy_reason: string; status: DecisionStatus; created_at: string; resolved_at?: string | null; response?: string | null; sim_day?: number | null;
}
export interface TrustRule { id: string; tool: string; vendor?: string | null; max_amount?: number | null; created_at: string; note?: string | null }
export interface Digest { at: string; sim_day: number; handled: string[]; escalated: string[]; flagged: string[]; narrative: string }
export interface State {
  clock: number; profile: { household?: string; city?: string; preferences?: Record<string, unknown> };
  digest: Digest | null; items: Item[]; actions: Action[]; decisions: Decision[]; trust_rules: TrustRule[];
  stats: { pending: number; handled_quietly: number; flagged: number; per_day: { day: number; handled: number; asked: number }[] };
}
