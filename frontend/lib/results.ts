import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Regression, Results } from "./types";

export * from "./types";

// Read at build time from the synced copy in public/, so the page is fully
// static and carries no runtime dependency on the Python pipeline.
export function loadResults(): Results {
  const path = join(process.cwd(), "public", "results", "results.json");
  return JSON.parse(readFileSync(path, "utf-8")) as Results;
}

export function regression(results: Results, label: string): Regression {
  const found = results.regressions.find((r) => r.label === label);
  if (!found) throw new Error(`No regression labelled ${label}`);
  return found;
}
