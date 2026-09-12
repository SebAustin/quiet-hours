"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { State } from "@/lib/types";
import QuietMeter from "./QuietMeter";
import DecisionCard from "./DecisionCard";
import Timeline from "./Timeline";
import TrendChart from "./TrendChart";
import AskBox from "./AskBox";

function headline(s: State): { title: React.ReactNode; sub: string } {
  const pending = s.stats.pending;
  const today = s.items.filter((i) => i.received_day === s.clock);
  const handled = today.filter((i) => i.status === "handled" || i.status === "snoozed").length;
  const flagged = today.filter((i) => i.status === "flagged").length;
  const waiting = today.filter((i) => i.status === "new").length;
  if (s.clock === 0) return { title: <>The house is <em>quiet</em>.</>, sub: "Start the demo household to see a day of mail arrive." };
  if (waiting) return { title: <>{waiting} new thing{waiting > 1 ? "s" : ""} arrived. <em>Sweeping soon.</em></>, sub: "The next background sweep will sort them. Or run one now." };
  if (pending === 0) return { title: <>Everything handled. <em>Nothing needs you.</em></>, sub: `${handled} done quietly today${flagged ? `, ${flagged} blocked as suspicious` : ""}. Enjoy the evening.` };
  return {
    title: <>{handled} handled quietly. <em>{pending} need{pending === 1 ? "s" : ""} you.</em></>,
    sub: `${flagged ? `${flagged} blocked as suspicious. ` : ""}Each card below is one real decision, with the reason it was not made for you.`,
  };
}

export default function Dashboard() {
  const params = useSearchParams();
  const [state, setState] = useState<State | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setState(await api.state());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the household state.");
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 12000);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    const decided = params.get("decided");
    if (decided) {
      const choice = params.get("choice");
      const status = params.get("status");
      setToast(status === "ok" ? `Got it — ${choice === "trust" ? "approved and trusted from now on" : choice === "deny" ? "declined" : "approved"}.` : "That link did not go through. The card is still below.");
      window.history.replaceState(null, "", "/");
    }
  }, [params]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(t);
  }, [toast]);

  async function run(label: string, fn: () => Promise<unknown>, done: string) {
    setBusy(label);
    try {
      await fn();
      setToast(done);
      await refresh();
    } catch (e) {
      setToast(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  const pending = useMemo(() => (state?.decisions ?? []).filter((d) => d.status === "pending"), [state]);
  const head = state ? headline(state) : null;

  return (
    <main className="shell">
      <header className="top">
        <div className="brand">
          <h1 className="display">Quiet Hours</h1>
          <span className="tag">{state?.profile?.household ?? "Household autopilot"}{state?.profile?.city ? ` · ${state.profile.city}` : ""}</span>
        </div>
        <div className="demo" aria-label="Demo controls">
          <span className="eyebrow">Demo · day {state?.clock ?? 0}</span>
          <button className="ghost" disabled={!!busy} onClick={() => run("advance", () => api.simulate("advance"), "A new day of mail arrived.")}>{busy === "advance" ? "Advancing…" : "Next day"}</button>
          <button className="ghost" disabled={!!busy} onClick={() => run("sweep", () => api.sweep(), "Sweep finished.")}>{busy === "sweep" ? "Sweeping…" : "Run sweep now"}</button>
          <button className="ghost" disabled={!!busy} onClick={() => run("reset", () => api.simulate("reset"), "Household reset to day 0.")}>Start over</button>
        </div>
      </header>

      <section className="hero" aria-labelledby="hero-h">
        <div>
          <h2 id="hero-h" className="display">{head?.title ?? "Loading the household…"}</h2>
          <p>{head?.sub ?? (error ?? "")}</p>
          {error && <p className="status-line">{error}</p>}
        </div>
        {state && <QuietMeter items={state.items} day={state.clock} />}
      </section>

      <section className="columns">
        <div>
          <div className="section-h"><h3 className="display">Needs you</h3><span className="count">{pending.length} pending</span></div>
          <div className="cards">
            {pending.length === 0 && (
              <div className="empty"><strong>Nothing needs you.</strong>Routine things get handled in the background. You only see the ones that are truly your call.</div>
            )}
            {pending.map((d) => (
              <DecisionCard key={d.id} d={d} busy={busy === d.id} onDecide={(choice) => run(d.id, () => api.decide(d.id, choice), choice === "trust" ? "Approved and trusted from now on." : choice === "deny" ? "Declined." : "Approved.")} />
            ))}
          </div>
        </div>
        <div>
          <div className="section-h"><h3 className="display">Handled quietly</h3><span className="count">{state?.stats.handled_quietly ?? 0} on its own</span></div>
          {state && <Timeline actions={state.actions} items={state.items} />}
        </div>
      </section>

      <section className="bottom">
        <div className="panel">
          <h3 className="display">Interruptions, day by day</h3>
          {state && <TrendChart perDay={state.stats.per_day} />}
        </div>
        <div className="panel">
          <h3 className="display">Standing permissions</h3>
          {state && state.trust_rules.length === 0 && <div className="status-line">None yet. Choose “Approve and trust” on a card and it lands here.</div>}
          <ul className="rules">
            {state?.trust_rules.map((r) => (
              <li key={r.id}>
                {r.tool.replace(/_/g, " ")} <span>{r.vendor ? `for ${r.vendor}` : "any vendor"}{typeof r.max_amount === "number" ? ` up to $${r.max_amount.toFixed(0)}` : ""}</span>
              </li>
            ))}
          </ul>
        </div>
        <AskBox />
      </section>
      {toast && <div className="toast" role="status">{toast}</div>}
    </main>
  );
}
