#!/usr/bin/env python3
"""
Filter schools_adjacent_to_pwd_roads_v2.csv down to schools falling inside
an axis-aligned bounding box, defined by four corner coordinates (given in
DMS - degrees/minutes/seconds).

The four input points don't need to form a rectangle themselves - the
bounding box used for filtering is the axis-aligned min/max lat/lon that
encloses all of them (standard "bounding box" meaning). If you actually
want the exact quadrilateral shape as the filter region instead (a
point-in-polygon test rather than a bounding rectangle), that needs a
different script - ask for it if so.

Usage:
    python3 filter_schools_by_bbox.py
"""

import csv

SRC = "schools_adjacent_to_pwd_roads_v2.csv"
OUT = "schools_adjacent_to_pwd_roads_v2_bbox.csv"

# Four corner points supplied as DMS (degrees, minutes, seconds, direction).
CORNER_POINTS_DMS = [
    ((11, 9, 35.20, "N"), (75, 48, 17.15, "E")),
    ((11, 17, 37.68, "N"), (76, 1, 16.84, "E")),
    ((10, 57, 8.21, "N"), (76, 17, 58.93, "E")),
    ((10, 43, 11.46, "N"), (75, 57, 25.54, "E")),
]


def dms_to_dd(deg, minute, sec, direction):
    dd = deg + minute / 60 + sec / 3600
    if direction in ("S", "W"):
        dd = -dd
    return dd


def main():
    coords = []
    for (latd, latm, lats, latdir), (lond, lonm, lons, londir) in CORNER_POINTS_DMS:
        lat = dms_to_dd(latd, latm, lats, latdir)
        lon = dms_to_dd(lond, lonm, lons, londir)
        coords.append((lat, lon))

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    print("Corner points (decimal degrees):")
    for lat, lon in coords:
        print(f"  {lat:.6f}, {lon:.6f}")
    print(f"\nBounding box: lat [{min_lat:.6f}, {max_lat:.6f}], lon [{min_lon:.6f}, {max_lon:.6f}]")

    with open(SRC, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    kept, dropped = [], []
    for r in rows:
        lat = float(r["Latitude"])
        lon = float(r["Longitude"])
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            kept.append(r)
        else:
            dropped.append(r)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\n[OK] {OUT} saved: {len(kept)} of {len(rows)} schools fall inside the bounding box")
    print(f"\n{len(dropped)} schools dropped (outside the box):")
    for r in sorted(dropped, key=lambda x: x["School Name"]):
        print(f"  {r['School Name']} ({r['Educational Sub-District']}) - {r['Latitude']}, {r['Longitude']}")


if __name__ == "__main__":
    main()
