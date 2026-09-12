"""Scrape every Klang Valley rail station and its coordinates from Wikipedia.

The list page gives the station table; each station's own article carries the
coordinates in a geo microformat. Wikipedia permits this kind of access with a
descriptive User-Agent and a polite rate, so the fetcher identifies itself,
sleeps between requests, and caches every page to disk so re-runs cost nothing.

Run:  python 01_stations.py
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
CACHE = HERE / "data" / "raw" / "wiki"
OUT = HERE / "data" / "stations.csv"

BASE = "https://en.wikipedia.org"
LIST_URL = f"{BASE}/wiki/List_of_rail_transit_stations_in_the_Klang_Valley_area"

# Wikipedia's policy asks for a User-Agent that says who you are and how to
# reach you. Anonymous defaults get throttled or blocked.
HEADERS = {
    "User-Agent": "Trackside/1.0 (portfolio data project; https://github.com/direenvy) python-requests",
    "Accept-Language": "en",
}
DELAY_SECONDS = 1.0


class Fetcher:
    """GET with a disk cache and a fixed pause between live requests."""

    def __init__(self) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.live_requests = 0

    def get(self, url: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9_.-]", "_", url.split("/wiki/")[-1])[:150]
        cached = CACHE / f"{slug}.html"
        if cached.exists():
            return cached.read_text(encoding="utf-8")

        if self.live_requests:
            time.sleep(DELAY_SECONDS)
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        self.live_requests += 1
        cached.write_text(response.text, encoding="utf-8")
        return response.text


def clean(text: str) -> str:
    # Strip footnote markers like [1] and collapse whitespace.
    return re.sub(r"\[\d+\]", "", text).replace("\xa0", " ").strip()


def parse_station_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []

    for table in soup.select("table.wikitable"):
        headers = [clean(th.get_text(" ")) for th in table.select("tr th")]
        if not any("station code" in h.lower() for h in headers):
            continue

        # Column positions differ between tables on the page, so resolve by name.
        index = {h.lower(): i for i, h in enumerate(headers)}

        def col(cells: list, key: str) -> str:
            for name, i in index.items():
                if key in name and i < len(cells):
                    return clean(cells[i].get_text(" "))
            return ""

        for tr in table.select("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 4 or tr.find("th") and not tr.find("td"):
                continue
            # Wikipedia may serve Parsoid HTML with absolute hrefs, so match on
            # the path rather than the prefix, and skip image links.
            link = cells[0].find("a", href=re.compile(r"/wiki/(?!File:)"))
            if not link:
                continue
            rows.append(
                {
                    "name": clean(link.get_text(" ")),
                    "url": urljoin(BASE, link["href"]),
                    "code": col(cells, "station code"),
                    "lines": col(cells, "line"),
                    "operator": col(cells, "operator"),
                    "type": col(cells, "type"),
                    "authority": col(cells, "local authority"),
                    "opened": col(cells, "opened"),
                }
            )
    return rows


COORD_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*;\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_coordinates(html: str) -> tuple[float, float] | None:
    soup = BeautifulSoup(html, "lxml")
    # The geo microformat is the stable hook: <span class="geo">3.13; 101.68</span>.
    for span in soup.select("span.geo"):
        match = COORD_PATTERN.match(span.get_text())
        if match:
            return float(match.group(1)), float(match.group(2))
    return None


API_URL = f"{BASE}/w/api.php"


def api_coordinates(fetcher: Fetcher, title: str) -> tuple[float, float] | None:
    """Fallback for articles with no geo microformat: the coordinates API,
    which reads from Wikidata. Cached like everything else."""
    cached = CACHE / f"api_{re.sub(r'[^A-Za-z0-9_-]', '_', title)[:120]}.json"
    if cached.exists():
        payload = json.loads(cached.read_text(encoding="utf-8"))
    else:
        time.sleep(DELAY_SECONDS)
        response = fetcher.session.get(
            API_URL,
            params={"action": "query", "prop": "coordinates", "titles": title, "format": "json"},
            timeout=30,
        )
        response.raise_for_status()
        fetcher.live_requests += 1
        payload = response.json()
        cached.write_text(json.dumps(payload), encoding="utf-8")
    for page in payload.get("query", {}).get("pages", {}).values():
        for coord in page.get("coordinates", []):
            return float(coord["lat"]), float(coord["lon"])
    return None


def main() -> None:
    fetcher = Fetcher()
    print("fetching station list …")
    stations = parse_station_table(fetcher.get(LIST_URL))
    print(f"  {len(stations)} stations in the table")

    # The list carries the same station once per line it serves; the article
    # is what we key on.
    unique: dict[str, dict] = {}
    for station in stations:
        entry = unique.setdefault(station["url"], dict(station))
        if station["lines"] and station["lines"] not in entry["lines"]:
            entry["lines"] = f"{entry['lines']} / {station['lines']}"
    print(f"  {len(unique)} distinct station articles")

    missing = []
    fallbacks = 0
    for i, (url, station) in enumerate(unique.items(), 1):
        coords = parse_coordinates(fetcher.get(url))
        if not coords:
            title = url.split("/wiki/")[-1].replace("_", " ")
            coords = api_coordinates(fetcher, title)
            fallbacks += coords is not None
        if coords:
            station["lat"], station["lon"] = coords
        else:
            station["lat"] = station["lon"] = ""
            missing.append(station["name"])
        if i % 25 == 0 or i == len(unique):
            print(f"  {i}/{len(unique)} articles ({fetcher.live_requests} live requests)", flush=True)

    fields = ["name", "code", "lines", "operator", "type", "authority", "opened", "lat", "lon", "url"]
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(unique.values())

    located = sum(1 for s in unique.values() if s["lat"] != "")
    print(f"\nwrote {OUT} — {located} of {len(unique)} stations with coordinates")
    if missing:
        print(f"no coordinates for: {', '.join(missing[:12])}{' …' if len(missing) > 12 else ''}")


if __name__ == "__main__":
    main()
