#!/usr/bin/env python3
"""
Kerala PWD Roads Extractor (State Highways + Major District Roads)
====================================================================
Source: OpenStreetMap (c) OpenStreetMap contributors, ODbL license -
        NOT the pwd4u app. The pwd4u app's full road asset dataset is
        gated behind PWD staff credentials (per Kerala PWD / TRL
        Software's iROADS case study), so this script does not touch
        that app at all - it pulls Kerala's PWD-maintained road network
        (State Highways + Major District Roads) from OSM's public,
        openly-licensed data instead, via the free Overpass API.

Tagging scheme (confirmed from the OSM wiki):
  - State Highways:        network=IN:SH:KL
    https://wiki.openstreetmap.org/wiki/India:Roads/Kerala
  - Major District Roads:  network=IN:MDR:KL
    https://wiki.openstreetmap.org/wiki/Kerala-MDR/Malappuram_District
Both categories are Kerala PWD-maintained road classifications.
The network tag sometimes lives on the way itself, and sometimes only
on a parent route "relation" that groups several way segments into one
named/numbered route - this script checks both.

NOTE: First live run showed most of Malappuram's SH/MDR tagging lives on
route RELATIONS rather than directly on ways, and that hitting two
separate Overpass queries back-to-back tripped rate limits (429) on the
free public instances, plus overpass-api.de rejecting the default
requests User-Agent (406). Fixed by merging into a single combined query
and adding a proper User-Agent + 429 retry/backoff. Coverage of Major
District Roads in OSM may still be incomplete in places, so don't be
surprised if the MDR count comes back lower than PWD's official ~2,300 km
inventory for Malappuram - State Highway coverage is documented as much
more complete (~95-100%).

Usage:
    pip install requests
    python pwd_roads_overpass.py

Output (written next to this script):
    malappuram_pwd_roads.geojson  - raw line geometry, for GIS tools
    malappuram_pwd_roads.kml      - styled, ready to import into Google My Maps
"""

import json
import os
import sys
import time
from math import radians, sin, cos, sqrt, atan2
import xml.sax.saxutils as sax

import requests

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]

# Overpass instances commonly reject requests with no identifying
# User-Agent (some return 406/403), and can rate-limit (429) rapid
# repeated requests from the same client - both were hit in testing.
HEADERS = {
    'User-Agent': 'MalappuramPWDRoadsScript/1.0 (personal research use)',
    'Accept': 'application/json, text/plain, */*',
}

AREA_NAME = "Malappuram"
NETWORKS = ["IN:SH:KL", "IN:MDR:KL"]

# Confirmed via diagnose_malappuram_area.py: the ONE OSM relation named
# "Malappuram" tagged boundary=administrative, admin_level=5,
# official_name "Malappuram District", LGD district code 562.
# https://www.openstreetmap.org/relation/2018186
# Pinning to this exact id (rather than matching by name) removes any
# residual ambiguity, though testing showed the name lookup wasn't
# actually ambiguous - see the area-clipping fix below for the real bug.
MALAPPURAM_RELATION_ID = 2018186
MALAPPURAM_AREA_ID = 3600000000 + MALAPPURAM_RELATION_ID  # Overpass area-id convention for relations

GEOJSON_OUT = "malappuram_pwd_roads.geojson"
KML_OUT = "malappuram_pwd_roads.kml"

# Single combined query: ways directly tagged with the network key, PLUS
# route relations tagged with the network key.
#
# IMPORTANT FIX: a naive "(relation...; >>;)" recursion (what the first
# working version used) pulls in a route relation's ENTIRE membership as
# soon as ANY part of it touches the search area - and State Highway
# routes commonly run through several districts. That's what caused the
# first real run to report ~1,830 km of "State Highway" for Malappuram
# vs the official ~375 km (roads from neighboring districts got swept
# in along with the genuinely local ones). This version explicitly
# re-filters relation members back down to only the ways that are
# ALSO geometrically within Malappuram's own boundary
# (way.rel_expanded(area.searchArea)) before using them.
COMBINED_QUERY = """
[out:json][timeout:180];
area({area_id})->.searchArea;

(
{way_clauses}
) -> .direct_ways;

(
{rel_clauses}
) -> .matched_rels;

(.matched_rels; >>;) -> .rel_expanded;
way.rel_expanded(area.searchArea) -> .rel_ways_in_area;

(.direct_ways; .rel_ways_in_area;) -> .final_ways;

.final_ways out body;
.matched_rels out body;
.final_ways;
>;
out skel qt;
"""


