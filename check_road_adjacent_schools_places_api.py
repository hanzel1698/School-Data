#!/usr/bin/env python3
"""
Cross-check every school in schools_adjacent_to_pwd_roads_v2.csv against
Google's Places API (New) Text Search, as an independent check on the
scraped KITE-portal coordinates (see G.M.L.P.S. Valavannur, code 19646,
which was ~1.4km off).

Read-only research pass - does not modify any existing CSV.

Usage:
    GOOGLE_MAPS_API_KEY=<key> python check_road_adjacent_schools_places_api.py [--limit N]
"""

import argparse
import csv
import difflib
import os
import re
import sys
import time
from math import radians, sin, cos, sqrt, atan2

import requests

SOURCE_CSV = "schools_adjacent_to_pwd_roads_v2.csv"
OUTPUT_CSV = "schools_road_adjacent_maps_check.csv"
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName,places.location,places.formattedAddress"
REQUEST_DELAY_SEC = 0.3


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


# Generic institutional words/abbreviations that appear in almost every Kerala
# school name and carry no location information - stripping these leaves just
# the distinctive place-name token(s), e.g. "GLPS Parathakkad" -> "PARATHAKKAD".
STOPWORDS = {
    "G", "M", "L", "P", "S", "U", "H", "A", "C", "V", "N", "T", "GLPS", "GMLPS",
    "GUPS", "GMUPS", "GHSS", "GHS", "GVHSS", "AMLPS", "AUPS", "AMUPS", "AUPHS",
    "LPS", "UPS", "HSS", "HS", "MSM", "SCHOOL", "SCHOOLS", "GOVT", "GOVERNMENT",
    "AIDED", "LP", "UP", "LOWER", "UPPER", "PRIMARY", "SECONDARY", "HIGHER",
    "VOCATIONAL", "ENGLISH", "MEDIUM", "CENTRAL", "PUBLIC", "MODEL", "OF",
    "AND", "THE", "SOUTH", "NORTH", "EAST", "WEST",
}


