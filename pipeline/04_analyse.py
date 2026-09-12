"""Join transactions to stations and measure the proximity premium.

For every transaction: locate its scheme, find the nearest rail station, and
record the distance. Then answer the question two ways — first descriptively
(median price per square metre by distance band), then with a regression that
holds property type, tenure, year, floor level and district constant so the
distance coefficient is not just "central Kuala Lumpur costs more".

Run:  python 04_analyse.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.spatial import cKDTree

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "outputs"
FIGURES = OUT / "figures"

# Column design tokens, so the figures match the rest of the portfolio.
NAVY, SEAFOAM, ORANGE, STEEL, HAIRLINE, CANVAS = "#111a4a", "#167e6c", "#ec652b", "#7c7f88", "#e3e4e8", "#f6f6f8"

# Distance bands in metres. 400 m is roughly a five-minute walk, the figure
# transit planners usually treat as a station's catchment.
BANDS = [0, 400, 800, 1200, 2000, 3000, 5000, np.inf]
BAND_LABELS = ["<400 m", "400–800 m", "800 m–1.2 km", "1.2–2 km", "2–3 km", "3–5 km", ">5 km"]
EARTH_RADIUS_M = 6_371_000


def to_metres(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Equirectangular projection onto a local plane. The Klang Valley spans
    about a degree, so the distortion is well under a percent — fine for a
    nearest-neighbour search, which is then re-measured with haversine."""
    lat0 = np.deg2rad(3.1)
    x = np.deg2rad(lon) * np.cos(lat0) * EARTH_RADIUS_M
    y = np.deg2rad(lat) * EARTH_RADIUS_M
    return np.column_stack([x, y])


