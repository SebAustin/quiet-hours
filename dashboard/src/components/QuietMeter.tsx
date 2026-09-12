"use client";
import type { Item } from "@/lib/types";

const tileClass: Record<string, string> = { handled: "handled", snoozed: "handled", needs_decision: "asked", flagged: "flagged", new: "pending", in_progress: "pending" };
const tileTitle: Record<string, string> = { handled: "handled quietly", snoozed: "snoozed", needs_decision: "needs you", flagged: "flagged", new: "waiting for the next sweep", in_progress: "in progress" };

export default function QuietMeter({ items, day }: { items: Item[]; day: number }) {
  const today = items.filter((i) => i.received_day === day);
  return (
    <div className="meter" aria-label={`Today's items, ${today.length} in total`}>
      <span className="eyebrow">Today, item by item</span>
      <div className="meter-row">
        {today.length === 0 && <span className="status-line">Nothing has arrived yet.</span>}
        {today.map((i) => (
          <div key={i.id} className={`tile ${tileClass[i.status] ?? "pending"}`} title={`${i.subject} — ${tileTitle[i.status] ?? i.status}`} />
        ))}
      </div>
      <div className="legend">
        <span style={{ "--dot": "var(--sage)" } as React.CSSProperties}>Handled quietly</span>
        <span style={{ "--dot": "var(--lamp)" } as React.CSSProperties}>Needs you</span>
        <span style={{ "--dot": "var(--rose)" } as React.CSSProperties}>Flagged</span>
      </div>
    </div>
  );
}
