#!/usr/bin/env python3
"""
KITE Sametham School Scraper - FINAL VERSION
Scrapes Government schools in Malappuram district with Level Name
starting with "1" (e.g. "1-4", "1-12"), and groups them by their real
Educational Sub-District (fetched from each school's detail page).

Confirmed working endpoints (reverse-engineered via live browser/network
inspection on 2026-08-08):

  1. https://sametham.kite.kerala.gov.in/publicView/schoolsLists/all/dist/{district_code}/{ftype}
     -> Full HTML table of schools for a district + finance type.
        Columns: #, School Name(with code+link), Block Name, Local Body Type,
        Assembly Name, Finance Type, Level Name, School Phone, School WIKI, Location
        NOTE: no Sub-District column here.
        The Location column holds a Google Maps link like
        "http://maps.google.com/maps?q=<lat>,<lng>" (or plain text
        "Not Available" for some schools) - lat/lng are parsed out of that
        href for use in the My Maps import CSV below.

  2. https://sametham.kite.kerala.gov.in/{school_code}
     -> Individual school profile page. Contains a "Basic Information" table
        with label:value pairs including "Sub District", "Education District",
        "Revenue District", "UDISE Code", "School Address", etc.

  Both are plain public GET routes - no CSRF token or special session
  handling was required in testing (an empty csrf_test_name-based session
  warm-up was tried but made no observable difference to these two GET
  routes).

  ftype values (from the advanced search <select name="ftype">):
    1 = Government, 3 = Aided, 4 = Unaided, All = All

District codes (from <select name="rev_sub">): Malappuram = 10
(TVM=1, KLM=2, PTN=3, ALP=4, KTM=5, IDK=6, EKM=7, TSR=8, PKD=9,
 MLP=10, KKD=11, WYD=12, KNR=13, KGD=14)

Usage:
    python kite_scraper_final.py

Output (written next to this script):
    schools_malappuram_sub_district.csv        - full data, grouped by
                                                   Educational District -> Sub-District
    schools_malappuram_sub_district.pdf         - same grouping, formatted tables
    schools_malappuram_my_maps_import.csv       - Name/Latitude/Longitude + grouping
                                                   columns, ready to import into
                                                   Google My Maps (mymaps.google.com)
"""

import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import os
import re
import sys
import time


def resolve_writable_filename(filename):
    """
    Return a filename that can actually be opened for writing. If
    `filename` is locked (e.g. already open in Excel on Windows), fall
    back to 'name (1).ext', 'name (2).ext', etc. - same convention as a
    browser download - instead of crashing.
    """
    base, ext = os.path.splitext(filename)
    candidate = filename
    n = 1
    while n <= 30:
        try:
            with open(candidate, 'ab'):
                pass
            if candidate != filename:
                print(f"  [!] '{filename}' appears to be open in another program "
                      f"(locked) - writing to '{candidate}' instead.")
            return candidate
        except PermissionError:
            candidate = f"{base} ({n}){ext}"
            n += 1
    raise PermissionError(f"Could not find a writable filename for {filename} "
                           f"after {n - 1} attempts - close whatever has it open.")

# ---- Config ----
BASE = "https://sametham.kite.kerala.gov.in"
DISTRICT_CODE = "10"       # Malappuram
DISTRICT_NAME = "Malappuram"
FTYPE = "1"                 # Government
LEVEL_START = "1"           # Level Name must start with this (e.g. "1 - 4")
MAX_WORKERS = 8             # concurrent detail-page requests
CSV_OUT = "schools_malappuram_sub_district.csv"
PDF_OUT = "schools_malappuram_sub_district.pdf"
MY_MAPS_CSV_OUT = "schools_malappuram_my_maps_import.csv"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    # Warm-up (establishes ci_session cookie; harmless if not strictly needed)
    try:
        s.get(f"{BASE}/search/advanced_search_interface", timeout=15)
    except Exception:
        pass
    return s


