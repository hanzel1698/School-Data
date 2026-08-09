#!/usr/bin/env python3
"""
Kerala PWD Roads Extractor v2 - from PWD's own RMMS citizen portal
====================================================================
Source: https://pwdrmms.kerala.gov.in/citizen/portal/ - PWD's Road
Management and Maintenance System (RMMS), NOT OpenStreetMap. This is
PWD's own authoritative State Highway + Major District Road network,
served as unauthenticated Mapbox vector tiles:

    https://pwdrmms.kerala.gov.in/citizen/kstp-network-sections/{z}/{x}/{y}.mvt

Replaces pwd_roads_overpass.py, whose OSM-sourced data was badly
incomplete for MDR (~728km found vs an official ~2,300km for
Malappuram - OSM simply hasn't digitized most MDR segments here).

ZOOM LEVEL - deviates from the original plan of z=17:
  z=17 covering Malappuram's padded bbox is ~96,400 tiles - confirmed
  by direct calculation, not an estimate. That's impractical (hours of
  requests hammering a government server) and unnecessary. Testing
  showed this tile source returns full, non-simplified-looking geometry
  at every zoom from 8 to 16 (same `measured_length` property regardless
  of zoom, and per-tile geometry is genuinely clipped to the tile - not
  progressively simplified away). Quantization error at z=13 is only
  ~1.2m (tile width in degrees / 4096 units), utterly negligible next
  to the 100m adjacency threshold. z=13 covers the same padded bbox in
  418 tiles - about 230x fewer requests than z=17, runs in a few
  minutes instead of hours, and is far more polite to PWD's server.

MERGING ACROSS TILES - deviates from the original "dedupe by id, keep
one copy" plan:
  Verified directly (see conversation) that this endpoint clips long
  roads at tile boundaries, same as standard MVT practice: a single
  58km road (id=81) appears as a ~226-point piece in one tile and a
  complementary ~90-point piece in the neighboring tile, not as
  duplicate copies of the whole thing. Deduping "keep one copy" would
  have silently truncated every road that crosses a tile edge - i.e.
  most of them. Instead: every distinct piece (by rounded coordinates)
  is kept as its own LineString feature, sharing the parent road's
  `id`/`section_label`/`road_name`/`measured_length`/`road_class`
  properties. Only byte-identical pieces (which can occur when a short
  segment falls entirely within two tiles' overlap buffer) are deduped.

CLASSIFICATION:
  section_label formats vary more than the simple regex in the original
  plan assumed (confirmed via a live survey of 1,500+ distinct labels):
    KPWD/MPM/SH/73/1        - 5 parts, district code before class
    KPWD/MDR/503030101/19   - 4 parts, class right after KPWD
    KPWD/NH66/303010102/2   - 4 parts, class+route fused ("NH66")
    KPWD/SH39/...           - class+route fused, no district code
    KPWD/TSR/SH/69/2/1      - 6 parts (rare)
  So instead of a fixed-position regex, every '/'-separated part is
  scanned against a whitelist of known class prefixes (SH, MDR, NH,
  ODR, VR, PMGSY), taking the first match. This correctly skips
  district codes (MPM, TSR, KKD, EKM, ...) which would otherwise be
  misidentified as the class under a naive "first ALL-CAPS token" rule.

Usage:
    pip install requests mapbox-vector-tile
    python pwd_roads_rmms_extractor.py

Output (written next to this script):
    malappuram_pwd_roads_v2.geojson
    malappuram_pwd_roads_v2.kml
"""

import json
import math
import os
import re
import sys
import threading
import time
import xml.sax.saxutils as sax
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# Force line-buffered stdout even when redirected to a file/pipe (the default
# is fully-buffered in that case, which is why the first version of this
# script appeared to hang - nothing printed until it finished). This makes
# every progress line show up immediately for live monitoring.
sys.stdout.reconfigure(line_buffering=True)

try:
    import mapbox_vector_tile
except ImportError:
    print("Missing dependency. Install it with:\n    pip install mapbox-vector-tile")
    sys.exit(1)

TILE_URL_TEMPLATE = "https://pwdrmms.kerala.gov.in/citizen/kstp-network-sections/{z}/{x}/{y}.mvt"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
    'Referer': 'https://pwdrmms.kerala.gov.in/citizen/portal/',
}

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
BBOX_PAD_DEG = 0.03

