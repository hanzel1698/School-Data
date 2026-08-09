#!/usr/bin/env python3
"""
Find schools adjacent to Kerala PWD roads (State Highways + Major District Roads)
====================================================================================
Combines the outputs of the previous two scripts:
  - schools_malappuram_my_maps_import.csv  (from kite_scraper_final.py)
  - malappuram_pwd_roads.geojson           (from pwd_roads_overpass.py)

For every school that has coordinates, computes the shortest distance (in
meters) from the school to the nearest Kerala PWD road segment (State
Highway or Major District Road, per OpenStreetMap's network=IN:SH:KL /
network=IN:MDR:KL tagging), and flags schools within ADJACENCY_THRESHOLD_M
meters as "adjacent".

Distances use a local equirectangular projection centered on the road
network's centroid - accurate to well under 1% distortion at Malappuram's
scale (a few tens of km across), more than precise enough for a 100m
threshold.

CAVEATS:
  - Only schools with usable coordinates are checked (381 of 471 in the
    last run - the rest had no location data published on the KITE
    Sametham site and are skipped here, not marked "not adjacent").
  - This is only as good as OpenStreetMap's road-mapping completeness for
    Malappuram. State Highway coverage is documented as largely complete;
    Major District Road coverage may have gaps in OSM, so a school next to
    an MDR segment that simply hasn't been digitized yet could be missed.
    If a sub-district's results look suspiciously sparse, check that
    sub-district's road segment/km count from the previous script's output
    before concluding there's really no nearby PWD road.

Usage:
    pip install numpy reportlab
    python schools_near_pwd_roads.py

Output (written next to this script):
    schools_all_road_distances.csv     - every checked school, distance to nearest PWD road
    schools_adjacent_to_pwd_roads.csv  - only schools within the threshold
    schools_adjacent_to_pwd_roads.pdf  - same, grouped by Educational Sub-District
"""

import csv
import json
import os
import sys
from collections import defaultdict
from math import radians, cos

try:
    import numpy as np
except ImportError:
    print("This script requires numpy. Install it with: pip install numpy")
    sys.exit(1)

SCHOOLS_CSV = "schools_malappuram_my_maps_import.csv"
ROADS_GEOJSON = "malappuram_pwd_roads.geojson"
ADJACENCY_THRESHOLD_M = 100

ALL_OUT = "schools_all_road_distances.csv"
ADJACENT_CSV_OUT = "schools_adjacent_to_pwd_roads.csv"
ADJACENT_PDF_OUT = "schools_adjacent_to_pwd_roads.pdf"

R_EARTH = 6371000.0

FIELDNAMES = [
    'School Name', 'Educational District', 'Educational Sub-District',
    'Block Name', 'Level Name', 'Distance to Nearest PWD Road (m)',
    'Nearest Road Type', 'Nearest Road Name/Ref', 'Latitude', 'Longitude',
]


def resolve_writable_filename(filename):
    """Falls back to 'name (1).ext' etc. if the file is locked (e.g. open in Excel)."""
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


def load_schools(path):
    if not os.path.exists(path):
        print(f"[!] {path} not found in this folder. Run kite_scraper_final.py first.")
        sys.exit(1)
    schools = []
    skipped_no_coords = 0
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row['Latitude'])
                lon = float(row['Longitude'])
            except (ValueError, KeyError, TypeError):
                skipped_no_coords += 1
                continue
            schools.append({
                'name': row.get('Name', ''),
                'lat': lat,
                'lon': lon,
                'edu_district': row.get('Educational District', ''),
                'sub_district': row.get('Educational Sub-District', ''),
                'block': row.get('Block Name', ''),
                'level': row.get('Level Name', ''),
                'phone': row.get('Phone', ''),
                'code': row.get('School Code', ''),
            })
    print(f"Loaded {len(schools)} schools with coordinates from {path}"
          + (f" ({skipped_no_coords} rows skipped - no coordinates)" if skipped_no_coords else ""))
    return schools


def load_roads(path):
    if not os.path.exists(path):
        print(f"[!] {path} not found in this folder. Run pwd_roads_overpass.py first.")
        sys.exit(1)
    with open(path, encoding='utf-8') as f:
        geo = json.load(f)
    roads = []
    for feat in geo['features']:
        coords = feat['geometry']['coordinates']  # [[lon,lat], ...]
        if len(coords) < 2:
            continue
        roads.append({
            'name': feat['properties'].get('name', ''),
            'network': feat['properties'].get('network', ''),
            'ref': feat['properties'].get('ref', ''),
            'highway': feat['properties'].get('highway', ''),
            'coords': coords,
        })
    print(f"Loaded {len(roads)} road segments from {path}")
    return roads


