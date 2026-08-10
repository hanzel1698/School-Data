#!/usr/bin/env python3
"""
Scrape "Students Details" (medium-wise class strength) from each school's
Sametham profile page (https://sametham.kite.kerala.gov.in/{School Code})
for the 146 schools in schools_adjacent_to_pwd_roads_v2_polygon.csv, and
produce sorted lists by total students in classes 1-4 (combined, and per
class).

Same request pattern (session/User-Agent/detail-page URL) as
kite_scraper_final.py, which already scrapes this exact site successfully.

IMPORTANT - UNTESTED: this was written without ever successfully fetching
a live page (blocked by this environment's network policy while writing
it) - only from a screenshot of the rendered table, not its HTML markup.
The table parser makes a deliberately generic assumption: the "Students
Details" table's rows always end with three columns (ALL Boys, ALL Girls,
ALL Total) regardless of how many medium sub-tables (Malayalam/English/
Tamil/Kannada/...) precede them, and each class row's first cell is the
standard number. Before trusting the full run, first do:

    python3 scrape_student_details.py --test-one <school_code>

and check the printed output makes sense (compare against the school's
own page) before running the full batch. If it doesn't parse right, share
the page's raw HTML (e.g. curl/view-source) and the parser can be fixed.

Usage:
    pip install requests beautifulsoup4
    python3 scrape_student_details.py                  # full run, all 146 schools
    python3 scrape_student_details.py --test-one 18205  # sanity-check one school first
    python3 scrape_student_details.py --limit 10        # quick partial run
"""

import argparse
import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

BASE = "https://sametham.kite.kerala.gov.in"
POLYGON_CSV = "schools_adjacent_to_pwd_roads_v2_polygon.csv"
MASTER_CSV = "schools_malappuram_my_maps_import.csv"
MAX_WORKERS = 8

RAW_OUT = "students_1to4_by_school.csv"
SORTED_TOTAL_OUT = "students_1to4_sorted_by_total.csv"
SORTED_CLASS_OUT_TMPL = "students_class{n}_sorted.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get(f"{BASE}/search/advanced_search_interface", timeout=15)
    except Exception:
        pass
    return s


def load_schools_with_codes():
    with open(POLYGON_CSV, newline="", encoding="utf-8") as f:
        polygon_rows = list(csv.DictReader(f))
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        master = {(r["Name"], r["Educational Sub-District"]): r for r in csv.DictReader(f)}

    schools = []
    unmatched = []
    for r in polygon_rows:
        key = (r["School Name"], r["Educational Sub-District"])
        m = master.get(key)
        if not m or not m.get("School Code"):
            unmatched.append(key)
            continue
        schools.append({
            "name": r["School Name"],
            "sub_district": r["Educational Sub-District"],
            "block": r.get("Block Name", ""),
            "code": m["School Code"],
        })
    if unmatched:
        print(f"[!] {len(unmatched)} schools could not be matched to a School Code and will be skipped:")
        for u in unmatched:
            print(f"    {u}")
    return schools


def parse_student_details(soup):
    """
    Find the 'Students Details' table and extract, per standard (class)
    row, the ALL-section Boys/Girls/Total - the last 3 cells of the row,
    which should hold regardless of how many medium columns precede them.
    Returns {standard_str: {'boys': int, 'girls': int, 'total': int}}.
    """
    target_table = None
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True).upper()
        if "STANDARD" in text and ("ALL" in text) and ("TOTAL" in text):
            target_table = table
            break
    if target_table is None:
        return {}

    results = {}
    for row in target_table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        first = cells[0].strip()
        if not re.match(r"^\d+$", first):
            continue  # header row, or a non-numeric label row (skip; grand "Total" row is handled separately if needed)
        try:
            boys = int(cells[-3])
            girls = int(cells[-2])
            total = int(cells[-1])
        except (ValueError, IndexError):
            continue
        results[first] = {"boys": boys, "girls": girls, "total": total}
    return results


def fetch_school_students(session, code, retries=3):
    url = f"{BASE}/{code}"
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            return parse_student_details(soup)
        except Exception as e:
            if attempt == retries - 1:
                print(f"  [!] Failed to fetch/parse {code}: {e}")
                return None
            time.sleep(1)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-one", metavar="CODE", help="Fetch and print just one school code, then exit.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N schools (for a quick test run).")
    args = parser.parse_args()

    session = get_session()

    if args.test_one:
        print(f"Fetching {BASE}/{args.test_one} ...")
        result = fetch_school_students(session, args.test_one)
        print("Parsed classes 1-4 (and any others found):")
        if not result:
            print("  (nothing parsed - table not found, or page structure differs from expectations)")
        else:
            for std in sorted(result.keys(), key=lambda x: int(x)):
                print(f"  Standard {std}: {result[std]}")
        return

    schools = load_schools_with_codes()
    if args.limit:
        schools = schools[: args.limit]
    print(f"Fetching Students Details for {len(schools)} schools (concurrency={MAX_WORKERS})...")

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_school = {executor.submit(fetch_school_students, session, s["code"]): s for s in schools}
        done = 0
        for future in as_completed(future_to_school):
            s = future_to_school[future]
            results[s["code"]] = future.result()
            done += 1
            if done % 20 == 0 or done == len(schools):
                print(f"  ...{done}/{len(schools)} fetched")

    rows = []
    failed = []
    for s in schools:
        classes = results.get(s["code"])
        if not classes:
            failed.append(s)
            continue
        c1 = classes.get("1", {}).get("total", 0)
        c2 = classes.get("2", {}).get("total", 0)
        c3 = classes.get("3", {}).get("total", 0)
        c4 = classes.get("4", {}).get("total", 0)
        rows.append({
            "School Name": s["name"],
            "Educational Sub-District": s["sub_district"],
            "Block Name": s["block"],
            "School Code": s["code"],
            "Class 1 Total": c1,
            "Class 2 Total": c2,
            "Class 3 Total": c3,
            "Class 4 Total": c4,
            "Total (Classes 1-4)": c1 + c2 + c3 + c4,
        })

    fieldnames = ["School Name", "Educational Sub-District", "Block Name", "School Code",
                  "Class 1 Total", "Class 2 Total", "Class 3 Total", "Class 4 Total", "Total (Classes 1-4)"]

    with open(RAW_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n[OK] Raw per-school data saved: {RAW_OUT} ({len(rows)} schools, {len(failed)} failed)")

    with open(SORTED_TOTAL_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["Total (Classes 1-4)"], reverse=True))
    print(f"[OK] Sorted by combined total saved: {SORTED_TOTAL_OUT}")

    for n in (1, 2, 3, 4):
        out = SORTED_CLASS_OUT_TMPL.format(n=n)
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: r[f"Class {n} Total"], reverse=True))
        print(f"[OK] Sorted by Class {n} total saved: {out}")

    if failed:
        print(f"\n[!] {len(failed)} schools failed to fetch/parse:")
        for s in failed:
            print(f"    {s['name']} ({s['sub_district']}) - code {s['code']}")


if __name__ == "__main__":
    main()
