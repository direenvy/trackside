"""Geocode place names with Nominatim (OpenStreetMap), politely.

Nominatim's usage policy is strict and reasonable: one request per second,
a User-Agent that identifies the application, and cache everything so the
same query never hits their servers twice. This module does all three.

Two jobs live here:
  --stations   fill coordinates for the stations Wikipedia has none for
  --schemes    geocode the distinct scheme names in the transaction table

Run:  python 03_geocode.py --stations
      python 03_geocode.py --schemes
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE_FILE = DATA / "geocode_cache.json"

NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": "Trackside/1.0 (portfolio data project; https://github.com/direenvy)",
    "Accept-Language": "en",
}
DELAY_SECONDS = 1.1  # a hair over the policy minimum, so clock jitter never violates it

# Bounding box for the Klang Valley, generously drawn. Results outside it are
# almost always a same-named place in another state, so they are rejected.
BBOX = {"lat_min": 2.6, "lat_max": 3.6, "lon_min": 101.2, "lon_max": 102.0}


class Geocoder:
    def __init__(self) -> None:
        self.cache: dict[str, dict | None] = (
            json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}
        )
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.live_requests = 0

    def save(self) -> None:
        CACHE_FILE.write_text(json.dumps(self.cache, indent=1, ensure_ascii=False), encoding="utf-8")

    def lookup(self, query: str) -> dict | None:
        key = query.strip().lower()
        if key in self.cache:
            return self.cache[key]

        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 3,
            "countrycodes": "my",
            "viewbox": f"{BBOX['lon_min']},{BBOX['lat_max']},{BBOX['lon_max']},{BBOX['lat_min']}",
            "bounded": 1,
        }
        # A thousand-query run will meet the odd timeout or 5xx. Back off and
        # retry; if it still fails, skip this query without caching the miss,
        # so a later run can try again.
        response = None
        for attempt in range(1, 4):
            if self.live_requests:
                time.sleep(DELAY_SECONDS)
            try:
                response = self.session.get(NOMINATIM, params=params, timeout=30)
                self.live_requests += 1
                if response.status_code >= 500 or response.status_code == 429:
                    raise requests.HTTPError(f"status {response.status_code}")
                response.raise_for_status()
                break
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as error:
                response = None
                if attempt == 3:
                    print(f"  giving up on {query!r}: {error}", flush=True)
                    return None
                time.sleep(5 * attempt)

        result = None
        for hit in response.json():
            lat, lon = float(hit["lat"]), float(hit["lon"])
            if BBOX["lat_min"] <= lat <= BBOX["lat_max"] and BBOX["lon_min"] <= lon <= BBOX["lon_max"]:
                result = {
                    "lat": lat,
                    "lon": lon,
                    "display": hit.get("display_name", "")[:120],
                    "type": hit.get("type", ""),
                    "importance": hit.get("importance", 0),
                }
                break

        self.cache[key] = result
        # Persist as we go — a crash 200 queries in should not cost 200 queries.
        if self.live_requests % 10 == 0:
            self.save()
        return result


def fill_stations(geocoder: Geocoder) -> None:
    stations = pd.read_csv(DATA / "stations.csv")
    missing = stations["lat"].isna()
    print(f"{int(missing.sum())} stations without coordinates")

    filled = 0
    for i in stations.index[missing]:
        name, kind = stations.at[i, "name"], stations.at[i, "type"]
        # Try the most specific phrasing first; fall back to the bare name.
        queries = [f"{name} {kind} station, Selangor", f"{name} station, Malaysia", f"{name}, Selangor"]
        for query in queries:
            hit = geocoder.lookup(query)
            if hit:
                stations.at[i, "lat"], stations.at[i, "lon"] = hit["lat"], hit["lon"]
                stations.at[i, "coord_source"] = "osm"
                filled += 1
                print(f"  {name:24s} <- {hit['display'][:70]}")
                break
        else:
            print(f"  {name:24s} -- not found")

    stations["coord_source"] = stations.get("coord_source", pd.Series(dtype=str)).fillna("wikipedia")
    stations.loc[stations["lat"].isna(), "coord_source"] = ""
    stations.to_csv(DATA / "stations.csv", index=False)
    geocoder.save()
    located = int(stations["lat"].notna().sum())
    print(f"\nfilled {filled}; {located} of {len(stations)} stations now have coordinates")


# NAPIC abbreviates Malay place words inconsistently. Nominatim knows the
# full forms, so expand before querying.
ABBREVIATIONS = {
    "TMN": "Taman", "KG": "Kampung", "KAW": "Kawasan", "JLN": "Jalan", "BDR": "Bandar",
    "SEK": "Seksyen", "LRG": "Lorong", "PSN": "Persiaran", "BKT": "Bukit", "SG": "Sungai",
    "PT": "Pusat", "APT": "Apartment", "KONDO": "Kondominium", "PKT": "Pangsapuri",
}


def normalise(name: str) -> str:
    text = re.sub(r"\(.*?\)", " ", str(name))          # drop annotations like (PKNS HOUSING SCHEME)
    text = re.sub(r"^OFF\s+", "", text, flags=re.I)     # "OFF JALAN KLANG LAMA" -> the road itself
    words = [ABBREVIATIONS.get(w.upper().strip(".,"), w) for w in text.split()]
    return re.sub(r"\s+", " ", " ".join(words)).strip().title()


def geocode_schemes(geocoder: Geocoder, retry_misses: bool = False) -> None:
    path = DATA / "transactions.parquet"
    if not path.exists():
        raise SystemExit(f"No {path}. Run 02_transactions.py first.")
    frame = pd.read_parquet(path)

    # One lookup per distinct scheme within a mukim, not per transaction. The
    # commonest road in each scheme is kept as a fallback anchor.
    places = (
        frame.dropna(subset=["scheme"])
        .groupby(["scheme", "mukim", "district"], dropna=False)["road"]
        .agg(lambda r: r.mode().iat[0] if not r.mode().empty else None)
        .reset_index()
    )
    out_path = DATA / "scheme_coords.csv"
    previous = pd.read_csv(out_path) if out_path.exists() else None
    if retry_misses and previous is not None:
        done = previous[previous["lat"].notna()]
        places = places.merge(done[["scheme", "mukim", "district"]], how="left", indicator=True)
        places = places[places["_merge"] == "left_only"].drop(columns="_merge")
        print(f"retrying {len(places)} unresolved schemes")
    else:
        done = None
        print(f"{len(places)} distinct scheme/mukim pairs to geocode")

    rows = []
    for n, (scheme, mukim, district, road) in enumerate(places.itertuples(index=False), 1):
        name = normalise(scheme)
        mukim_name = str(mukim).replace("MUKIM ", "").title() if pd.notna(mukim) else ""
        # Most specific first; the raw form is included so first-pass cache hits are reused.
        cascade = [
            (f"{name}, {mukim_name}, {district}, Malaysia", "scheme"),
            (f"{scheme}, {district}, Malaysia", "scheme"),
            (f"{name}, {district}, Malaysia", "scheme"),
        ]
        if road and pd.notna(road):
            cascade.append((f"{normalise(road)}, {mukim_name}, {district}, Malaysia", "road"))

        hit, level = None, "none"
        for query, lvl in cascade:
            hit = geocoder.lookup(query)
            if hit:
                level = lvl
                break
        rows.append({"scheme": scheme, "mukim": mukim, "district": district,
                     "lat": hit["lat"] if hit else None, "lon": hit["lon"] if hit else None,
                     "geo_level": level, "matched": hit["display"] if hit else ""})
        if n % 50 == 0:
            print(f"  {n}/{len(places)} ({geocoder.live_requests} live requests)", flush=True)

    geocoder.save()
    out = pd.DataFrame(rows)
    if done is not None:
        out = pd.concat([done, out], ignore_index=True)
    out.to_csv(out_path, index=False)
    located = int(out["lat"].notna().sum())
    at_scheme = int((out["geo_level"] == "scheme").sum())
    at_road = int((out["geo_level"] == "road").sum())
    print()
    print(f"wrote scheme_coords.csv — {located} of {len(out)} located ({at_scheme} at scheme level, {at_road} at road level)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", action="store_true")
    parser.add_argument("--schemes", action="store_true")
    parser.add_argument("--retry-misses", action="store_true", help="Only re-query schemes that failed last time.")
    args = parser.parse_args()
    if not (args.stations or args.schemes):
        parser.error("choose --stations and/or --schemes")

    geocoder = Geocoder()
    if args.stations:
        fill_stations(geocoder)
    if args.schemes:
        geocode_schemes(geocoder, retry_misses=args.retry_misses)


if __name__ == "__main__":
    main()
