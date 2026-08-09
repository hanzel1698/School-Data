#!/usr/bin/env python3
"""
Find schools adjacent to Kerala PWD roads - v2 (RMMS source)
====================================================================
Same logic as schools_near_pwd_roads.py, but against
malappuram_pwd_roads_v2.geojson (Kerala PWD's own RMMS road network,
via pwd_roads_rmms_extractor.py) instead of the OSM-derived file. The
OSM MDR data was too incomplete to trust (~728km vs an official
~2,300km for Malappuram).

Also loads the ORIGINAL v1 results (schools_all_road_distances.csv) so
it can print which specific schools changed adjacency status between
runs, for sanity-checking the difference.

Usage:
    pip install numpy reportlab
    python schools_near_pwd_roads_v2.py

Output (written next to this script):
    schools_all_road_distances_v2.csv
    schools_adjacent_to_pwd_roads_v2.csv
    schools_adjacent_to_pwd_roads_v2.pdf
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
ROADS_GEOJSON = "malappuram_pwd_roads_v2.geojson"
PRIOR_DISTANCES_CSV = "schools_all_road_distances.csv"  # v1 (OSM-based), for comparison only
ADJACENCY_THRESHOLD_M = 100

ALL_OUT = "schools_all_road_distances_v2.csv"
ADJACENT_CSV_OUT = "schools_adjacent_to_pwd_roads_v2.csv"
ADJACENT_PDF_OUT = "schools_adjacent_to_pwd_roads_v2.pdf"

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
        print(f"[!] {path} not found in this folder. Run pwd_roads_rmms_extractor.py first.")
        sys.exit(1)
    with open(path, encoding='utf-8') as f:
        geo = json.load(f)
    roads = []
    for feat in geo['features']:
        coords = feat['geometry']['coordinates']  # [[lon,lat], ...]
        if len(coords) < 2:
            continue
        props = feat['properties']
        roads.append({
            'name': props.get('road_name', ''),
            'section_label': props.get('section_label', ''),
            'road_class': props.get('road_class', ''),
            'coords': coords,
        })
    print(f"Loaded {len(roads)} road segment pieces from {path}")
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


def load_prior_status(path, threshold):
    """Load v1 (OSM-based) per-school distances, keyed by school name, for the
    before/after comparison. Best-effort - if missing, comparison is skipped."""
    if not os.path.exists(path):
        return None
    prior = {}
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                dist = float(row['Distance to Nearest PWD Road (m)'])
            except (ValueError, KeyError):
                continue
            prior[row['School Name']] = dist <= threshold
    return prior


def main():
    print("=" * 70)
    print("Finding schools adjacent to Kerala PWD roads v2 (RMMS source)")
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
            'nearest_road_class': nearest_road['road_class'],
            'nearest_road_label': nearest_road['section_label'],
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
            'Nearest Road Type': r['nearest_road_class'],
            'Nearest Road Name/Ref': f"{r['nearest_road_name']} ({r['nearest_road_label']})".strip(' ()'),
            'Latitude': r['lat'],
            'Longitude': r['lon'],
        }

    all_out = resolve_writable_filename(ALL_OUT)
    with open(all_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in sorted(results, key=lambda x: x['nearest_distance_m']):
            writer.writerow(to_row(r))
    print(f"\n[OK] Full distance table saved: {all_out} ({len(results)} schools)")

    adjacent = [r for r in results if r['nearest_distance_m'] <= ADJACENCY_THRESHOLD_M]
    print(f"\n{len(adjacent)} of {len(results)} checked schools are within "
          f"{ADJACENCY_THRESHOLD_M}m of a PWD road (v2 / RMMS)")

    adj_csv_out = resolve_writable_filename(ADJACENT_CSV_OUT)
    with open(adj_csv_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in sorted(adjacent, key=lambda x: (x['edu_district'], x['sub_district'], x['nearest_distance_m'])):
            writer.writerow(to_row(r))
    print(f"[OK] Adjacent-schools CSV saved: {adj_csv_out}")

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

    # --- v1 vs v2 comparison ---
    print("\n" + "=" * 70)
    print("COMPARISON: v1 (OSM) vs v2 (PWD RMMS)")
    print("=" * 70)
    prior_status = load_prior_status(PRIOR_DISTANCES_CSV, ADJACENCY_THRESHOLD_M)
    if prior_status is None:
        print(f"[!] {PRIOR_DISTANCES_CSV} not found - skipping before/after comparison.")
    else:
        v2_status = {r['name']: r['nearest_distance_m'] <= ADJACENCY_THRESHOLD_M for r in results}
        newly_flagged = []
        no_longer_flagged = []
        for name, was_adjacent in prior_status.items():
            is_adjacent = v2_status.get(name)
            if is_adjacent is None:
                continue  # school wasn't in the v2 result set (shouldn't normally happen)
            if is_adjacent and not was_adjacent:
                newly_flagged.append(name)
            elif was_adjacent and not is_adjacent:
                no_longer_flagged.append(name)

        old_count = sum(1 for v in prior_status.values() if v)
        new_count = len(adjacent)
        print(f"v1 (OSM):     {old_count} of {len(prior_status)} schools within {ADJACENCY_THRESHOLD_M}m")
        print(f"v2 (RMMS):    {new_count} of {len(results)} schools within {ADJACENCY_THRESHOLD_M}m")
        print(f"\nNewly flagged as adjacent in v2 ({len(newly_flagged)} schools):")
        for name in sorted(newly_flagged):
            print(f"  + {name}")
        print(f"\nNo longer flagged as adjacent in v2 ({len(no_longer_flagged)} schools):")
        for name in sorted(no_longer_flagged):
            print(f"  - {name}")

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
    story.append(Paragraph("Schools Adjacent to PWD State Highways / MDRs (v2 - RMMS source)", title_style))
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
                    s['nearest_road_class'],
                    f"{s['nearest_road_name']} ({s['nearest_road_label']})".strip(' ()')[:30],
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
    print(f"[OK] PDF saved: {filename}")


if __name__ == "__main__":
    main()