def normalize_name(name):
    name = name.upper()
    name = re.sub(r"[.\-,()]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def distinctive_tokens(name):
    tokens = normalize_name(name).split()
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def name_similarity(school_name, google_name):
    """Best fuzzy match between the school's distinctive place-name token(s)
    and any token in the Google result's own name. Whole-string ratios are
    too easily inflated by shared generic words (GLPS, School, the
    sub-district name); this isolates the part that actually identifies
    *which* school it is. Deliberately excludes the formatted address - a
    wrong-but-nearby result's road name can coincidentally contain the same
    place word (e.g. "...Kizhisseri Rd..."), which would otherwise inflate
    confidence for a match that isn't actually the same school."""
    school_tokens = distinctive_tokens(school_name)
    candidate_tokens = distinctive_tokens(google_name)
    if not school_tokens or not candidate_tokens:
        return 0.0
    best = 0.0
    for st in school_tokens:
        for ct in candidate_tokens:
            ratio = difflib.SequenceMatcher(None, st, ct).ratio()
            best = max(best, ratio)
    return round(best, 3)


# A village commonly has both a Government-run and a separately-run Aided
# school (often adjacent grade levels) sharing the same place name - these
# are different institutions, not spelling variants of one school, so a high
# place-name token score alone isn't enough to call it a match. The
# management type is usually encoded in the school's abbreviation, but not
# always as a plain prefix - e.g. "VPAUPS" is place-initials (V,P) + "A"
# (Aided) + "UPS", so this scans the whole first token for a known marker
# rather than just checking its first letter.
GOVT_MARKERS = ("GLPS", "GMLPS", "GUPS", "GMUPS", "GHSS", "GVHSS", "GHS")
AIDED_MARKERS = ("AMLPS", "AUPHS", "AMUPS", "AUPS", "AMPS", "AHSS", "AHS", "AUP")


def management_type(name):
    """Returns 'GOVT', 'AIDED', or None (unparseable) from the name's first token."""
    first_token = normalize_name(name).split()[0] if name.strip() else ""
    if any(m in first_token for m in AIDED_MARKERS):
        return "AIDED"
    if any(m in first_token for m in GOVT_MARKERS):
        return "GOVT"
    return None


def search_place(query, api_key):
    try:
        r = requests.post(
            SEARCH_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": FIELD_MASK,
            },
            json={"textQuery": query},
            timeout=20,
        )
        if r.status_code != 200:
            return {"status": f"HTTP_{r.status_code}"}
        places = r.json().get("places", [])
        if not places:
            return {"status": "NO_MATCH_FOUND"}
        top = places[0]
        return {
            "status": "OK",
            "name": top.get("displayName", {}).get("text", ""),
            "lat": top["location"]["latitude"],
            "lon": top["location"]["longitude"],
            "address": top.get("formattedAddress", ""),
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Set GOOGLE_MAPS_API_KEY in the environment first.", file=sys.stderr)
        sys.exit(1)

    with open(SOURCE_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.limit:
        rows = rows[: args.limit]
    print(f"Checking {len(rows)} road-adjacent schools against Places API (New)...")

    out_rows = []
    for i, row in enumerate(rows, 1):
        name = row["School Name"]
        subdist = row["Educational Sub-District"]
        db_lat, db_lon = float(row["Latitude"]), float(row["Longitude"])
        query = f"{name} {subdist} Malappuram Kerala"

        result = search_place(query, api_key)
        print(f"  [{i}/{len(rows)}] {name!r} -> {result['status']}")

        # Throttled milestone line for progress monitoring - printed roughly
        # every 5%, plus always on the first and last row, so a filter can
        # show a percent readout without a notification per school.
        step = max(1, len(rows) // 20)
        if i == 1 or i == len(rows) or i % step == 0:
            pct = round(i * 100 / len(rows))
            print(f"PROGRESS: {i}/{len(rows)} ({pct}%)", flush=True)

        out = {
            "School Name": name,
            "Educational Sub-District": subdist,
            "Block Name": row["Block Name"],
            "DB Latitude": db_lat,
            "DB Longitude": db_lon,
            "Google Matched Name": "",
            "Google Latitude": "",
            "Google Longitude": "",
            "Distance Meters": "",
            "Name Similarity": "",
            "Management Mismatch": "",
            "Notes": "",
        }

        if result["status"] == "OK":
            dist = haversine_m(db_lat, db_lon, result["lat"], result["lon"])
            sim = name_similarity(name, result["name"])
            school_mgmt = management_type(name)
            match_mgmt = management_type(result["name"])
            mgmt_mismatch = bool(school_mgmt and match_mgmt and school_mgmt != match_mgmt)
            out.update({
                "Google Matched Name": result["name"],
                "Google Latitude": result["lat"],
                "Google Longitude": result["lon"],
                "Distance Meters": round(dist, 1),
                "Name Similarity": sim,
                "Management Mismatch": f"{school_mgmt or '?'} vs {match_mgmt or '?'}" if mgmt_mismatch else "",
            })
        else:
            out["Notes"] = result["status"]

        out_rows.append(out)
        time.sleep(REQUEST_DELAY_SEC)

    # A fuzzy token ratio below this means the "match" is almost certainly an
    # unrelated place Google fell back to (see e.g. "Parathakkad" vs
    # "Kuzhimanna" ~0.39) rather than the actual school - its distance isn't
    # meaningful evidence of a coordinate error, just of a missing listing.
    CONFIDENCE_THRESHOLD = 0.72

    for r in out_rows:
        has_match = isinstance(r["Distance Meters"], (int, float))
        if has_match and r["Management Mismatch"]:
            r["Notes"] = "LOW_CONFIDENCE_MATCH (different Govt/Aided institution)"
        elif has_match and r["Name Similarity"] < CONFIDENCE_THRESHOLD:
            r["Notes"] = "LOW_CONFIDENCE_MATCH"

    def sort_key(r):
        has_match = isinstance(r["Distance Meters"], (int, float))
        confident = (
            has_match
            and r["Name Similarity"] >= CONFIDENCE_THRESHOLD
            and not r["Management Mismatch"]
        )
        dist = r["Distance Meters"] if confident else 0
        # worst first: no/unreliable match, then confident matches by distance desc
        return (1 if confident else 0, -dist)

    out_rows.sort(key=sort_key)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    no_match = sum(1 for r in out_rows if not isinstance(r["Distance Meters"], (int, float)))
    low_conf = sum(1 for r in out_rows if str(r["Notes"]).startswith("LOW_CONFIDENCE_MATCH"))
    confident = [
        r for r in out_rows
        if isinstance(r["Distance Meters"], (int, float))
        and r["Name Similarity"] >= CONFIDENCE_THRESHOLD
        and not r["Management Mismatch"]
    ]
    over_300 = sum(1 for r in confident if r["Distance Meters"] > 300)
    print(f"\nWrote {len(out_rows)} rows to {OUTPUT_CSV}")
    print(f"  No match found: {no_match}")
    print(f"  Low-confidence match (Google likely returned an unrelated school): {low_conf}")
    print(f"  Confident match: {len(confident)}, of which >300m from DB coordinate: {over_300}")


if __name__ == "__main__":
    main()
