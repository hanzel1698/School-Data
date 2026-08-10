#!/usr/bin/env python3
"""
Filter schools_adjacent_to_pwd_roads_v2.csv down to schools falling inside
the exact quadrilateral formed by four corner coordinates (given in DMS -
degrees/minutes/seconds), connected in the given order - a true
point-in-polygon test, not just the enclosing bounding box (see
filter_schools_by_bbox.py for that simpler variant).

Usage:
    pip install shapely
    python3 filter_schools_by_polygon.py
"""

import csv

try:
    from shapely.geometry import Point, Polygon
except ImportError:
    print("This script requires shapely. Install it with: pip install shapely")
    raise SystemExit(1)

SRC = "schools_adjacent_to_pwd_roads_v2.csv"
OUT = "schools_adjacent_to_pwd_roads_v2_polygon.csv"

# Four corner points, in order, as DMS (degrees, minutes, seconds, direction).
# Connecting them in this order (and closing back to the first) forms the
# filter polygon - verified simple/non-self-intersecting.
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
    coords_latlon = []
    for (latd, latm, lats, latdir), (lond, lonm, lons, londir) in CORNER_POINTS_DMS:
        lat = dms_to_dd(latd, latm, lats, latdir)
        lon = dms_to_dd(lond, lonm, lons, londir)
        coords_latlon.append((lat, lon))

    print("Corner points (decimal degrees), in polygon order:")
    for lat, lon in coords_latlon:
        print(f"  {lat:.6f}, {lon:.6f}")

    polygon = Polygon([(lon, lat) for lat, lon in coords_latlon])  # shapely wants (x=lon, y=lat)
    if not polygon.is_valid or not polygon.is_simple:
        print("[!] The given points form a self-intersecting polygon in this order - aborting.")
        raise SystemExit(1)
    print(f"\nPolygon area: {polygon.area:.4f} deg^2 (valid, non-self-intersecting)")

    with open(SRC, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    kept, dropped = [], []
    for r in rows:
        lat = float(r["Latitude"])
        lon = float(r["Longitude"])
        if polygon.covers(Point(lon, lat)):  # covers() includes points exactly on the boundary
            kept.append(r)
        else:
            dropped.append(r)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\n[OK] {OUT} saved: {len(kept)} of {len(rows)} schools fall inside the polygon")
    print(f"\n{len(dropped)} schools dropped (outside the polygon):")
    for r in sorted(dropped, key=lambda x: x["School Name"]):
        print(f"  {r['School Name']} ({r['Educational Sub-District']}) - {r['Latitude']}, {r['Longitude']}")


if __name__ == "__main__":
    main()
