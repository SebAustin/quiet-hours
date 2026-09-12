"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function AskBox() {
  const [q, setQ] = useState("");
  const [a, setA] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim() || busy) return;
    setBusy(true);
    setA(null);
    try {
      const r = await api.chat(q.trim());
      setA(r.response ?? r.error ?? "No answer.");
    } catch (err) {
      setA(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="panel ask">
      <h3>Ask Quiet Hours</h3>
      <form onSubmit={submit}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Why did you pay the water bill?" aria-label="Ask Quiet Hours a question" />
        <button className="ghost" type="submit" disabled={busy}>{busy ? "Thinking…" : "Ask"}</button>
      </form>
      {a && <div className="answer">{a}</div>}
    </div>
  );
}
