"use client";
import type { Action, Item } from "@/lib/types";

function declined(a: Action): string {
  const i = a.input;
  const money = typeof i.amount === "number" ? ` $${(i.amount as number).toFixed(2)}` : "";
  if (a.tool === "pay_bill") return `Declined: pay ${i.vendor}${money}`;
  if (a.tool === "schedule_appointment") return `Declined: book ${i.for_member} with ${i.provider}`;
  if (a.tool === "submit_form") return `Declined: submit ${String(i.form_name ?? "form").replace(/_/g, " ")}`;
  return `Declined: ${a.tool.replace(/_/g, " ")}`;
}

const verbs: Record<string, string> = { pay_bill: "Paid", schedule_appointment: "Booked", submit_form: "Submitted", reschedule_delivery: "Rescheduled", report_suspicious: "Flagged", snooze: "Snoozed", mark_handled: "Closed" };

export default function Timeline({ actions, items }: { actions: Action[]; items: Item[] }) {
  const byId = new Map(items.map((i) => [i.id, i]));
  const rows = [...actions].reverse();
  if (!rows.length) return <div className="empty"><strong>Nothing yet.</strong>Run a sweep and the quiet work shows up here.</div>;
  return (
    <div className="timeline-wrap">
    <ol className="timeline">
      {rows.map((a) => {
        const item = a.item_id ? byId.get(a.item_id) : undefined;
        const cls = a.mode === "autonomous" ? (a.tool === "report_suspicious" ? "flagged" : "") : a.mode;
        return (
          <li key={a.id} className={cls}>
            <div className="day">Day {a.sim_day ?? "–"}</div>
            <div className="what">
              {a.mode === "denied" ? declined(a) : a.outcome || `${verbs[a.tool] ?? a.tool} ${item?.vendor ?? ""}`}
              {a.mode !== "autonomous" && <span className={`badge ${a.mode}`}>{a.mode === "trusted" ? "you trusted this" : a.mode === "approved" ? "you approved" : "you declined"}</span>}
              {a.tool === "report_suspicious" && <span className="badge flagged">blocked</span>}
            </div>
            <div className="because">{a.mode === "autonomous" || a.mode === "trusted" ? `On its own: ${a.policy_reason}` : a.policy_reason}</div>
          </li>
        );
      })}
    </ol>
    </div>
  );
}
