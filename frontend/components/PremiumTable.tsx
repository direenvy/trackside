import { BAND_ORDER, REFERENCE, regression, type Effect, type Results } from "@/lib/results";

function Cell({ e }: { e: Effect | undefined }) {
  if (!e) return <td style={{ padding: "10px 0", textAlign: "right", color: "var(--text-label)" }}>—</td>;
  const clear = e.ci_low_pct > 0 || e.ci_high_pct < 0;
  const colour = !clear ? "var(--text-body)" : e.premium_pct > 0 ? "var(--data)" : "var(--accent)";
  return (
    <td className="tabular" style={{ padding: "10px 0", textAlign: "right" }}>
      <span style={{ fontWeight: clear ? 600 : 400, color: colour }}>
        {e.premium_pct > 0 ? "+" : ""}
        {e.premium_pct.toFixed(1)}%
      </span>
      <span className="mono" style={{ fontSize: 11, color: "var(--text-label)", marginLeft: 8 }}>
        [{e.ci_low_pct > 0 ? "+" : ""}{e.ci_low_pct.toFixed(1)}, {e.ci_high_pct > 0 ? "+" : ""}{e.ci_high_pct.toFixed(1)}]
      </span>
    </td>
  );
}

export default function PremiumTable({ results }: { results: Results }) {
  const strata = regression(results, "strata");
  const landed = regression(results, "landed");
  const head = {
    padding: "0 0 10px",
    fontSize: 12,
    fontWeight: 500,
    letterSpacing: "0.04em",
    textTransform: "uppercase" as const,
    color: "var(--text-label)",
  };
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="w-full" style={{ minWidth: 560 }}>
        <thead>
          <tr>
            <th style={{ ...head, textAlign: "left" }}>Distance to station</th>
            <th style={{ ...head, textAlign: "right" }}>Strata</th>
            <th style={{ ...head, textAlign: "right" }}>Landed</th>
          </tr>
        </thead>
        <tbody>
          {BAND_ORDER.map((band) => (
            <tr key={band} style={{ borderTop: "1px solid var(--border-hairline)" }}>
              <td style={{ padding: "10px 0", fontSize: 14, color: band === REFERENCE ? "var(--text-label)" : "var(--text-heading)" }}>
                {band}
                {band === REFERENCE && (
                  <span className="mono" style={{ marginLeft: 8, fontSize: 11, color: "var(--text-label)" }}>
                    reference
                  </span>
                )}
              </td>
              {band === REFERENCE ? (
                <>
                  <td style={{ padding: "10px 0", textAlign: "right", color: "var(--text-label)" }}>0</td>
                  <td style={{ padding: "10px 0", textAlign: "right", color: "var(--text-label)" }}>0</td>
                </>
              ) : (
                <>
                  <Cell e={strata.effects[band]} />
                  <Cell e={landed.effects[band]} />
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 12, color: "var(--text-label)", marginTop: 12, lineHeight: 1.5 }}>
        Premium on price per square metre against the 1.2–2 km band, holding mukim, property type,
        tenure, year, unit size and (strata) floor level fixed. Bold where the 95% interval excludes
        zero. Strata n = {strata.n.toLocaleString()}, landed n = {landed.n.toLocaleString()}.
      </p>
    </div>
  );
}
