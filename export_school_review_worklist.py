#!/usr/bin/env python3
"""
Export a plain manual-review worklist of every school that has a scraped
coordinate, for spot-checking against Google Earth.

Background: every lat/lon in this project traces back to a single source
(a Google-Maps-link field scraped off the KITE Kerala "Sametham" portal by
kite_scraper_final.py) - there's no independent per-school source to check
it against. G. M. L. P. S. Valavannur (code 19646) turned out to be ~1.4km
off. Two automated screening attempts (panchayat boundary containment via
OSM Nominatim, and OSM amenity=school proximity/name matching) were both
tried and rejected: the boundary check is too coarse to catch a 1-2km drift
(it scored Valavannur as fine), and OSM doesn't reliably have rural Kerala
LP schools mapped by name. So this is a plain worklist, not a filter - no
automated flag, sorted for efficient manual review.

Usage:
    python export_school_review_worklist.py
"""

import csv

SOURCE_CSV = "schools_malappuram_sub_district.csv"
OUTPUT_CSV = "schools_review_worklist.csv"


def main():
    with open(SOURCE_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    schools = [r for r in rows if r["Latitude"].strip() and r["Longitude"].strip()]

    # Group geographically (sub-district, then local body, then name) so
    # nearby schools land next to each other in the worklist - easier to
    # review several in the same area of Google Earth in one sitting.
    schools.sort(key=lambda r: (
        r["Educational Sub-District"].strip().lower(),
        r["Local Body"].strip().lower(),
        r["School Name"].strip().lower(),
    ))

    fieldnames = [
        "School Code", "School Name", "Educational Sub-District", "Local Body",
        "Block Name", "Latitude", "Longitude", "Maps Link",
        "Verified (Y/N)", "Corrected Latitude", "Corrected Longitude", "Notes",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in schools:
            lat, lon = s["Latitude"], s["Longitude"]
            writer.writerow({
                "School Code": s["School Code"],
                "School Name": s["School Name"],
                "Educational Sub-District": s["Educational Sub-District"],
                "Local Body": s["Local Body"],
                "Block Name": s["Block Name"],
                "Latitude": lat,
                "Longitude": lon,
                "Maps Link": f"http://maps.google.com/maps?q={lat},{lon}",
                "Verified (Y/N)": "",
                "Corrected Latitude": "",
                "Corrected Longitude": "",
                "Notes": "",
            })

    print(f"Wrote {len(schools)} schools to {OUTPUT_CSV}, grouped by "
          f"sub-district / local body / name for area-by-area review.")


if __name__ == "__main__":
    main()
