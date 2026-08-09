#!/usr/bin/env python3
"""
Clip malappuram_pwd_roads_v2.geojson to the actual Malappuram district
polygon (not just its bounding box).
====================================================================
pwd_roads_rmms_extractor.py fetches every z=13 tile that covers a PADDED
BOUNDING BOX around Malappuram. That's necessary to make sure no road
near the border gets missed, but it also means the raw output includes
real roads from neighboring districts (Palakkad, Kozhikode, Thrissur,
Wayanad) that fall inside the rectangle but outside the actual district.

Confirmed by comparing areas: the assembled district polygon is
~0.295 deg^2 (~3,560 km^2, matching Malappuram's real ~3,550 km^2
area), while the padded bbox is ~0.612 deg^2 (~7,400 km^2) - more than
2x larger. That lines up almost exactly with the observed ~2x MDR
over-count relative to the official ~2,300km figure, which is what
gave this away in the first place.

This script:
  1. Fetches Malappuram's boundary relation (2018186) from Overpass with
     full way geometry, assembles it into a polygon with shapely
     (cached to malappuram_district_polygon.wkt so this only needs to
     run once).
  2. Clips every road piece in malappuram_pwd_roads_v2.geojson against
     that polygon (shapely intersection - trims segments that cross the
     border exactly at the border, drops segments entirely outside).
  3. Overwrites malappuram_pwd_roads_v2.geojson / .kml with the clipped
     result and prints corrected summary stats.

Usage:
    pip install shapely requests
    python clip_roads_to_district.py
"""

import json
import os
import re
import sys
import xml.sax.saxutils as sax
from collections import defaultdict
from math import radians, sin, cos, sqrt, atan2

import requests

try:
    from shapely.geometry import LineString, MultiLineString, GeometryCollection, mapping, shape
    from shapely.ops import polygonize, unary_union
    from shapely import wkt as shapely_wkt
except ImportError:
    print("Missing dependency. Install it with:\n    pip install shapely")
    sys.exit(1)

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
OVERPASS_HEADERS = {
    'User-Agent': 'MalappuramPWDRoadsScript/1.0 (personal research use)',
    'Accept': 'application/json, text/plain, */*',
}
MALAPPURAM_RELATION_ID = 2018186

GEOJSON_PATH = "malappuram_pwd_roads_v2.geojson"
KML_PATH = "malappuram_pwd_roads_v2.kml"
POLYGON_WKT_PATH = "malappuram_district_polygon.wkt"

OSM_SH_KM = 467
OSM_MDR_KM = 728
OFFICIAL_SH_KM = 375
OFFICIAL_MDR_KM = 2300


def get_malappuram_polygon():
    """Assemble the real district polygon (not bbox) from Overpass, with a WKT cache."""
    if os.path.exists(POLYGON_WKT_PATH):
        print(f"  Loading cached polygon from {POLYGON_WKT_PATH}")
        with open(POLYGON_WKT_PATH, encoding='utf-8') as f:
            return shapely_wkt.loads(f.read())

    query = f"""
    [out:json][timeout:120];
    relation({MALAPPURAM_RELATION_ID});
    (._;>;);
    out geom;
    """
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"  Querying {endpoint} for full boundary geometry...")
            r = requests.post(endpoint, data={'data': query}, headers=OVERPASS_HEADERS, timeout=150)
            r.raise_for_status()
            data = r.json()
            ways = [el for el in data['elements'] if el['type'] == 'way']
            lines = []
            for w in ways:
                geom = w.get('geometry')
                if not geom or len(geom) < 2:
                    continue
                lines.append(LineString([(pt['lon'], pt['lat']) for pt in geom]))
            polys = list(polygonize(lines))
            if not polys:
                print(f"  [!] polygonize produced nothing via {endpoint}, trying next endpoint")
                continue
            merged = unary_union(polys)
            with open(POLYGON_WKT_PATH, "w", encoding='utf-8') as f:
                f.write(merged.wkt)
            print(f"  Polygon assembled from {len(ways)} boundary ways, "
                  f"area {merged.area:.4f} deg^2, cached to {POLYGON_WKT_PATH}")
            return merged
        except Exception as e:
            print(f"  Failed on {endpoint}: {e}")
    print("[!] Could not build Malappuram polygon from any Overpass endpoint. Aborting.")
    sys.exit(1)


def haversine_km(coords):
    total = 0.0
    R = 6371.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        total += R * c
    return total


def extract_lines(geom):
    """Flatten a shapely intersection result (LineString / MultiLineString /
    GeometryCollection / empty) into a list of coordinate-list pieces."""
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [list(geom.coords)] if len(geom.coords) >= 2 else []
    if isinstance(geom, MultiLineString):
        return [list(g.coords) for g in geom.geoms if len(g.coords) >= 2]
    if isinstance(geom, GeometryCollection):
        out = []
        for g in geom.geoms:
            out.extend(extract_lines(g))
        return out
    return []  # points/polygons from a line-polygon intersection are degenerate, ignore


def resolve_writable_filename(filename):
    base, ext = os.path.splitext(filename)
    candidate = filename
    n = 1
    while n <= 30:
        try:
            with open(candidate, 'ab'):
                pass
            if candidate != filename:
                print(f"  [!] '{filename}' appears locked - writing to '{candidate}' instead.")
            return candidate
        except PermissionError:
            candidate = f"{base} ({n}){ext}"
            n += 1
    raise PermissionError(f"Could not find a writable filename for {filename}")