def project(lon, lat, ref_lon, ref_lat):
    """Equirectangular projection to local meters, centered on (ref_lon, ref_lat)."""
    x = radians(lon - ref_lon) * R_EARTH * cos(radians(ref_lat))
    y = radians(lat - ref_lat) * R_EARTH
    return x, y


def point_segment_distance(p, a, b):
    """
    Vectorized distance from point p (shape (2,)) to each segment defined
    by a[i]->b[i] (each shape (N,2)). Returns an array of distances (N,).
    """
    ap = p - a
    ab = b - a
    ab_len_sq = np.sum(ab * ab, axis=1)
    ab_len_sq = np.where(ab_len_sq == 0, 1e-12, ab_len_sq)
    t = np.sum(ap * ab, axis=1) / ab_len_sq
    t = np.clip(t, 0.0, 1.0)
    proj = a + ab * t[:, None]
    diff = p - proj
    return np.sqrt(np.sum(diff * diff, axis=1))


def main():
    print("=" * 70)
    print("Finding schools adjacent to Kerala PWD roads (State Highways + MDR)")
    print(f"Adjacency threshold: {ADJACENCY_THRESHOLD_M} m")
    print("=" * 70)

    schools = load_schools(SCHOOLS_CSV)
    roads = load_roads(ROADS_GEOJSON)

    if not schools or not roads:
        print("Nothing to do - check the input files.")
        sys.exit(1)

    all_lons = [c[0] for r in roads for c in r['coords']]
    all_lats = [c[1] for r in roads for c in r['coords']]
    ref_lon = sum(all_lons) / len(all_lons)
    ref_lat = sum(all_lats) / len(all_lats)
    print(f"Projection reference point: {ref_lat:.5f}, {ref_lon:.5f}")

    seg_a, seg_b, seg_road_idx = [], [], []
    for ridx, r in enumerate(roads):
        proj_coords = [project(lon, lat, ref_lon, ref_lat) for lon, lat in r['coords']]
        for i in range(len(proj_coords) - 1):
            seg_a.append(proj_coords[i])
            seg_b.append(proj_coords[i + 1])
            seg_road_idx.append(ridx)

    seg_a = np.array(seg_a)
    seg_b = np.array(seg_b)
    seg_road_idx = np.array(seg_road_idx)
    print(f"Total road segments to check against: {len(seg_a)}")

    results = []
    for i, s in enumerate(schools):
        px, py = project(s['lon'], s['lat'], ref_lon, ref_lat)
        p = np.array([px, py])
        dists = point_segment_distance(p, seg_a, seg_b)
        nearest_idx = int(np.argmin(dists))
        nearest_dist = float(dists[nearest_idx])
        nearest_road = roads[seg_road_idx[nearest_idx]]

        results.append({
            **s,
            'nearest_distance_m': round(nearest_dist, 1),
            'nearest_road_name': nearest_road['name'],
            'nearest_road_network': (
                'State Highway' if nearest_road['network'] == 'IN:SH:KL'
                else 'MDR' if nearest_road['network'] == 'IN:MDR:KL'
                else nearest_road['network']
            ),
            'nearest_road_ref': nearest_road['ref'],
        })

        if (i + 1) % 50 == 0 or (i + 1) == len(schools):
            print(f"  ...{i + 1}/{len(schools)} schools checked")

    def to_row(r):
        return {
            'School Name': r['name'],
            'Educational District': r['edu_district'],
            'Educational Sub-District': r['sub_district'],
            'Block Name': r['block'],
            'Level Name': r['level'],
            'Distance to Nearest PWD Road (m)': r['nearest_distance_m'],
            'Nearest Road Type': r['nearest_road_network'],
            'Nearest Road Name/Ref': f"{r['nearest_road_name']} ({r['nearest_road_ref']})".strip(' ()'),
            'Latitude': r['lat'],
            'Longitude': r['lon'],
        }

    all_out = resolve_writable_filename(ALL_OUT)
    with open(all_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in sorted(results, key=lambda x: x['nearest_distance_m']):
            writer.writerow(to_row(r))
    print(f"\n✓ Full distance table saved: {all_out} ({len(results)} schools)")

    adjacent = [r for r in results if r['nearest_distance_m'] <= ADJACENCY_THRESHOLD_M]
    print(f"\n{len(adjacent)} of {len(results)} checked schools are within "
          f"{ADJACENCY_THRESHOLD_M}m of a PWD road")

    adj_csv_out = resolve_writable_filename(ADJACENT_CSV_OUT)
    with open(adj_csv_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in sorted(adjacent, key=lambda x: (x['edu_district'], x['sub_district'], x['nearest_distance_m'])):
            writer.writerow(to_row(r))
    print(f"✓ Adjacent-schools CSV saved: {adj_csv_out}")

    save_pdf(adjacent)

    print("\nSummary - adjacent schools by Educational District -> Sub-District:")
    grouped = defaultdict(lambda: defaultdict(int))
    for r in adjacent:
        grouped[r['edu_district']][r['sub_district']] += 1
    for edu_district in sorted(grouped.keys()):
        total = sum(grouped[edu_district].values())
        print(f"  {edu_district} ({total} schools)")
        for sd in sorted(grouped[edu_district].keys()):
            print(f"    - {sd}: {grouped[edu_district][sd]} schools")
    print("=" * 70)
    print("Done!")


def save_pdf(adjacent):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
    except ImportError:
        print("\n[!] reportlab not installed. Run: pip install reportlab")
        print("    Skipping PDF generation.")
        return

    if not adjacent:
        print("\n[!] No schools met the adjacency threshold - skipping PDF.")
        return

    grouped = defaultdict(lambda: defaultdict(list))
    for r in adjacent:
        grouped[r['edu_district']][r['sub_district']].append(r)

    filename = resolve_writable_filename(ADJACENT_PDF_OUT)
    doc = SimpleDocTemplate(filename, pagesize=A4,
                             topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                             leftMargin=0.4 * inch, rightMargin=0.4 * inch)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('T', parent=styles['Heading1'], fontSize=16,
                                  textColor=colors.HexColor('#1f4788'), spaceAfter=6, alignment=1)
    subtitle_style = ParagraphStyle('S', parent=styles['Normal'], fontSize=10,
                                     textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=14)
    edu_style = ParagraphStyle('E', parent=styles['Heading1'], fontSize=14,
                                textColor=colors.white, backColor=colors.HexColor('#1f4788'),
                                spaceAfter=8, spaceBefore=18, leftIndent=4, borderPadding=6)
    sub_style = ParagraphStyle('SD', parent=styles['Heading2'], fontSize=12,
                                textColor=colors.white, backColor=colors.HexColor('#2c5aa0'),
                                spaceAfter=6, spaceBefore=12, leftIndent=4, borderPadding=4)

    total = len(adjacent)
    story.append(Paragraph("Schools Adjacent to PWD State Highways / MDRs", title_style))
    story.append(Paragraph(
        f"Malappuram District &nbsp;|&nbsp; within {ADJACENCY_THRESHOLD_M}m of a road &nbsp;|&nbsp; "
        f"{total} schools &nbsp;|&nbsp; Government, Level starting at 1", subtitle_style))

    for edu_district in sorted(grouped.keys()):
        sub_map = grouped[edu_district]
        edu_total = sum(len(v) for v in sub_map.values())
        story.append(Paragraph(f"Educational District: {edu_district} ({edu_total} schools)", edu_style))

        for sub_district in sorted(sub_map.keys()):
            schools_in_sd = sub_map[sub_district]
            story.append(Paragraph(f"Sub-District: {sub_district} ({len(schools_in_sd)} schools)", sub_style))

            table_data = [['#', 'School Name', 'Dist (m)', 'Road Type', 'Road Name/Ref']]
            for i, s in enumerate(sorted(schools_in_sd, key=lambda x: x['nearest_distance_m']), 1):
                table_data.append([
                    str(i),
                    s['name'][:38],
                    f"{s['nearest_distance_m']:.0f}",
                    s['nearest_road_network'],
                    f"{s['nearest_road_name']} ({s['nearest_road_ref']})".strip(' ()')[:30],
                ])

            table = Table(table_data, colWidths=[0.3 * inch, 2.2 * inch, 0.7 * inch, 1.0 * inch, 2.1 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472c4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eef2f9')]),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(table)
            story.append(Spacer(1, 0.12 * inch))

    doc.build(story)
    print(f"✓ PDF saved: {filename}")


if __name__ == "__main__":
    main()
