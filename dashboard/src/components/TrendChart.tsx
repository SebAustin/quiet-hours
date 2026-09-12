"use client";
import type { State } from "@/lib/types";

/** Handled quietly vs. asked you, per day. Two categorical series, fixed hue order, direct labels. */
export default function TrendChart({ perDay }: { perDay: State["stats"]["per_day"] }) {
  const days = perDay.length ? perDay : [{ day: 1, handled: 0, asked: 0 }];
  const W = 420, H = 170, padL = 22, padB = 28, padT = 14;
  const max = Math.max(1, ...days.map((d) => Math.max(d.handled, d.asked)));
  const groupW = (W - padL) / days.length;
  const barW = Math.min(26, groupW / 3);
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / max);
  return (
    <div>
      <div className="legend" style={{ marginBottom: 8 }}>
        <span style={{ "--dot": "var(--chart-handled)" } as React.CSSProperties}>Handled quietly</span>
        <span style={{ "--dot": "var(--chart-asked)" } as React.CSSProperties}>Asked you</span>
      </div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Actions handled quietly versus decisions asked, per day">
        {[0.5, 1].map((f) => (
          <line key={f} className="grid" x1={padL} x2={W} y1={y(max * f)} y2={y(max * f)} strokeWidth={1} />
        ))}
        <line className="baseline" x1={padL} x2={W} y1={y(0)} y2={y(0)} strokeWidth={1} />
        {days.map((d, i) => {
          const cx = padL + groupW * i + groupW / 2;
          const bars = [
            { v: d.handled, color: "var(--chart-handled)", x: cx - barW - 1, label: "handled quietly" },
            { v: d.asked, color: "var(--chart-asked)", x: cx + 1, label: "asked you" },
          ];
          return (
            <g key={d.day}>
              {bars.map((b) => (
                <g key={b.label}>
                  <title>{`Day ${d.day}: ${b.v} ${b.label}`}</title>
                  <rect x={b.x} y={y(b.v)} width={barW} height={Math.max(0, y(0) - y(b.v))} rx={3} fill={b.color} />
                  {b.v > 0 && <text className="val" x={b.x + barW / 2} y={y(b.v) - 4} textAnchor="middle">{b.v}</text>}
                </g>
              ))}
              <text x={cx} y={H - 8} textAnchor="middle">Day {d.day}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