def save_geojson(features, filename):
    filename = resolve_writable_filename(filename)
    geo = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": f['id'],
                    "section_label": f['section_label'],
                    "road_name": f['road_name'],
                    "measured_length": f['measured_length'],
                    "road_class": f['road_class'],
                },
                "geometry": {"type": "LineString", "coordinates": f['coords']},
            }
            for f in features
        ]
    }
    with open(filename, 'w', encoding='utf-8') as fh:
        json.dump(geo, fh)
    print(f"[OK] GeoJSON saved: {filename}")


def save_kml(features, filename):
    filename = resolve_writable_filename(filename)
    style_by_class = {
        'SH': ('ff0000ff', 4),
        'MDR': ('ffff0000', 3),
    }
    default_style = ('ff888888', 2)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2">',
             '<Document>',
             '<name>Malappuram PWD Roads v2 (RMMS - State Highways + MDR, clipped to district)</name>']

    all_classes = sorted(set(f['road_class'] for f in features))
    for cls in all_classes:
        color, width = style_by_class.get(cls, default_style)
        lines.append(f'<Style id="style_{cls}"><LineStyle><color>{color}</color>'
                      f'<width>{width}</width></LineStyle></Style>')

    for f in features:
        name = sax.escape(f['road_name'] or f['section_label'])
        desc = sax.escape(f"Section: {f['section_label']} | Class: {f['road_class']} | "
                           f"Length: {f['measured_length']}m | id: {f['id']}")
        coord_str = ' '.join(f"{lon},{lat},0" for lon, lat in f['coords'])
        lines.append(f'<Placemark><name>{name}</name><description>{desc}</description>'
                      f'<styleUrl>#style_{f["road_class"]}</styleUrl>'
                      f'<LineString><tessellate>1</tessellate><coordinates>{coord_str}</coordinates>'
                      f'</LineString></Placemark>')

    lines.append('</Document></kml>')
    with open(filename, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print(f"[OK] KML saved: {filename}")


def main():
    print("=" * 70)
    print("Clipping malappuram_pwd_roads_v2.geojson to the real district polygon")
    print("=" * 70)

    if not os.path.exists(GEOJSON_PATH):
        print(f"[!] {GEOJSON_PATH} not found. Run pwd_roads_rmms_extractor.py first.")
        sys.exit(1)

    print("\nStep 1: district polygon")
    polygon = get_malappuram_polygon()

    print(f"\nStep 2: loading {GEOJSON_PATH}")
    with open(GEOJSON_PATH, encoding='utf-8') as f:
        geo = json.load(f)
    raw_features = geo['features']
    print(f"  {len(raw_features)} raw (unclipped) features loaded")

    print("\nStep 3: clipping each feature against the district polygon...")
    clipped_features = []
    dropped_fully_outside = 0
    trimmed_partial = 0
    for feat in raw_features:
        props = feat['properties']
        coords = feat['geometry']['coordinates']
        if len(coords) < 2:
            continue
        line = LineString(coords)
        if polygon.contains(line):
            clipped_features.append({**props, 'coords': coords})
            continue
        intersection = line.intersection(polygon)
        pieces = extract_lines(intersection)
        if not pieces:
            dropped_fully_outside += 1
            continue
        trimmed_partial += 1
        for piece in pieces:
            clipped_features.append({**props, 'coords': [list(c) for c in piece]})

    print(f"  {len(clipped_features)} features after clipping "
          f"({dropped_fully_outside} dropped - fully outside district, "
          f"{trimmed_partial} partially trimmed at the border)")

    save_geojson(clipped_features, GEOJSON_PATH)
    save_kml(clipped_features, KML_PATH)

    print("\n" + "=" * 70)
    print("CORRECTED SUMMARY (clipped to actual district polygon)")
    print("=" * 70)
    km_by_class = defaultdict(float)
    count_by_class = defaultdict(int)
    unique_ids_by_class = defaultdict(set)
    for f in clipped_features:
        km_by_class[f['road_class']] += haversine_km(f['coords'])
        count_by_class[f['road_class']] += 1
        unique_ids_by_class[f['road_class']].add(f['id'])

    total_km = sum(km_by_class.values())
    print(f"Total length (clipped, geometry-based): {total_km:.1f} km")
    print("\nBreakdown by road_class:")
    for cls in sorted(km_by_class, key=lambda c: -km_by_class[c]):
        print(f"  {cls:8s}: {count_by_class[cls]:5d} pieces, "
              f"{len(unique_ids_by_class[cls]):5d} unique ids, {km_by_class[cls]:8.1f} km")

    print("\nComparison against prior figures:")
    sh_km = km_by_class.get('SH', 0)
    mdr_km = km_by_class.get('MDR', 0)
    print(f"  SH:  official ~{OFFICIAL_SH_KM} km | OSM extraction {OSM_SH_KM} km | RMMS (clipped) {sh_km:.1f} km")
    print(f"  MDR: official ~{OFFICIAL_MDR_KM} km | OSM extraction {OSM_MDR_KM} km | RMMS (clipped) {mdr_km:.1f} km")
    print("=" * 70)


if __name__ == "__main__":
    main()