ZOOM = 13
MAX_RETRIES = 4
CONCURRENCY = 8  # concurrent tile fetches - still polite (one server, shared connection pool), much faster than serial
PROGRESS_EVERY = 40  # kept low-volume: overly chatty output can trip an external log-noise safeguard

GEOJSON_OUT = "malappuram_pwd_roads_v2.geojson"
KML_OUT = "malappuram_pwd_roads_v2.kml"

# Known Kerala PWD / national road-class prefixes seen in section_label,
# e.g. "SH", "SH39", "MDR", "MDR19A", "NH66". District codes (MPM, TSR,
# KKD, EKM, ...) deliberately do NOT match this, so they're skipped when
# scanning label parts left-to-right.
CLASS_RE = re.compile(r'^(SH|MDR|NH|ODR|VR|PMGSY)\d*[A-Z]?$')

# Prior OSM-based run, for the completeness comparison printed at the end.
OSM_SH_KM = 467
OSM_MDR_KM = 728


def get_malappuram_bbox():
    """Fetch Malappuram district's bounding box from Overpass, padded for safety margin."""
    query = f"[out:json][timeout:60];relation({MALAPPURAM_RELATION_ID});out bb;"
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"  Querying {endpoint} for relation {MALAPPURAM_RELATION_ID} bounds...")
            r = requests.post(endpoint, data={'data': query}, headers=OVERPASS_HEADERS, timeout=60)
            r.raise_for_status()
            data = r.json()
            bounds = data['elements'][0]['bounds']
            minlat, minlon = bounds['minlat'], bounds['minlon']
            maxlat, maxlon = bounds['maxlat'], bounds['maxlon']
            print(f"  Raw bbox: lat [{minlat}, {maxlat}], lon [{minlon}, {maxlon}]")
            minlat -= BBOX_PAD_DEG
            minlon -= BBOX_PAD_DEG
            maxlat += BBOX_PAD_DEG
            maxlon += BBOX_PAD_DEG
            print(f"  Padded by {BBOX_PAD_DEG} deg: lat [{minlat:.4f}, {maxlat:.4f}], "
                  f"lon [{minlon:.4f}, {maxlon:.4f}]")
            return minlat, minlon, maxlat, maxlon
        except Exception as e:
            print(f"  Failed on {endpoint}: {e}")
    print("[!] Could not get Malappuram bbox from Overpass. Aborting.")
    sys.exit(1)


def deg2tile(lat, lon, z):
    lat_rad = math.radians(lat)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_list_for_bbox(minlat, minlon, maxlat, maxlon, z):
    x1, y1 = deg2tile(maxlat, minlon, z)  # top-left (max lat = smallest y)
    x2, y2 = deg2tile(minlat, maxlon, z)  # bottom-right
    xs = range(min(x1, x2), max(x1, x2) + 1)
    ys = range(min(y1, y2), max(y1, y2) + 1)
    return [(x, y) for x in xs for y in ys]


def tile_pixel_to_lonlat(px, py, z, x, y, extent=4096):
    """Standard inverse slippy-map tile math, generalized to fractional tile position."""
    n = 2 ** z
    lon = (x + px / extent) / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + py / extent) / n)))
    lat = math.degrees(lat_rad)
    return lon, lat


def fetch_tile(session, z, x, y):
    """Fetch and decode one tile. Returns list of features (raw, tile-local coords) or [] if empty."""
    url = TILE_URL_TEMPLATE.format(z=z, x=x, y=y)
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            if attempt == MAX_RETRIES - 1:
                print(f"  [!] {z}/{x}/{y}: giving up after {MAX_RETRIES} attempts ({e})")
                return []
            time.sleep(delay)
            delay *= 2
            continue

        if r.status_code == 200 and not r.content:
            return []  # legitimately empty tile: 200 OK with an empty body (no roads in this tile)
        elif r.status_code == 200:
            try:
                # y_coord_down=True disables the library's default y-flip so we get
                # raw tile-pixel coordinates (y increasing downward/southward),
                # which is what tile_pixel_to_lonlat() above expects.
                decoded = mapbox_vector_tile.decode(
                    r.content, per_layer_options={'all': {'y_coord_down': True}})
            except Exception as e:
                print(f"  [!] {z}/{x}/{y}: MVT decode failed ({e}), skipping")
                return []
            return decoded.get('all', {}).get('features', [])
        elif r.status_code in (204, 404):
            return []  # legitimately empty tile (e.g. over water / district edge)
        elif r.status_code == 429:
            time.sleep(delay)
            delay *= 2
        else:
            if attempt == MAX_RETRIES - 1:
                print(f"  [!] {z}/{x}/{y}: HTTP {r.status_code} after {MAX_RETRIES} attempts, skipping")
                return []
            time.sleep(delay)
            delay *= 2
    return []