def haversine(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(np.deg2rad, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    transactions = pd.read_parquet(DATA / "transactions.parquet")
    coords = pd.read_csv(DATA / "scheme_coords.csv")
    stations = pd.read_csv(DATA / "stations.csv").dropna(subset=["lat", "lon"])
    # Only stations that were open for at least part of the transaction window
    # can plausibly have priced in; the rest are dropped from the search.
    stations["opened_year"] = pd.to_numeric(stations["opened"].astype(str).str.extract(r"(\d{4})")[0], errors="coerce")
    stations = stations[stations["opened_year"].fillna(0) <= transactions["year"].max()]

    located = coords.dropna(subset=["lat", "lon"])
    frame = transactions.merge(located, on=["scheme", "mukim", "district"], how="inner")
    print(f"{len(transactions):,} transactions, {len(frame):,} with a located scheme "
          f"({len(frame) / len(transactions):.0%}); {len(stations)} stations open in the window")
    return frame, stations


def attach_nearest_station(frame: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    tree = cKDTree(to_metres(stations["lat"].to_numpy(), stations["lon"].to_numpy()))
    _, index = tree.query(to_metres(frame["lat"].to_numpy(), frame["lon"].to_numpy()))
    nearest = stations.iloc[index].reset_index(drop=True)
    out = frame.reset_index(drop=True)
    out["station"] = nearest["name"].to_numpy()
    out["station_operator"] = nearest["operator"].to_numpy()
    out["distance_m"] = haversine(out["lat"], out["lon"], nearest["lat"].to_numpy(), nearest["lon"].to_numpy())
    out["band"] = pd.cut(out["distance_m"], BANDS, labels=BAND_LABELS, right=False)
    out["log_price_sqm"] = np.log(out["price_per_sqm"])
    out["log_area"] = np.log(out["area_sqm"])
    out["near_400"] = (out["distance_m"] < 400).astype(int)
    out["near_800"] = (out["distance_m"] < 800).astype(int)
    out["log_distance"] = np.log(out["distance_m"].clip(lower=50))
    return out


def describe(frame: pd.DataFrame) -> pd.DataFrame:
    table = (
        frame.groupby(["is_strata", "band"], observed=True)["price_per_sqm"]
        .agg(n="size", median="median", p25=lambda s: s.quantile(0.25), p75=lambda s: s.quantile(0.75))
        .reset_index()
    )
    table["segment"] = np.where(table["is_strata"], "Strata (condo, flat)", "Landed")
    return table


def regress(frame: pd.DataFrame, label: str, treatment: str = "band") -> dict:
    """Log price per sq.m on distance, controlling for the things that also
    move price. Robust (HC1) standard errors — the residual spread differs a
    lot between a low-cost flat and a detached house."""
    if treatment == "band":
        formula = ("log_price_sqm ~ C(band, Treatment(reference='1.2–2 km')) + C(ptype) + C(tenure) "
                   "+ C(year) + C(mukim) + log_area")
    elif treatment == "log_distance":
        formula = "log_price_sqm ~ log_distance + C(ptype) + C(tenure) + C(year) + C(mukim) + log_area"
    else:
        formula = f"log_price_sqm ~ {treatment} + C(ptype) + C(tenure) + C(year) + C(mukim) + log_area"
    if frame["is_strata"].all():
        formula += " + level"
        frame = frame.dropna(subset=["level"])
    # An empty band would enter the design matrix as an all-zero column and
    # produce a meaningless coefficient, so drop levels with no rows.
    frame = frame.copy()
    frame["band"] = frame["band"].cat.remove_unused_categories()
    band_counts = frame["band"].value_counts()

    model = smf.ols(formula, data=frame).fit(cov_type="HC1")
    params = model.params
    conf = model.conf_int()

    effects = {}
    for name in params.index:
        if "band" in name or name in ("near_400", "near_800", "log_distance"):
            key = name.split("[T.")[-1].rstrip("]") if "band" in name else name
            # A log-point coefficient converts to a percentage premium.
            effects[key] = {
                "n": int(band_counts.get(key, model.nobs)),
                "premium_pct": round(100 * (np.exp(params[name]) - 1), 1),
                "ci_low_pct": round(100 * (np.exp(conf.loc[name, 0]) - 1), 1),
                "ci_high_pct": round(100 * (np.exp(conf.loc[name, 1]) - 1), 1),
                "p": float(model.pvalues[name]),
            }
    return {"label": label, "n": int(model.nobs), "r2": round(float(model.rsquared), 3), "effects": effects}


def figure_bands(table: pd.DataFrame) -> None:
    # Only bands that actually hold data get an axis position, and a point
    # resting on fewer than 50 sales is hollowed out so it reads as thin.
    present = [b for b in BAND_LABELS if b in set(table["band"].astype(str))]
    position = {b: i for i, b in enumerate(present)}
    fig, ax = plt.subplots(figsize=(9, 5), facecolor="white")
    for segment, colour in [("Strata (condo, flat)", SEAFOAM), ("Landed", NAVY)]:
        part = table[table["segment"] == segment].copy()
        part["x"] = part["band"].astype(str).map(position)
        part = part.sort_values("x")
        ax.plot(part["x"], part["median"], color=colour, linewidth=2, label=segment)
        solid, thin = part[part["n"] >= 50], part[part["n"] < 50]
        ax.plot(solid["x"], solid["median"], "o", color=colour)
        ax.plot(thin["x"], thin["median"], "o", markerfacecolor="white", markeredgecolor=colour, markeredgewidth=2)
        ax.fill_between(part["x"], part["p25"], part["p75"], color=colour, alpha=0.10, linewidth=0)
    ax.set_xticks(range(len(present)), present)
    ax.set_ylabel("Median price per sq.m (RM)", color=STEEL)
    ax.set_xlabel("Distance from nearest rail station", color=STEEL)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", color=HAIRLINE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False)
    ax.set_title("Price per square metre by distance from the rail network", loc="left", color=NAVY, fontweight="600")
    fig.text(0.01, 0.01, "Shaded band is the interquartile range. Hollow points rest on fewer than 50 sales. NAPIC registered transactions.", color=STEEL, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "price_by_distance.png", dpi=160)
    plt.close(fig)


def figure_premium(results: list[dict]) -> None:
    main = next(r for r in results if r["label"] == "strata")
    reference = "1.2–2 km"
    bands = [b for b in BAND_LABELS if b in main["effects"] or b == reference]
    fig, ax = plt.subplots(figsize=(9, 4.5), facecolor="white")
    y = np.arange(len(bands))
    for yi, b in zip(y, bands):
        if b == reference:
            ax.plot(0, yi, "o", markerfacecolor="white", markeredgecolor=NAVY, markeredgewidth=2, markersize=7)
            ax.annotate("reference", (0, yi), xytext=(8, 0), textcoords="offset points", va="center", color=STEEL, fontsize=9)
            continue
        e = main["effects"][b]
        ax.hlines(yi, e["ci_low_pct"], e["ci_high_pct"], color=SEAFOAM, linewidth=2)
        ax.plot(e["premium_pct"], yi, "o", color=NAVY, markersize=7)
    ax.axvline(0, color=STEEL, linewidth=1)
    ax.set_yticks(y, bands)
    ax.invert_yaxis()
    ax.set_xlabel("Price premium vs. 1.2–2 km from a station (%), holding type, tenure, year, level, size and mukim fixed", color=STEEL, fontsize=9)
    ax.grid(axis="x", color=HAIRLINE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title("Strata units: what proximity is worth after controls", loc="left", color=NAVY, fontweight="600")
    fig.text(0.01, 0.01, "Points are OLS estimates on log price per sq.m; lines are 95% intervals with robust errors.", color=STEEL, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "premium_by_band.png", dpi=160)
    plt.close(fig)


def figure_territory(results: list[dict]) -> None:
    """The headline: the same estimate, split by territory and segment."""
    rows = [
        ("Strata · Kuala Lumpur", "strata_kl_only"),
        ("Strata · Selangor & Putrajaya", "strata_selangor_putrajaya"),
        ("Landed · Kuala Lumpur", "landed_kl_only"),
        ("Landed · Selangor & Putrajaya", "landed_selangor_putrajaya"),
    ]
    fig, ax = plt.subplots(figsize=(9, 4.2), facecolor="white")
    for yi, (name, label) in enumerate(rows):
        r = next(x for x in results if x["label"] == label)
        e = r["effects"]["<400 m"]
        colour = SEAFOAM if "Strata" in name else NAVY
        ax.hlines(yi, e["ci_low_pct"], e["ci_high_pct"], color=colour, linewidth=2.5)
        ax.plot(e["premium_pct"], yi, "o", color=colour, markersize=8)
        ax.annotate(f"{e['premium_pct']:+.1f}%", (e["ci_high_pct"], yi), xytext=(8, 0),
                    textcoords="offset points", va="center", color=colour, fontsize=10, fontweight="600")
    ax.axvline(0, color=STEEL, linewidth=1)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(-4, 17)
    ax.set_xlabel("Premium for being within 400 m of a station vs. 1.2–2 km away (%), after controls", color=STEEL, fontsize=9)
    ax.grid(axis="x", color=HAIRLINE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title("The station premium is a suburban phenomenon", loc="left", color=NAVY, fontweight="600")
    fig.text(0.01, 0.01, "OLS on log price per sq.m with mukim, type, tenure, year, size and (strata) floor-level fixed; 95% intervals, robust errors.", color=STEEL, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / "premium_by_territory.png", dpi=160)
    plt.close(fig)


def figure_map(frame: pd.DataFrame, stations: pd.DataFrame) -> None:
    schemes = frame.groupby(["scheme", "lat", "lon"], as_index=False).agg(price=("price_per_sqm", "median"), n=("price", "size"))
    fig, ax = plt.subplots(figsize=(9, 8), facecolor="white")
    order = schemes["price"].rank(pct=True)
    # Single-hue sequential ramp from the Column seafoam scale, light to deep,
    # so magnitude reads the same way here as in the other charts.
    ramp = matplotlib.colors.LinearSegmentedColormap.from_list("seafoam", ["#94efb7", "#44b48b", "#167e6c", "#023247"])
    scatter = ax.scatter(schemes["lon"], schemes["lat"], c=order, cmap=ramp, s=np.clip(schemes["n"] / 3, 4, 40), alpha=0.8, linewidths=0)
    ax.scatter(stations["lon"], stations["lat"], marker="s", s=10, color=ORANGE, label="Rail station", linewidths=0)
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude", color=STEEL); ax.set_ylabel("Latitude", color=STEEL)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    bar = fig.colorbar(scatter, ax=ax, fraction=0.035, pad=0.02)
    bar.set_label("Scheme price per sq.m (percentile)", color=STEEL)
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Where the transactions are, and where the stations are", loc="left", color=NAVY, fontweight="600")
    fig.tight_layout()
    fig.savefig(FIGURES / "map.png", dpi=160)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(exist_ok=True); FIGURES.mkdir(exist_ok=True)
    frame, stations = load()
    frame = attach_nearest_station(frame, stations)
    print(f"median distance to a station: {frame['distance_m'].median():,.0f} m; "
          f"{(frame['distance_m'] < 800).mean():.0%} of transactions within 800 m")

    table = describe(frame)
    print("\nmedian RM per sq.m by band:")
    print(table.pivot(index="band", columns="segment", values="median").round(0).to_string())

    strata = frame[frame["is_strata"]].copy()
    landed = frame[~frame["is_strata"]].copy()
    results = [
        regress(strata, "strata"),
        regress(landed, "landed"),
        regress(strata, "strata_near_800", treatment="near_800"),
        regress(strata, "strata_near_400", treatment="near_400"),
        regress(strata, "strata_log_distance", treatment="log_distance"),
        # Robustness: only schemes placed at scheme level, not road level.
        regress(strata[strata["geo_level"] == "scheme"], "strata_scheme_level_only"),
        # Robustness: drop 2021, when the market was still distorted by the pandemic.
        regress(strata[strata["year"] >= 2022], "strata_2022_onward"),
        # The split that tests the mechanism: KL's rail runs through older, cheaper
        # corridors; Selangor's suburbs are car-dependent, so a station there is an
        # amenity rather than a marker of where the line happened to go.
        regress(strata[strata["district"] == "Kuala Lumpur"], "strata_kl_only"),
        regress(strata[strata["district"] != "Kuala Lumpur"], "strata_selangor_putrajaya"),
        regress(landed[landed["district"] == "Kuala Lumpur"], "landed_kl_only"),
        regress(landed[landed["district"] != "Kuala Lumpur"], "landed_selangor_putrajaya"),
    ]

    print("\nstrata premium by band vs 1.2-2 km (after controls):")
    for band, effect in results[0]["effects"].items():
        print(f"  {band:14s} {effect['premium_pct']:+6.1f}%  [{effect['ci_low_pct']:+.1f}, {effect['ci_high_pct']:+.1f}]  p={effect['p']:.3g}  n={effect['n']:,}")
    for label, key in (("strata_near_800", "near_800"), ("strata_near_400", "near_400")):
        r = next(x for x in results if x["label"] == label)
        e = r["effects"][key]
        print(f"  {label:24s} {e['premium_pct']:+6.1f}%  [{e['ci_low_pct']:+.1f}, {e['ci_high_pct']:+.1f}]  n={r['n']:,}")
    print()
    print("by segment and territory, <400 m vs 1.2-2 km:")
    for label in ("strata_kl_only", "strata_selangor_putrajaya", "landed", "landed_kl_only",
                  "landed_selangor_putrajaya", "strata_scheme_level_only", "strata_2022_onward"):
        r = next(x for x in results if x["label"] == label)
        e = r["effects"].get("<400 m")
        f = r["effects"].get(">5 km")
        near = f"{e['premium_pct']:+5.1f}% [{e['ci_low_pct']:+.1f}, {e['ci_high_pct']:+.1f}]" if e else "   n/a"
        far = f"{f['premium_pct']:+5.1f}% [{f['ci_low_pct']:+.1f}, {f['ci_high_pct']:+.1f}]" if f else "   n/a"
        print(f"  {label:28s} <400m {near}   >5km {far}   n={r['n']:,}")
    r = next(x for x in results if x["label"] == "strata_log_distance")
    e = r["effects"]["log_distance"]
    # Elasticity: percent change in price per 1% change in distance.
    print(f"  elasticity to distance   {e['premium_pct']/100:+.4f} log-points per log-metre "
          f"(doubling distance: {100*(2**(e['premium_pct']/100)-1):+.1f}%)")

    figure_bands(table)
    figure_premium(results)
    figure_territory(results)
    figure_map(frame, stations)

    summary = {
        "transactions_located": int(len(frame)),
        "schemes_located": int(frame["scheme"].nunique()),
        "stations_used": int(len(stations)),
        "median_distance_m": round(float(frame["distance_m"].median())),
        "share_within_800m": round(float((frame["distance_m"] < 800).mean()), 3),
        "bands": table.to_dict(orient="records"),
        "regressions": results,
    }
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    frame.drop(columns=["matched"], errors="ignore").to_parquet(OUT / "joined.parquet", index=False)
    print(f"\nwrote {OUT / 'results.json'} and three figures to {FIGURES}")


if __name__ == "__main__":
    main()