def fetch_district_schools(session, district_code, ftype):
    """
    Fetch the full school list for a district + finance type using the
    confirmed working publicView/schoolsLists/all/dist/{district}/{ftype} route.
    Returns a list of dicts with the raw table columns.
    """
    url = f"{BASE}/publicView/schoolsLists/all/dist/{district_code}/{ftype}"
    print(f"Fetching school list: {url}")
    r = session.get(url, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table')
    if not table:
        raise RuntimeError("No table found in district school list response")

    tbody = table.find('tbody')
    rows = tbody.find_all('tr') if tbody else table.find_all('tr')[2:]

    schools = []
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 9:
            continue

        # Column 1 contains "<code> - <name>" as link text
        name_cell = cells[1]
        name_link = name_cell.find('a')
        raw_name_text = name_link.get_text(strip=True) if name_link else name_cell.get_text(strip=True)

        code = ''
        name = raw_name_text
        m = re.match(r'^\s*(\S+)\s*-\s*(.+)$', raw_name_text)
        if m:
            code = m.group(1).strip()
            name = m.group(2).strip()

        # Column 9 (last) is the "Location map" link, e.g.
        # <a href="http://maps.google.com/maps?q=11.17135,76.017949999999999">
        # Some rows just say "Not Available" (plain text, no link).
        lat, lng, maps_url = '', '', ''
        if len(cells) > 9:
            loc_link = cells[9].find('a', href=True)
            if loc_link:
                maps_url = loc_link['href']
                m_loc = re.search(r'q=(-?\d+\.?\d*),(-?\d+\.?\d*)', maps_url)
                if m_loc:
                    lat, lng = m_loc.group(1), m_loc.group(2)

        school = {
            'code': code,
            'name': name,
            'block': cells[2].get_text(strip=True),
            'local_body': cells[3].get_text(strip=True),
            'assembly': cells[4].get_text(strip=True),
            'finance_type': cells[5].get_text(strip=True),
            'level': cells[6].get_text(strip=True),
            'phone': cells[7].get_text(strip=True) if len(cells) > 7 else '',
            'latitude': lat,
            'longitude': lng,
            'maps_url': maps_url,
        }
        schools.append(school)

    print(f"  -> Parsed {len(schools)} schools from district list")
    return schools


def filter_by_level(schools, level_start):
    """Keep only schools whose Level Name starts with level_start (e.g. '1')."""
    filtered = []
    for s in schools:
        level = s.get('level', '').strip()
        # Level format observed: "1 - 4", "8 - 12" etc.
        first_part = level.split('-')[0].strip() if '-' in level else level
        if first_part == level_start:
            filtered.append(s)
    print(f"Filtered to {len(filtered)} schools with Level Name starting '{level_start}'")
    return filtered


def parse_profile_table(table):
    """
    Parse a 'Basic Information'-style table where rows contain repeated
    (label, ':', value) triples, into a flat dict.
    """
    result = {}
    for row in table.find_all('tr'):
        cells = [c.get_text(strip=True) for c in row.find_all(['td', 'th'])]
        # Walk the cells in groups of 3: label, ':', value
        i = 0
        while i + 2 < len(cells) + 1 and i + 2 <= len(cells):
            if i + 2 < len(cells) and cells[i + 1] == ':':
                label = cells[i].strip()
                value = cells[i + 2].strip()
                if label:
                    result[label] = value
                i += 3
            else:
                i += 1
    return result


def fetch_school_detail(session, code):
    """Fetch a school's detail page and extract Sub District / related fields."""
    url = f"{BASE}/{code}"
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table')
            if not tables:
                return {}
            info = parse_profile_table(tables[0])
            return {
                'sub_district': info.get('Sub District', ''),
                'education_district': info.get('Education District', ''),
                'revenue_district': info.get('Revenue District', ''),
                'udise_code': info.get('UDISE Code', ''),
                'address': info.get('School Address', ''),
            }
        except Exception as e:
            if attempt == 2:
                print(f"  [!] Failed to fetch detail for {code}: {e}")
                return {}
            time.sleep(1)
    return {}


def enrich_with_sub_district(session, schools):
    """Fetch detail pages concurrently to add Sub District info to each school."""
    print(f"\nFetching Sub-District info for {len(schools)} schools "
          f"(concurrency={MAX_WORKERS})...")

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_code = {
            executor.submit(fetch_school_detail, session, s['code']): s['code']
            for s in schools if s['code']
        }
        done = 0
        total = len(future_to_code)
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            results[code] = future.result()
            done += 1
            if done % 25 == 0 or done == total:
                print(f"  ...{done}/{total} detail pages fetched")

    for s in schools:
        detail = results.get(s['code'], {})
        s.update(detail)
        if not s.get('sub_district'):
            s['sub_district'] = 'Unknown'

    return schools


def group_hierarchically(schools):
    """
    Group schools by Educational District -> Sub District.
    Returns: {education_district: {sub_district: [schools]}}
    """
    grouped = defaultdict(lambda: defaultdict(list))
    for s in schools:
        edu_district = s.get('education_district') or 'Unknown'
        sub_district = s.get('sub_district') or 'Unknown'
        grouped[edu_district][sub_district].append(s)
    return grouped


def save_csv(schools, filename):
    grouped = group_hierarchically(schools)

    fieldnames = [
        'Educational District', 'Educational Sub-District', 'School Code',
        'School Name', 'Block Name', 'Level Name', 'Local Body',
        'Revenue District', 'Phone', 'UDISE Code', 'Latitude', 'Longitude',
        'Maps Link',
    ]

    sub_district_count = 0
    filename = resolve_writable_filename(filename)
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for edu_district in sorted(grouped.keys()):
            sub_map = grouped[edu_district]
            for sub_district in sorted(sub_map.keys()):
                sub_district_count += 1
                for s in sorted(sub_map[sub_district], key=lambda x: x['name']):
                    writer.writerow({
                        'Educational District': edu_district,
                        'Educational Sub-District': sub_district,
                        'School Code': s.get('code', ''),
                        'School Name': s.get('name', ''),
                        'Block Name': s.get('block', ''),
                        'Level Name': s.get('level', ''),
                        'Local Body': s.get('local_body', ''),
                        'Revenue District': s.get('revenue_district', ''),
                        'Phone': s.get('phone', ''),
                        'UDISE Code': s.get('udise_code', ''),
                        'Latitude': s.get('latitude', ''),
                        'Longitude': s.get('longitude', ''),
                        'Maps Link': s.get('maps_url', ''),
                    })

    print(f"\n✓ CSV saved: {filename} ({len(schools)} schools, "
          f"{len(grouped)} education districts, {sub_district_count} sub-districts)")
    return grouped


def save_my_maps_csv(schools, filename):
    """
    Write a CSV specifically formatted for Google My Maps import
    (https://mymaps.google.com). My Maps auto-detects Latitude/Longitude
    columns by name, uses 'Name' as the placemark title, and any other
    column (e.g. 'Educational Sub-District') can be selected afterwards
    under a layer's "Style by data column" option to auto color-code /
    group the pins with a legend - the closest equivalent to "lists"
    grouped by Sub-District on a single map.

    Only schools with valid coordinates are included, since My Maps can't
    place a pin without them.
    """
    with_coords = [s for s in schools if s.get('latitude') and s.get('longitude')]
    without_coords = [s for s in schools if not (s.get('latitude') and s.get('longitude'))]

    fieldnames = [
        'Name', 'Latitude', 'Longitude', 'Educational District',
        'Educational Sub-District', 'Block Name', 'Level Name', 'Phone',
        'School Code',
    ]

    filename = resolve_writable_filename(filename)
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in sorted(with_coords, key=lambda x: (x.get('education_district', ''),
                                                       x.get('sub_district', ''), x['name'])):
            writer.writerow({
                'Name': s.get('name', ''),
                'Latitude': s.get('latitude', ''),
                'Longitude': s.get('longitude', ''),
                'Educational District': s.get('education_district', 'Unknown'),
                'Educational Sub-District': s.get('sub_district', 'Unknown'),
                'Block Name': s.get('block', ''),
                'Level Name': s.get('level', ''),
                'Phone': s.get('phone', ''),
                'School Code': s.get('code', ''),
            })

    print(f"\n✓ My Maps import CSV saved: {filename} "
          f"({len(with_coords)} schools with coordinates)")
    if without_coords:
        print(f"  [!] {len(without_coords)} schools had no location data on the site "
              f"and were excluded from this file (still present in the main CSV).")
    return with_coords, without_coords


def save_pdf(grouped, filename):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                          Paragraph, Spacer)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
    except ImportError:
        print("\n[!] reportlab not installed. Run: pip install reportlab")
        print("    Skipping PDF generation.")
        return

    filename = resolve_writable_filename(filename)
    doc = SimpleDocTemplate(filename, pagesize=A4,
                             topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                             leftMargin=0.4 * inch, rightMargin=0.4 * inch)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'], fontSize=16,
        textColor=colors.HexColor('#1f4788'), spaceAfter=6, alignment=1,
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'], fontSize=10,
        textColor=colors.HexColor('#555555'), alignment=1, spaceAfter=14,
    )
    edu_district_style = ParagraphStyle(
        'EduDistrictHeading', parent=styles['Heading1'], fontSize=14,
        textColor=colors.white, backColor=colors.HexColor('#1f4788'),
        spaceAfter=8, spaceBefore=18, leftIndent=4, borderPadding=6,
    )
    heading_style = ParagraphStyle(
        'SubDistrictHeading', parent=styles['Heading2'], fontSize=12,
        textColor=colors.white, backColor=colors.HexColor('#2c5aa0'),
        spaceAfter=6, spaceBefore=12, leftIndent=4, borderPadding=4,
    )

    total_schools = sum(len(v) for sub_map in grouped.values() for v in sub_map.values())
    total_sub_districts = sum(len(sub_map) for sub_map in grouped.values())
    story.append(Paragraph(f"KITE Sametham &ndash; {DISTRICT_NAME} District", title_style))
    story.append(Paragraph(
        f"Government Schools, Level starting at 1 &nbsp;|&nbsp; "
        f"{total_schools} schools across {len(grouped)} Educational Districts, "
        f"{total_sub_districts} Sub-Districts",
        subtitle_style))

    for edu_district in sorted(grouped.keys()):
        sub_map = grouped[edu_district]
        edu_total = sum(len(v) for v in sub_map.values())
        story.append(Paragraph(
            f"Educational District: {edu_district}  ({edu_total} schools, {len(sub_map)} sub-districts)",
            edu_district_style))

        for sub_district in sorted(sub_map.keys()):
            schools_in_sd = sub_map[sub_district]
            story.append(Paragraph(
                f"Sub-District: {sub_district}  ({len(schools_in_sd)} schools)",
                heading_style))

            table_data = [['#', 'School Name', 'Block', 'Level', 'Local Body']]
            for i, s in enumerate(sorted(schools_in_sd, key=lambda x: x['name']), 1):
                table_data.append([
                    str(i),
                    s.get('name', '')[:45],
                    s.get('block', '')[:18],
                    s.get('level', ''),
                    s.get('local_body', '')[:20],
                ])

            table = Table(table_data,
                           colWidths=[0.3 * inch, 2.6 * inch, 1.2 * inch, 0.7 * inch, 1.5 * inch])
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