def classify(section_label):
    for part in section_label.split('/')[1:]:  # skip leading "KPWD"
        m = CLASS_RE.match(part)
        if m:
            return m.group(1)
    return 'OTHER'


def flatten_pieces(coords):
    """A LineString's coords is [[x,y],...]; a MultiLineString's is [[[x,y],...],...].
    Normalize both to a list of pieces, each a list of [x,y]."""
    if not coords:
        return []
    if isinstance(coords[0][0], (int, float)):
        return [coords]
    return coords


def main():
    print("=" * 70)
    print("Kerala PWD Roads v2 - from PWD RMMS citizen portal vector tiles")
    print("=" * 70)

    print("\nStep 1: Malappuram district bounding box (Overpass)")
    minlat, minlon, maxlat, maxlon = get_malappuram_bbox()

    print(f"\nStep 2: computing z={ZOOM} tile grid")
    tiles = tile_list_for_bbox(minlat, minlon, maxlat, maxlon, ZOOM)
    print(f"  {len(tiles)} tiles to fetch at z={ZOOM} "
          f"(for reference: z=17 would need ~96,400 tiles - infeasible, see script docstring)")

    print(f"\nStep 3: fetching + decoding tiles ({CONCURRENCY} concurrent workers, "
          f"shared connection pool - no per-request handshake overhead)...")
    # pieces_by_id[id] -> {'props': {...}, 'pieces': set of rounded-coord tuples}
    pieces_by_id = defaultdict(lambda: {'props': None, 'pieces': {}})
    empty_tiles = 0
    total_raw_features = 0
    completed = 0
    lock = threading.Lock()
    start_time = time.time()

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=CONCURRENCY, pool_maxsize=CONCURRENCY)
    session.mount('https://', adapter)

    def process_tile(tx, ty):
        return tx, ty, fetch_tile(session, ZOOM, tx, ty)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(process_tile, tx, ty) for tx, ty in tiles]
        for future in as_completed(futures):
            tx, ty, features = future.result()
            with lock:
                completed += 1
                if not features:
                    empty_tiles += 1
                for feat in features:
                    total_raw_features += 1
                    props = feat.get('properties', {})
                    fid = props.get('id')
                    if fid is None:
                        continue
                    geom = feat.get('geometry', {})
                    for piece in flatten_pieces(geom.get('coordinates', [])):
                        if len(piece) < 2:
                            continue
                        lonlat_piece = tuple(
                            (round(lon, 7), round(lat, 7))
                            for lon, lat in (tile_pixel_to_lonlat(px, py, ZOOM, tx, ty) for px, py in piece)
                        )
                        entry = pieces_by_id[fid]
                        if entry['props'] is None:
                            entry['props'] = props
                        entry['pieces'][lonlat_piece] = None  # dict used as an ordered set

                if completed % PROGRESS_EVERY == 0 or completed == len(tiles):
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta_s = (len(tiles) - completed) / rate if rate > 0 else 0
                    print(f"  ...{completed}/{len(tiles)} tiles ({100 * completed / len(tiles):.0f}%) | "
                          f"{len(pieces_by_id)} road ids so far | {empty_tiles} empty | "
                          f"{rate:.1f} tiles/s | ETA {eta_s:.0f}s")

    print(f"\n  Done fetching in {time.time() - start_time:.0f}s. {total_raw_features} raw tile-features seen, "
          f"deduped to {len(pieces_by_id)} distinct road ids.")

    if not pieces_by_id:
        print("[!] No road data retrieved - check connectivity / endpoint. Aborting.")
        sys.exit(1)

    print("\nStep 4/5: building output features (classifying road_class, "
          "flattening deduped pieces)...")
    out_features = []  # each: dict with id, section_label, road_name, measured_length, road_class, coords
    for fid, entry in pieces_by_id.items():
        props = entry['props']
        section_label = props.get('section_label', '')
        road_class = classify(section_label)
        for piece in entry['pieces'].keys():
            out_features.append({
                'id': fid,
                'section_label': section_label,
                'road_name': props.get('road_name', ''),
                'measured_length': props.get('measured_length', 0),
                'road_class': road_class,
                'coords': [list(c) for c in piece],
            })

    print(f"  {len(out_features)} output LineString features "
          f"(roads fragment across the {len(tiles)}-tile grid, so this is > "
          f"the {len(pieces_by_id)} distinct road ids - expected)")

    save_geojson(out_features, GEOJSON_OUT)
    save_kml(out_features, KML_OUT)

    print_summary(pieces_by_id)