def run_overpass_query(query, label):
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(2):  # one retry on the SAME endpoint if rate-limited
            print(f"  [{label}] trying {endpoint}"
                  + (f" (retry after rate limit)" if attempt else "") + " ...")
            try:
                r = requests.post(endpoint, data={'data': query}, headers=HEADERS, timeout=200)
                if r.status_code == 429:
                    print(f"  [{label}] rate-limited (429) on {endpoint}, waiting 10s...")
                    time.sleep(10)
                    continue
                r.raise_for_status()
                data = r.json()
                print(f"  [{label}] OK via {endpoint} - {len(data.get('elements', []))} elements")
                return data
            except Exception as e:
                print(f"  [{label}] failed on {endpoint}: {e}")
                break  # try next endpoint (don't retry non-429 failures)
        time.sleep(2)  # be polite before hitting the next endpoint
    print(f"  [{label}] ALL endpoints failed")
    return {'elements': []}


def resolve_way_geometry(elements):
    """Build {way_id: [(lon,lat), ...]} from a flat elements list."""
    nodes = {}
    ways = {}
    for el in elements:
        if el['type'] == 'node':
            nodes[el['id']] = (el['lon'], el['lat'])
    for el in elements:
        if el['type'] == 'way':
            coords = [nodes[n] for n in el.get('nodes', []) if n in nodes]
            ways[el['id']] = {
                'coords': coords,
                'tags': el.get('tags', {}),
            }
    return ways


def main():
    print("=" * 70)
    print(f"Kerala PWD Roads (State Highways + Major District Roads)")
    print(f"Source: OpenStreetMap via Overpass API - {AREA_NAME} District")
    print("=" * 70)

    way_clauses = "\n".join(f'  way["network"="{n}"](area.searchArea);' for n in NETWORKS)
    rel_clauses = "\n".join(f'  relation["network"="{n}"](area.searchArea);' for n in NETWORKS)

    print("\nFetching directly-tagged ways + route relations (single combined query)...")
    data = run_overpass_query(
        COMBINED_QUERY.format(area_id=MALAPPURAM_AREA_ID, way_clauses=way_clauses, rel_clauses=rel_clauses),
        "combined")

    if not data['elements']:
        print("\n[!] Query returned nothing. Possible causes:")
        print("    - Overpass API is temporarily unreachable/rate-limiting your network")
        print(f"    - The area name '{AREA_NAME}' doesn't match an OSM")
        print("      boundary=administrative relation exactly (could be tagged")
        print("      differently, e.g. with a different admin_level)")
        print("    Try running the same query manually at https://overpass-turbo.eu/")
        print("    to see the raw error, and share it back.")
        sys.exit(1)

    # --- Directly-tagged ways ---
    direct_ways = resolve_way_geometry(data['elements'])
    features_by_way_id = {}
    for way_id, w in direct_ways.items():
        net = w['tags'].get('network', '')
        if net not in NETWORKS or len(w['coords']) < 2:
            continue
        features_by_way_id[way_id] = {
            'id': way_id,
            'network': net,
            'ref': w['tags'].get('ref', ''),
            'name': w['tags'].get('name') or w['tags'].get('ref') or f"way {way_id}",
            'highway': w['tags'].get('highway', ''),
            'coords': w['coords'],
        }

    # --- Ways that only get their network via a parent relation ---
    rel_ways = direct_ways  # same combined elements list already resolved above
    relations = {el['id']: el for el in data['elements'] if el['type'] == 'relation'}
    for rel_id, rel in relations.items():
        net = rel.get('tags', {}).get('network', '')
        if net not in NETWORKS:
            continue
        rel_ref = rel.get('tags', {}).get('ref', '')
        rel_name = rel.get('tags', {}).get('name', rel_ref or f"relation {rel_id}")
        for member in rel.get('members', []):
            if member.get('type') != 'way':
                continue
            way_id = member.get('ref')
            if way_id in features_by_way_id:
                continue  # already have it from the direct-way pass
            w = rel_ways.get(way_id)
            if not w or len(w['coords']) < 2:
                continue
            features_by_way_id[way_id] = {
                'id': way_id,
                'network': net,
                'ref': w['tags'].get('ref', rel_ref),
                'name': w['tags'].get('name') or rel_name,
                'highway': w['tags'].get('highway', ''),
                'coords': w['coords'],
            }

    features = list(features_by_way_id.values())

    if not features:
        print("\n[!] Queries succeeded but no usable road geometry was found.")
        print("    OSM may simply not have this network tagged yet for")
        print(f"    {AREA_NAME} - see the wiki inventory for what SHOULD exist:")
        print("    https://wiki.openstreetmap.org/wiki/Kerala-MDR/Malappuram_District")
        sys.exit(1)

    sh_features = [f for f in features if f['network'] == 'IN:SH:KL']
    mdr_features = [f for f in features if f['network'] == 'IN:MDR:KL']

    sh_km = sum(compute_length_km(f['coords']) for f in sh_features)
    mdr_km = sum(compute_length_km(f['coords']) for f in mdr_features)

    print(f"\nState Highway segments found: {len(sh_features)}  (~{sh_km:.1f} km)")
    print(f"Major District Road segments found: {len(mdr_features)}  (~{mdr_km:.1f} km)")
    print("(PWD's official inventory lists ~375 km of SH and ~2,300 km of MDR")
    print(" for Malappuram - compare against that to gauge OSM's coverage gap.)")

    save_geojson(features, GEOJSON_OUT)
    save_kml(features, KML_OUT)

    print(f"\nDone! To add to your existing school map:")
    print(f"  1. Open the same map as your school pins at mymaps.google.com")
    print(f"  2. Click 'Add layer'")
    print(f"  3. Click 'Import' under the new layer, upload {KML_OUT}")
    print(f"  4. Roads appear as styled lines (red = State Highway, blue = MDR)")