def main():
    print("=" * 70)
    print(f"KITE Sametham Scraper - {DISTRICT_NAME} | Government | Level starts '1'")
    print("Grouped by Educational Sub-District")
    print("=" * 70)

    session = get_session()

    # Step 1: full district school list (ftype filtered server-side)
    schools = fetch_district_schools(session, DISTRICT_CODE, FTYPE)
    if not schools:
        print("No schools returned - site structure may have changed.")
        sys.exit(1)

    # Step 2: filter by level client-side
    schools = filter_by_level(schools, LEVEL_START)
    if not schools:
        print("No schools matched the level filter.")
        sys.exit(1)

    # Step 3: enrich each school with its real Sub District via detail page
    schools = enrich_with_sub_district(session, schools)

    # Step 4: export
    grouped = save_csv(schools, CSV_OUT)
    save_pdf(grouped, PDF_OUT)
    save_my_maps_csv(schools, MY_MAPS_CSV_OUT)

    print("\n" + "=" * 70)
    print("Summary by Educational District -> Sub-District:")
    for edu_district in sorted(grouped.keys()):
        sub_map = grouped[edu_district]
        edu_total = sum(len(v) for v in sub_map.values())
        print(f"  {edu_district} ({edu_total} schools)")
        for sd in sorted(sub_map.keys()):
            print(f"    - {sd}: {len(sub_map[sd])} schools")
    print("=" * 70)
    print("Done!")


if __name__ == "__main__":
    main()
