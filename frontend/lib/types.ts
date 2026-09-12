export type Band = "<400 m" | "400–800 m" | "800 m–1.2 km" | "1.2–2 km" | "2–3 km" | "3–5 km" | ">5 km";

export const BAND_ORDER: Band[] = ["<400 m", "400–800 m", "800 m–1.2 km", "1.2–2 km", "2–3 km", "3–5 km", ">5 km"];
export const REFERENCE: Band = "1.2–2 km";

export type BandRow = {
  is_strata: boolean;
  band: Band;
  n: number;
  median: number;
  p25: number;
  p75: number;
  segment: "Strata (condo, flat)" | "Landed";
};

export type Effect = {
  n: number;
  premium_pct: number;
  ci_low_pct: number;
  ci_high_pct: number;
  p: number;
};

export type Regression = {
  label: string;
  n: number;
  r2: number;
  effects: Record<string, Effect>;
};

export type Results = {
  transactions_located: number;
  schemes_located: number;
  stations_used: number;
  median_distance_m: number;
  share_within_800m: number;
  bands: BandRow[];
  regressions: Regression[];
};
