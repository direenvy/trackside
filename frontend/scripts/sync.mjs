// Copy the pipeline's outputs into public/ so the page is a pure static build
// with no dependency on the Python side at runtime.
import { cpSync, mkdirSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const outputs = resolve(import.meta.dirname, "../../pipeline/outputs");
const target = resolve(import.meta.dirname, "../public/results");
if (!existsSync(outputs)) {
  console.error(`No pipeline outputs at ${outputs} — run pipeline/04_analyse.py first.`);
  process.exit(1);
}
mkdirSync(target, { recursive: true });
cpSync(resolve(outputs, "results.json"), resolve(target, "results.json"));
cpSync(resolve(outputs, "figures"), resolve(target, "figures"), { recursive: true });
console.log("synced pipeline outputs into public/results");
