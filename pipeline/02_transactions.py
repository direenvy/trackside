"""Load NAPIC Open Sales Data exports into one clean transaction table.

NAPIC's Excel export is pivot-shaped: a value that repeats the row above is
left blank, so five identity columns and the date all need forward-filling
before the rows mean anything on their own. Prices arrive as "RM1,600,000.00".
For strata units the parcel area sits in the land column and floor area is
empty; for landed property it is the reverse. This module untangles all of
that and writes a single parquet.

Run:  python 02_transactions.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw" / "napic"
OUT = HERE / "data" / "transactions.parquet"

COLUMNS = [
    "ptype", "district", "mukim", "scheme", "road", "date", "tenure",
    "land_area", "land_unit", "floor_area", "floor_unit", "level", "price",
]
# Columns the export blanks when they repeat the previous row.
GROUPED = ["ptype", "district", "mukim", "scheme", "road", "date"]

STRATA = {"Condominium/Apartment", "Flat", "Low-Cost Flat", "Town House"}

# Klang Valley: Kuala Lumpur, Putrajaya, and the Selangor districts that the
# rail network actually reaches. Sabak Bernam and Hulu Selangor are Selangor
# but nowhere near a station, so they would only add noise to the far tail.
KLANG_VALLEY = {
    "Kuala Lumpur", "Putrajaya",
    "Petaling", "Gombak", "Hulu Langat", "Klang", "Sepang", "Kuala Langat", "Kuala Selangor",
}


def load_one(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path)
    if len(frame.columns) != len(COLUMNS):
        raise SystemExit(f"{path.name}: expected {len(COLUMNS)} columns, found {len(frame.columns)}: {list(frame.columns)}")
    frame.columns = COLUMNS
    frame[GROUPED] = frame[GROUPED].ffill()
    frame["source_file"] = path.name
    return frame


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()

    out["price"] = (
        out["price"].astype(str).str.replace(r"[RM,\s]", "", regex=True).pipe(pd.to_numeric, errors="coerce")
    )
    out["date"] = pd.to_datetime(out["date"], format="%B %Y", errors="coerce")
    out["year"] = out["date"].dt.year
    out["land_area"] = pd.to_numeric(out["land_area"], errors="coerce")
    out["floor_area"] = pd.to_numeric(out["floor_area"], errors="coerce")
    out["level"] = pd.to_numeric(out["level"], errors="coerce")

    out["is_strata"] = out["ptype"].isin(STRATA)
    # The size that price is naturally quoted against: the parcel for a strata
    # unit, the built-up floor area for a landed house.
    out["area_sqm"] = out["land_area"].where(out["is_strata"], out["floor_area"])
    out["price_per_sqm"] = out["price"] / out["area_sqm"]

    for column in ["scheme", "road", "mukim", "district"]:
        out[column] = out[column].astype(str).str.strip().str.upper().replace({"NAN": None, "": None})
    out["district"] = out["district"].str.title()

    before = len(out)
    out = out[out["district"].isin(KLANG_VALLEY)]
    dropped_geo = before - len(out)

    # Rows that cannot support a price-per-area comparison are dropped, and the
    # extreme tails are trimmed rather than modelled: a RM 17,000 "sale" or a
    # RM 300,000 per sq.m entry is a data-entry artefact, not a market signal.
    usable = out["price"].notna() & out["area_sqm"].notna() & (out["area_sqm"] > 10) & (out["price"] > 10_000)
    out = out[usable]
    low, high = out["price_per_sqm"].quantile([0.005, 0.995])
    trimmed = out[(out["price_per_sqm"] >= low) & (out["price_per_sqm"] <= high)]

    print(f"  outside Klang Valley: {dropped_geo}")
    print(f"  unusable price/area:  {int((~usable).sum())}")
    print(f"  tail-trimmed (0.5% each side, RM/sq.m {low:,.0f} to {high:,.0f}): {len(out) - len(trimmed)}")
    return trimmed.reset_index(drop=True)


def main() -> None:
    files = sorted(RAW.glob("*.xlsx")) + sorted(RAW.glob("*.xls")) + sorted(RAW.glob("*.csv"))
    if not files:
        raise SystemExit(f"No NAPIC exports in {RAW}. Download them from the Open Sales Data page first.")

    frames = []
    for path in files:
        frame = load_one(path) if path.suffix != ".csv" else pd.read_csv(path)
        print(f"{path.name}: {len(frame):,} rows")
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    print(f"combined: {len(raw):,} rows\n")

    print("cleaning:")
    table = clean(raw)
    table.to_parquet(OUT, index=False)

    print(f"\nwrote {OUT}: {len(table):,} transactions")
    print(f"  {table['date'].min().date()} to {table['date'].max().date()}")
    print(f"  {table['scheme'].nunique():,} distinct schemes across {table['district'].nunique()} districts")
    print("  by district:")
    print(table["district"].value_counts().to_string())
    print("  by type:")
    print(table["ptype"].value_counts().head(8).to_string())


if __name__ == "__main__":
    main()
