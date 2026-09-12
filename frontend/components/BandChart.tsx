"use client";

import { useState } from "react";
import { BAND_ORDER, type BandRow } from "@/lib/types";

const W = 640;
const H = 300;
const PAD = { top: 18, right: 18, bottom: 44, left: 68 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

type Segment = "Strata (condo, flat)" | "Landed";

/* Raw medians by distance band, one segment at a time. Showing one series
   sidesteps a two-hue palette entirely, and the toggle makes the contrast
   between strata and landed an action rather than a legend. */
export default function BandChart({ rows }: { rows: BandRow[] }) {
  const [segment, setSegment] = useState<Segment>("Strata (condo, flat)");
  const [hover, setHover] = useState<number | null>(null);

  const series = BAND_ORDER.map((band) => rows.find((r) => r.segment === segment && r.band === band)).filter(
    (r): r is BandRow => r !== undefined,
  );
  const allMax = Math.max(...rows.map((r) => r.p75));
  const yMax = Math.ceil(allMax / 2000) * 2000;

  const x = (i: number) => PAD.left + (i / (series.length - 1)) * PLOT_W;
  const y = (v: number) => PAD.top + (1 - v / yMax) * PLOT_H;

  const line = series.map((r, i) => `${i === 0 ? "M" : "L"}${x(i)} ${y(r.median)}`).join(" ");
  const area =
    series.map((r, i) => `${i === 0 ? "M" : "L"}${x(i)} ${y(r.p75)}`).join(" ") +
    " " +
    [...series].reverse().map((r, i) => `L${x(series.length - 1 - i)} ${y(r.p25)}`).join(" ") +
    " Z";
  const ticks = Array.from({ length: yMax / 2000 + 1 }, (_, i) => i * 2000);

  return (
    <div>
      <div className="mb-4 flex gap-2">
        {(["Strata (condo, flat)", "Landed"] as Segment[]).map((s) => (
          <button key={s} onClick={() => setSegment(s)} aria-pressed={segment === s} className="btn-pill">
            {s}
          </button>
        ))}
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          role="img"
          aria-label={`Median price per square metre by distance from the nearest rail station, ${segment}`}
          onMouseLeave={() => setHover(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--border-hairline)" />
              <text x={PAD.left - 10} y={y(t) + 4} textAnchor="end" fontSize={11} fontFamily="var(--font-jetbrains-mono)" fill="var(--text-label)">
                {t.toLocaleString()}
              </text>
            </g>
          ))}
          <path d={area} fill="var(--data)" opacity={0.1} />
          <path d={line} fill="none" stroke="var(--data)" strokeWidth={2} strokeLinejoin="round" />
          {series.map((r, i) => (
            <g key={r.band}>
              <circle cx={x(i)} cy={y(r.median)} r={r.n < 50 ? 5 : 4} fill={r.n < 50 ? "var(--surface-card)" : "var(--data)"} stroke="var(--data)" strokeWidth={2} />
              <rect x={x(i) - PLOT_W / series.length / 2} y={PAD.top} width={PLOT_W / series.length} height={PLOT_H} fill="transparent" onMouseEnter={() => setHover(i)} />
              <text x={x(i)} y={H - PAD.bottom + 18} textAnchor="middle" fontSize={11} fill="var(--text-label)">
                {r.band}
              </text>
            </g>
          ))}
          {hover !== null && (
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={H - PAD.bottom} stroke="var(--color-fog)" />
          )}
          <text x={PAD.left + PLOT_W / 2} y={H - 4} textAnchor="middle" fontSize={11} fill="var(--text-body)">
            Distance from nearest rail station
          </text>
          <text x={15} y={PAD.top + PLOT_H / 2} textAnchor="middle" fontSize={11} fill="var(--text-body)" transform={`rotate(-90 15 ${PAD.top + PLOT_H / 2})`}>
            Median RM per sq.m
          </text>
        </svg>

        {hover !== null && series[hover] && (
          <div
            className="mono pointer-events-none absolute px-2.5 py-1.5"
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-hairline)",
              borderRadius: "var(--radius)",
              boxShadow: "var(--shadow-lift)",
              color: "var(--text-heading)",
              fontSize: 11,
              left: `${(x(hover) / W) * 100}%`,
              top: `${(y(series[hover].median) / H) * 100}%`,
              transform: "translate(-50%, -125%)",
              whiteSpace: "nowrap",
            }}
          >
            RM {Math.round(series[hover].median).toLocaleString()} / sq.m
            <br />
            <span style={{ color: "var(--text-label)" }}>
              IQR {Math.round(series[hover].p25).toLocaleString()}–{Math.round(series[hover].p75).toLocaleString()} · n={series[hover].n.toLocaleString()}
            </span>
          </div>
        )}
      </div>
      <p style={{ fontSize: 12, color: "var(--text-label)", marginTop: 8 }}>
        Shaded band is the interquartile range. Hollow points rest on fewer than 50 sales.
      </p>
    </div>
  );
}
