#!/usr/bin/env python3
"""
Apply reviewed coordinate corrections (from schools_road_adjacent_maps_check.html)
back into the master school coordinate DB.

Input is the CSV exported by the HTML review tool's "Export CSV" button
(one row per road-adjacent school, with a Review Status column). Each row
is resolved to a final Latitude/Longitude and merged into a copy of
schools_malappuram_my_maps_import.csv, matched by (School Name,
Educational Sub-District) - verified unique across all 381 rows.

Resolution per Review Status:
    DB Confirmed          -> unchanged (DB Latitude/Longitude)
    Google Confirmed       -> Google Latitude/Longitude
    Corrected               -> Corrected Latitude/Longitude
    Flagged / Unreviewed   -> unchanged, listed as outstanding

The master CSV is never edited in place - this writes a new versioned copy.

Usage:
    python3 apply_road_review_corrections.py [--input schools_road_adjacent_maps_check_reviewed.csv]
"""

import argparse
import csv
import os
import sys

MASTER_CSV = "schools_malappuram_my_maps_import.csv"
DEFAULT_INPUT = "schools_road_adjacent_maps_check_reviewed.csv"

MASTER_OUT = "schools_malappuram_my_maps_import_v2.csv"
CHANGELOG_OUT = "road_review_corrections_changelog.csv"
OUTSTANDING_OUT = "road_review_outstanding.csv"

MASTER_FIELDNAMES = [
    "Name", "Latitude", "Longitude", "Educational District",
    "Educational Sub-District", "Block Name", "Level Name", "Phone", "School Code",
]

CHANGELOG_FIELDNAMES = [
    "School Name", "Educational Sub-District", "Old Latitude", "Old Longitude",
    "New Latitude", "New Longitude", "Source", "Reviewer Note",
]

OUTSTANDING_FIELDNAMES = [
    "School Name", "Educational Sub-District", "Block Name", "Bucket",
    "Review Status", "DB Latitude", "DB Longitude", "Distance Meters", "Notes",
]


def load_master(path):
    if not os.path.exists(path):
        print(f"[!] {path} not found in this folder.")
        sys.exit(1)
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["Name"], row["Educational Sub-District"])
            rows[key] = row
    return rows


def resolve_final_coord(row):
    status = row["Review Status"]
    if status == "Google Confirmed":
        return float(row["Google Latitude"]), float(row["Google Longitude"]), "google_confirmed"
    if status == "Corrected":
        if not row["Corrected Latitude"] or not row["Corrected Longitude"]:
            return None
        return float(row["Corrected Latitude"]), float(row["Corrected Longitude"]), "corrected"
    if status == "DB Confirmed":
        return float(row["DB Latitude"]), float(row["DB Longitude"]), "db_confirmed"
    return None  # Flagged / Unreviewed - no change


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[!] {args.input} not found.")
        print("    Export it from schools_road_adjacent_maps_check.html ('Export CSV' button)")
        print("    and place it in this folder, or pass --input <path>.")
        sys.exit(1)

    master = load_master(MASTER_CSV)
    print(f"Loaded {len(master)} schools from {MASTER_CSV}")

    with open(args.input, newline="", encoding="utf-8") as f:
        reviewed_rows = list(csv.DictReader(f))
    print(f"Loaded {len(reviewed_rows)} reviewed rows from {args.input}")

    status_counts = {}
    changelog = []
    outstanding = []
    unmatched = []
    changed_count = 0
    unchanged_confirmed_count = 0

    for row in reviewed_rows:
        status = row.get("Review Status", "Unreviewed")
        status_counts[status] = status_counts.get(status, 0) + 1

        key = (row["School Name"], row["Educational Sub-District"])
        master_row = master.get(key)
        if master_row is None:
            unmatched.append(key)
            continue

        if status in ("Flagged", "Unreviewed"):
            outstanding.append({
                "School Name": row["School Name"],
                "Educational Sub-District": row["Educational Sub-District"],
                "Block Name": row.get("Block Name", ""),
                "Bucket": row.get("Bucket", ""),
                "Review Status": status,
                "DB Latitude": row.get("DB Latitude", ""),
                "DB Longitude": row.get("DB Longitude", ""),
                "Distance Meters": row.get("Distance Meters", ""),
                "Notes": row.get("Notes", ""),
            })
            continue

        resolved = resolve_final_coord(row)
        if resolved is None:
            # Corrected status but missing corrected coords - treat as outstanding
            outstanding.append({
                "School Name": row["School Name"],
                "Educational Sub-District": row["Educational Sub-District"],
                "Block Name": row.get("Block Name", ""),
                "Bucket": row.get("Bucket", ""),
                "Review Status": status + " (missing corrected coords)",
                "DB Latitude": row.get("DB Latitude", ""),
                "DB Longitude": row.get("DB Longitude", ""),
                "Distance Meters": row.get("Distance Meters", ""),
                "Notes": row.get("Notes", ""),
            })
            continue

        new_lat, new_lon, source = resolved
        old_lat, old_lon = float(master_row["Latitude"]), float(master_row["Longitude"])

        if abs(new_lat - old_lat) > 1e-9 or abs(new_lon - old_lon) > 1e-9:
            changelog.append({
                "School Name": row["School Name"],
                "Educational Sub-District": row["Educational Sub-District"],
                "Old Latitude": old_lat,
                "Old Longitude": old_lon,
                "New Latitude": new_lat,
                "New Longitude": new_lon,
                "Source": source,
                "Reviewer Note": row.get("Reviewer Note", ""),
            })
            master_row["Latitude"] = str(new_lat)
            master_row["Longitude"] = str(new_lon)
            changed_count += 1
        else:
            unchanged_confirmed_count += 1

    master_out = MASTER_OUT
    with open(master_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_FIELDNAMES)
        writer.writeheader()
        for row in master.values():
            writer.writerow({k: row.get(k, "") for k in MASTER_FIELDNAMES})
    print(f"\n[OK] Corrected master CSV saved: {master_out} ({len(master)} schools)")

    with open(CHANGELOG_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CHANGELOG_FIELDNAMES)
        writer.writeheader()
        writer.writerows(changelog)
    print(f"[OK] Changelog saved: {CHANGELOG_OUT} ({len(changelog)} coordinates changed)")

    with open(OUTSTANDING_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTSTANDING_FIELDNAMES)
        writer.writeheader()
        writer.writerows(outstanding)
    print(f"[OK] Outstanding list saved: {OUTSTANDING_OUT} ({len(outstanding)} schools still need review)")

    if unmatched:
        print(f"\n[!] {len(unmatched)} reviewed rows could not be matched to {MASTER_CSV}:")
        for key in unmatched[:10]:
            print(f"    {key}")

    print("\nReview Status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    print(f"\nCoordinates changed: {changed_count}")
    print(f"Confirmed unchanged (DB Confirmed matching existing coord): {unchanged_confirmed_count}")
    print(f"Still outstanding (Flagged/Unreviewed/missing corrected coords): {len(outstanding)}")
    total_accounted = changed_count + unchanged_confirmed_count + len(outstanding)
    print(f"Total accounted for: {total_accounted} / {len(reviewed_rows)}")

    if changelog:
        print(f"\nNext step: python3 schools_near_pwd_roads_v3.py")


if __name__ == "__main__":
    main()
