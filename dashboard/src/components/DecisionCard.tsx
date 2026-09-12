"use client";
import type { Decision } from "@/lib/types";

function describe(d: Decision): string {
  const i = d.input;
  const money = typeof i.amount === "number" ? ` $${(i.amount as number).toFixed(2)}` : "";
  switch (d.tool) {
    case "pay_bill": return `Pay ${i.vendor}${money} from ${i.account_id}`;
    case "schedule_appointment": return `Book ${i.for_member} with ${i.provider}, ${i.weekday} day ${i.day} at ${i.time}`;
    case "submit_form": return `Submit ${i.form_name}${typeof i.fee === "number" && i.fee ? `, fee $${(i.fee as number).toFixed(2)}` : ""}${i.requires_signature ? ", with your signature" : ""}`;
    default: return d.tool.replace(/_/g, " ");
  }
}

export default function DecisionCard({ d, busy, onDecide }: { d: Decision; busy: boolean; onDecide: (choice: "approve" | "trust" | "deny") => void }) {
  return (
    <article className="card" aria-labelledby={`${d.id}-t`}>
      <h4 id={`${d.id}-t`}>{d.title}</h4>
      <p className="why">{d.summary}</p>
      <div className="reason">Asking because {d.policy_reason}.</div>
      <div className="detail mono">{describe(d)}</div>
      <div className="actions">
        <button className="btn" disabled={busy} onClick={() => onDecide("approve")}>Approve</button>
        <button className="btn secondary" disabled={busy} onClick={() => onDecide("trust")}>Approve and trust from now on</button>
        <button className="btn quiet" disabled={busy} onClick={() => onDecide("deny")}>Decline</button>
      </div>
    </article>
  );
}
