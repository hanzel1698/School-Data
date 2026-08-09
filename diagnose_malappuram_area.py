#!/usr/bin/env python3
"""
Diagnostic: list every OpenStreetMap area named "Malappuram" tagged
boundary=administrative, with its relation id, admin_level, and any
other identifying tags. This is to pin down exactly which relation is
the actual Malappuram DISTRICT (as opposed to a taluk, municipality, or
anything else that happens to share the name) - since the last run's
State Highway total (1,830 km) came in ~5x higher than the official
~375 km figure for the district, suggesting the name-based area lookup
in pwd_roads_overpass.py may have matched something broader than
intended.

Usage:
    python diagnose_malappuram_area.py
"""

import requests
import time

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]

HEADERS = {
    'User-Agent': 'MalappuramPWDRoadsScript/1.0 (personal research use)',
    'Accept': 'application/json, text/plain, */*',
}

QUERY = """
[out:json][timeout:60];
relation["name"="Malappuram"]["boundary"="administrative"];
out tags;
"""


def run_query():
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            print(f"Trying {endpoint} ...")
            try:
                r = requests.post(endpoint, data={'data': QUERY}, headers=HEADERS, timeout=90)
                if r.status_code == 429:
                    print("  rate-limited, waiting 10s...")
                    time.sleep(10)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as e:
                print(f"  failed: {e}")
                break
        time.sleep(2)
    return None


def main():
    print("=" * 70)
    print('Finding all OSM relations named "Malappuram" (boundary=administrative)')
    print("=" * 70)

    data = run_query()
    if not data or not data.get('elements'):
        print("\n[!] No matching relations found, or all endpoints failed.")
        print("    Try https://overpass-turbo.eu/ manually with this query:")
        print(QUERY)
        return

    print(f"\nFound {len(data['elements'])} matching relation(s):\n")
    for el in data['elements']:
        tags = el.get('tags', {})
        print(f"  relation id: {el['id']}")
        print(f"    admin_level: {tags.get('admin_level', '?')}")
        print(f"    name:en:     {tags.get('name:en', tags.get('name', '?'))}")
        print(f"    is_in / is_in:district: {tags.get('is_in', '')} / {tags.get('is_in:district', '')}")
        print(f"    wikidata:    {tags.get('wikidata', '')}")
        print(f"    population:  {tags.get('population', '')}")
        print(f"    all tags:    {tags}")
        print(f"    view on OSM: https://www.openstreetmap.org/relation/{el['id']}")
        print()

    print("=" * 70)
    print("The DISTRICT relation is almost always admin_level=5 in India")
    print("(state=4, district=5). Copy the relation id for that one and")
    print("share it back - the roads script will be updated to pin to")
    print("that exact relation instead of matching by name.")
    print("=" * 70)


if __name__ == "__main__":
    main()
