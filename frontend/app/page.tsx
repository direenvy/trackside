import BandChart from "@/components/BandChart";
import Nav from "@/components/Nav";
import PremiumTable from "@/components/PremiumTable";
import TerritoryChart from "@/components/TerritoryChart";
import { loadResults, regression } from "@/lib/results";

function Stat({ value, label, note }: { value: string; label: string; note: string }) {
  return (
    <div>
      <div className="tabular" style={{ fontSize: 28, lineHeight: 1.1, letterSpacing: "-0.28px", fontWeight: 500, color: "var(--data)" }}>
        {value}
      </div>
      <div style={{ fontSize: 14, color: "var(--text-label)", marginTop: 6 }}>{label}</div>
      <div style={{ fontSize: 12, color: "var(--text-label)", marginTop: 2 }}>{note}</div>
    </div>
  );
}

function Panel({ id, children }: { id?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="card" style={{ padding: "var(--card-padding)" }}>
      {children}
    </section>
  );
}

export default function Home() {
  const results = loadResults();
  const strataSel = regression(results, "strata_selangor_putrajaya").effects;
  const landedSel = regression(results, "landed_selangor_putrajaya").effects;
  const robustGeo = regression(results, "strata_scheme_level_only").effects;
  const robustYear = regression(results, "strata_2022_onward").effects;
  const pct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

  return (
    <>
      <Nav />

      <main className="mx-auto w-full px-6 lg:px-16" style={{ maxWidth: "var(--page-max-width)" }}>
        <header style={{ paddingTop: 64, paddingBottom: 48 }}>
          <span className="tag">Data analysis</span>
          <h1 className="display" style={{ marginTop: 20, maxWidth: 760 }}>
            Does a rail station nearby raise property prices?
          </h1>
          <p style={{ fontSize: 18, lineHeight: 1.33, color: "var(--text-body)", marginTop: 20, maxWidth: 620 }}>
            Yes — but almost entirely in the suburbs. {results.transactions_located.toLocaleString()} registered
            Klang Valley transactions, {results.stations_used} stations, and a regression that holds neighbourhood,
            property type, tenure, year, size and floor level fixed.
          </p>
        </header>

        <Panel>
          <h2 className="subheading-sm">The station premium is a suburban phenomenon</h2>
          <p style={{ fontSize: 14, color: "var(--text-body)", marginTop: 8, marginBottom: 20, maxWidth: 640 }}>
            The same estimate, split by territory. Inside Kuala Lumpur the intervals straddle zero. In Selangor
            and Putrajaya a strata unit within 400 m of a station sells for {pct(strataSel["<400 m"].premium_pct)} more
            than an equivalent one 1.2–2 km away, and a landed home {pct(landedSel["<400 m"].premium_pct)} more.
          </p>
          <TerritoryChart results={results} />
        </Panel>

        <div className="grid grid-cols-2 gap-x-12 gap-y-8 lg:grid-cols-4" style={{ marginTop: 48 }}>
          <Stat value={pct(strataSel["<400 m"].premium_pct)} label="Strata, within 400 m" note="Selangor & Putrajaya, vs 1.2–2 km" />
          <Stat value={pct(strataSel[">5 km"].premium_pct)} label="Strata, beyond 5 km" note="Selangor & Putrajaya, vs 1.2–2 km" />
          <Stat value={pct(landedSel["<400 m"].premium_pct)} label="Landed, within 400 m" note="Selangor & Putrajaya, vs 1.2–2 km" />
          <Stat value={pct(landedSel[">5 km"].premium_pct)} label="Landed, beyond 5 km" note="Selangor & Putrajaya, vs 1.2–2 km" />
        </div>

        <section style={{ paddingTop: "var(--section-gap)" }}>
          <span className="tag">Across the whole region</span>
          <h2 className="subheading" style={{ marginTop: 16, marginBottom: 8 }}>
            Every band, both segments
          </h2>
          <p style={{ fontSize: 16, color: "var(--text-body)", marginBottom: 32, maxWidth: 620 }}>
            Pooled across Kuala Lumpur, Selangor and Putrajaya. Strata declines smoothly with distance. Landed is a
            step: a sharp premium at walking distance, a flat middle, then a drop beyond 5 km — for a house, what
            seems to matter is whether the station is walkable at all.
          </p>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel>
              <h3 className="subheading-sm">What proximity is worth, after controls</h3>
              <div style={{ marginTop: 16 }}>
                <PremiumTable results={results} />
              </div>
            </Panel>
            <Panel>
              <h3 className="subheading-sm">What the market actually paid</h3>
              <p style={{ fontSize: 14, color: "var(--text-body)", marginTop: 8, marginBottom: 16 }}>
                Raw medians, before any controls. Hover for the interquartile range and sale count.
              </p>
              <BandChart rows={results.bands} />
            </Panel>
          </div>
        </section>

        <section id="method" style={{ paddingTop: "var(--section-gap)" }}>
          <span className="tag">Method</span>
          <h2 className="subheading" style={{ marginTop: 16, marginBottom: 8 }}>
            How the number was made, and what it survives
          </h2>
          <div className="grid gap-6 lg:grid-cols-2" style={{ marginTop: 32 }}>
            <Panel>
              <h3 className="subheading-sm">Three sources, joined</h3>
              <dl style={{ marginTop: 16, fontSize: 14, color: "var(--text-body)", display: "grid", gap: 14 }}>
                <div>
                  <dt style={{ fontWeight: 500, color: "var(--text-heading)" }}>Transactions</dt>
                  <dd style={{ marginTop: 2 }}>
                    NAPIC Open Sales Data — the government registry of completed residential sales, January 2021 to
                    June 2026. Pivot-shaped Excel exports, forward-filled, cleaned and trimmed.
                  </dd>
                </div>
                <div>
                  <dt style={{ fontWeight: 500, color: "var(--text-heading)" }}>Stations</dt>
                  <dd style={{ marginTop: 2 }}>
                    {results.stations_used} Klang Valley rail stations scraped from Wikipedia — the list page, then each
                    station&apos;s article for its coordinates — at one request per second with a disk cache.
                  </dd>
                </div>
                <div>
                  <dt style={{ fontWeight: 500, color: "var(--text-heading)" }}>Locations</dt>
                  <dd style={{ marginTop: 2 }}>
                    {results.schemes_located.toLocaleString()} schemes geocoded through OpenStreetMap after a normaliser
                    expanded NAPIC&apos;s abbreviations (TMN, KG, KAW). {Math.round(results.share_within_800m * 100)}% of
                    located homes sit within 800 m of a station; the median is {(results.median_distance_m / 1000).toFixed(1)} km.
                  </dd>
                </div>
              </dl>
            </Panel>
            <Panel>
              <h3 className="subheading-sm">Robustness</h3>
              <p style={{ fontSize: 14, color: "var(--text-body)", marginTop: 8 }}>
                The strata estimate, within 400 m and beyond 5 km, under the two changes most likely to break it.
              </p>
              <table className="tabular w-full" style={{ marginTop: 16 }}>
                <thead>
                  <tr style={{ fontSize: 12, color: "var(--text-label)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    <th style={{ textAlign: "left", paddingBottom: 10, fontWeight: 500 }}>Sample</th>
                    <th style={{ textAlign: "right", paddingBottom: 10, fontWeight: 500 }}>&lt; 400 m</th>
                    <th style={{ textAlign: "right", paddingBottom: 10, fontWeight: 500 }}>&gt; 5 km</th>
                  </tr>
                </thead>
                <tbody style={{ fontSize: 14 }}>
                  {[
                    ["All located strata", regression(results, "strata").effects],
                    ["Scheme-level geocodes only", robustGeo],
                    ["2022 onward (no pandemic year)", robustYear],
                  ].map(([name, e]) => (
                    <tr key={name as string} style={{ borderTop: "1px solid var(--border-hairline)" }}>
                      <td style={{ padding: "10px 0" }}>{name as string}</td>
                      <td style={{ padding: "10px 0", textAlign: "right", color: "var(--data)", fontWeight: 600 }}>
                        {pct((e as Record<string, { premium_pct: number }>)["<400 m"].premium_pct)}
                      </td>
                      <td style={{ padding: "10px 0", textAlign: "right", color: "var(--accent)", fontWeight: 600 }}>
                        {pct((e as Record<string, { premium_pct: number }>)[">5 km"].premium_pct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ fontSize: 12, color: "var(--text-label)", marginTop: 16, lineHeight: 1.5 }}>
                This is what the market pays for proximity, not what a station would do to prices. Stations were built
                where people already were; the mukim fixed effect absorbs the coarse neighbourhood, not the fine grain.
              </p>
            </Panel>
          </div>
        </section>

        <section style={{ paddingTop: "var(--section-gap)" }}>
          <Panel>
            <h3 className="subheading-sm">Where the homes are, and where the stations are</h3>
            <p style={{ fontSize: 14, color: "var(--text-body)", marginTop: 8, marginBottom: 16 }}>
              Every located scheme, coloured by its median price per square metre, with stations in orange.
            </p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/results/figures/map.png" alt="Map of geocoded schemes across the Klang Valley coloured by price percentile, with rail stations overlaid" style={{ width: "100%", borderRadius: "var(--radius)" }} />
          </Panel>
        </section>

        <footer style={{ marginTop: "var(--section-gap)", paddingTop: 32, paddingBottom: 64, borderTop: "1px solid var(--border-hairline)", fontSize: 12, lineHeight: 1.5, color: "var(--text-label)", maxWidth: 720 }}>
          Transactions: National Property Information Centre (NAPIC), Open Sales Data. Stations: Wikipedia, CC BY-SA 4.0.
          Geocoding: © OpenStreetMap contributors via Nominatim, ODbL. The original plan used rental listings from
          Mudah.my; its Terms of Use prohibit scraping, so the project uses the official registry instead.
        </footer>
      </main>
    </>
  );
}