def print_summary(pieces_by_id):
    """Stats use each id's own `measured_length` property (authoritative total per
    road segment, from PWD's own database) rather than summing piece geometry -
    that avoids any double-counting from tile-boundary buffer overlap."""
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    by_class_km = defaultdict(float)
    by_class_count = defaultdict(int)
    for fid, entry in pieces_by_id.items():
        props = entry['props']
        road_class = classify(props.get('section_label', ''))
        by_class_km[road_class] += props.get('measured_length', 0) / 1000.0
        by_class_count[road_class] += 1

    total_km = sum(by_class_km.values())
    total_segments = sum(by_class_count.values())
    print(f"Total distinct road segments (unique ids): {total_segments}")
    print(f"Total length: {total_km:.1f} km")
    print("\nBreakdown by road_class:")
    for cls in sorted(by_class_km, key=lambda c: -by_class_km[c]):
        print(f"  {cls:8s}: {by_class_count[cls]:5d} segments, {by_class_km[cls]:8.1f} km")

    print("\nComparison against the prior OSM-derived extraction:")
    sh_km = by_class_km.get('SH', 0)
    mdr_km = by_class_km.get('MDR', 0)
    print(f"  SH:  OSM {OSM_SH_KM} km  ->  RMMS {sh_km:.1f} km")
    print(f"  MDR: OSM {OSM_MDR_KM} km  ->  RMMS {mdr_km:.1f} km "
          f"({mdr_km / OSM_MDR_KM:.1f}x more MDR coverage)" if OSM_MDR_KM else "")
    print("=" * 70)


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
                "geometry": {
                    "type": "LineString",
                    "coordinates": f['coords'],
                }
            }
            for f in features
        ]
    }
    with open(filename, 'w', encoding='utf-8') as fh:
        json.dump(geo, fh)
    print(f"\n[OK] GeoJSON saved: {filename}")


def save_kml(features, filename):
    filename = resolve_writable_filename(filename)
    style_by_class = {
        'SH': ('ff0000ff', 4),   # red, thicker - State Highway (KML aabbggrr)
        'MDR': ('ffff0000', 3),  # blue - Major District Road
    }
    default_style = ('ff888888', 2)  # grey - anything else (NH, ODR, VR, OTHER, ...)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2">',
             '<Document>',
             '<name>Malappuram PWD Roads v2 (RMMS - State Highways + MDR)</name>']

    all_classes = sorted(set(f['road_class'] for f in features))
    for cls in all_classes:
        color, width = style_by_class.get(cls, default_style)
        lines.append(f'<Style id="style_{cls}">')
        lines.append('<LineStyle>')
        lines.append(f'<color>{color}</color>')
        lines.append(f'<width>{width}</width>')
        lines.append('</LineStyle>')
        lines.append('</Style>')

    for f in features:
        name = sax.escape(f['road_name'] or f['section_label'])
        desc = sax.escape(
            f"Section: {f['section_label']} | Class: {f['road_class']} | "
            f"Length: {f['measured_length']}m | id: {f['id']}")
        coord_str = ' '.join(f"{lon},{lat},0" for lon, lat in f['coords'])
        lines.append('<Placemark>')
        lines.append(f'<name>{name}</name>')
        lines.append(f'<description>{desc}</description>')
        lines.append(f'<styleUrl>#style_{f["road_class"]}</styleUrl>')
        lines.append('<LineString>')
        lines.append('<tessellate>1</tessellate>')
        lines.append(f'<coordinates>{coord_str}</coordinates>')
        lines.append('</LineString>')
        lines.append('</Placemark>')

    lines.append('</Document>')
    lines.append('</kml>')

    with open(filename, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print(f"[OK] KML saved: {filename}")


if __name__ == "__main__":
    main()