def compute_length_km(coords):
    """Rough length using the haversine formula, no external deps."""
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
                    "name": f['name'],
                    "network": f['network'],
                    "ref": f['ref'],
                    "highway": f['highway'],
                    "osm_way_id": f['id'],
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[c[0], c[1]] for c in f['coords']],
                }
            }
            for f in features
        ]
    }
    with open(filename, 'w', encoding='utf-8') as fh:
        json.dump(geo, fh)
    print(f"✓ GeoJSON saved: {filename}")


def save_kml(features, filename):
    filename = resolve_writable_filename(filename)
    style_by_network = {
        'IN:SH:KL': ('ff0000ff', 4),   # red, thicker - State Highway
        'IN:MDR:KL': ('ffff0000', 3),  # blue - Major District Road
    }

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2">',
             '<Document>',
             '<name>Malappuram PWD Roads (State Highways + MDR)</name>']

    for net_key, (color, width) in style_by_network.items():
        style_id = net_key.replace(':', '_')
        lines.append(f'<Style id="style_{style_id}">')
        lines.append('<LineStyle>')
        lines.append(f'<color>{color}</color>')
        lines.append(f'<width>{width}</width>')
        lines.append('</LineStyle>')
        lines.append('</Style>')

    for f in features:
        style_id = f['network'].replace(':', '_') if f['network'] in style_by_network else ''
        name = sax.escape(f['name'])
        desc = sax.escape(
            f"Network: {f['network']} | Ref: {f['ref']} | "
            f"Highway class: {f['highway']} | OSM way: {f['id']}")
        coord_str = ' '.join(f"{lon},{lat},0" for lon, lat in f['coords'])
        lines.append('<Placemark>')
        lines.append(f'<name>{name}</name>')
        lines.append(f'<description>{desc}</description>')
        if style_id:
            lines.append(f'<styleUrl>#style_{style_id}</styleUrl>')
        lines.append('<LineString>')
        lines.append('<tessellate>1</tessellate>')
        lines.append(f'<coordinates>{coord_str}</coordinates>')
        lines.append('</LineString>')
        lines.append('</Placemark>')

    lines.append('</Document>')
    lines.append('</kml>')

    with open(filename, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    print(f"✓ KML saved: {filename}")


if __name__ == "__main__":
    main()
