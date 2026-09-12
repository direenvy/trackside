import { regression, type Results } from "@/lib/results";

const ROWS = [
  { label: "Strata · Kuala Lumpur", key: "strata_kl_only", strata: true },
  { label: "Strata · Selangor & Putrajaya", key: "strata_selangor_putrajaya", strata: true },
  { label: "Landed · Kuala Lumpur", key: "landed_kl_only", strata: false },
  { label: "Landed · Selangor & Putrajaya", key: "landed_selangor_putrajaya", strata: false },
];

const W = 640;
const ROW_H = 54;
const PAD = { top: 12, right: 70, bottom: 36, left: 216 };
const H = PAD.top + ROWS.length * ROW_H + PAD.bottom;
const PLOT_W = W - PAD.left - PAD.right;
const X_MIN = -4;
const X_MAX = 16;

const x = (pct: number) => PAD.left + ((pct - X_MIN) / (X_MAX - X_MIN)) * PLOT_W;

/* The headline: the same estimate, split by territory and segment. Each row
   is text-labelled, so colour is a redundant cue rather than the only one. */
export default function TerritoryChart({ results }: { results: Results }) {
  const ticks = [0, 5, 10, 15];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label="Price premium within 400 metres of a station, by territory and property segment, with 95% intervals"
    >
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={PAD.top} y2={H - PAD.bottom} stroke={t === 0 ? "var(--color-fog)" : "var(--border-hairline)"} strokeWidth={1} />
          <text x={x(t)} y={H - PAD.bottom + 18} textAnchor="middle" fontSize={11} fontFamily="var(--font-jetbrains-mono)" fill="var(--text-label)">
            {t > 0 ? "+" : ""}{t}%
          </text>
        </g>
      ))}

      {ROWS.map((row, i) => {
        const e = regression(results, row.key).effects["<400 m"];
        const y = PAD.top + i * ROW_H + ROW_H / 2;
        const colour = row.strata ? "var(--data)" : "var(--color-indigo-navy)";
        const clear = e.ci_low_pct > 0;
        return (
          <g key={row.key}>
            <text x={PAD.left - 14} y={y + 4} textAnchor="end" fontSize={13} fill="var(--text-heading)">
              {row.label}
            </text>
            <line x1={x(e.ci_low_pct)} x2={x(e.ci_high_pct)} y1={y} y2={y} stroke={colour} strokeWidth={2.5} strokeLinecap="round" />
            <circle cx={x(e.premium_pct)} cy={y} r={6} fill={clear ? colour : "var(--surface-card)"} stroke={colour} strokeWidth={2.5} />
            <text x={x(e.ci_high_pct) + 10} y={y + 4} fontSize={13} fontWeight={600} fontFamily="var(--font-jetbrains-mono)" fill={colour}>
              {e.premium_pct > 0 ? "+" : ""}{e.premium_pct.toFixed(1)}%
            </text>
          </g>
        );
      })}

      <text x={PAD.left + PLOT_W / 2} y={H - 4} textAnchor="middle" fontSize={11} fill="var(--text-body)">
        Premium within 400 m of a station vs. 1.2–2 km away, after controls
      </text>
    </svg>
  );
}
