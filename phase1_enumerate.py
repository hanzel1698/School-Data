#!/usr/bin/env python3
"""Phase 1 - enumerate every Malappuram school.

One request to the district-wide list. All managements are written to the raw
dump; only Government rows are flagged into the working set.

Education District and Sub District do not exist on the district list - they
are only on the school detail page - so they are written as null here and
backfilled in Phase 3.

    python phase1_enumerate.py
"""

from __future__ import annotations

import json
from collections import Counter

from scraper.config import load_config
from scraper.fetcher import RateLimitedFetcher
from scraper.parse import DistrictRow, level_bounds, parse_district_list

GOVERNMENT = "Government"


def exclusion_reason(row: DistrictRow, min_class_to_skip: int) -> str | None:
    """Why this school is out of the working set, or None if it's in.

    Schools starting at class 8 or above have no LP or UP section and so no
    LP/UP teaching posts to count; fetching them would be ~37 wasted requests.
    """
    if row.management != GOVERNMENT:
        return f"management is {row.management!r}, not Government"

    bounds = level_bounds(row.level)
    if bounds is None:
        # Unreadable level: keep it rather than silently dropping a school.
        return None
    if bounds[0] >= min_class_to_skip:
        return f"lowest class {bounds[0]} >= {min_class_to_skip}; no LP/UP section"
    return None


def main() -> int:
    config = load_config()
    raw_dir = config.path("raw")
    samples_dir = config.path("samples")

    with RateLimitedFetcher(config) as fetcher:
        url = f"{config.base_url}/search/districtWiseSchools/{config.district_id}"
        result = fetcher.get(url)

    if not result.ok:
        print(f"FAILED to fetch district list: {result.reason}")
        return 1

    (samples_dir / "district_list.html").write_text(result.text, encoding="utf-8")
    rows = parse_district_list(result.text)

    min_class_to_skip = config.skip_if_lowest_class_at_least

    target = raw_dir / f"{config.district_name.lower()}_schools.jsonl"
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            reason = exclusion_reason(row, min_class_to_skip)
            record = {
                "school_code": row.school_code,
                "school_name": row.school_name,
                "category": row.section_label,
                "management": row.management,
                "edu_district": None,      # detail-page only; backfilled Phase 3
                "sub_district": None,      # detail-page only; backfilled Phase 3
                "local_body": row.local_body,
                "block": row.block,
                "assembly": row.assembly,
                "parliamentary": row.parliamentary,
                "classes_approved": row.level,
                "phone": row.phone,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "in_working_set": reason is None,
                "excluded_reason": reason,
                "source_url": url,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    government = [r for r in rows if r.management == GOVERNMENT]
    working = [r for r in rows if exclusion_reason(r, min_class_to_skip) is None]

    print(f"\nWrote {len(rows)} schools to {target}")
    print("\nBy management:")
    for management, count in Counter(r.management for r in rows).most_common():
        print(f"  {count:5d}  {management}")

    skipped = [
        r
        for r in government
        if (bounds := level_bounds(r.level)) and bounds[0] >= min_class_to_skip
    ]
    print(f"\nGovernment schools:            {len(government)}")
    print(f"  less no-LP/UP-section schools: -{len(skipped)}")
    for level, count in sorted(Counter(r.level for r in skipped).items()):
        print(f"      {count:5d}  level {level!r}")
    print(f"  = working set to fetch:        {len(working)}")

    print("\nWorking set by section label:")
    for label, count in Counter(r.section_label for r in working).most_common():
        print(f"  {count:5d}  {label}")

    missing_code = [r for r in rows if not r.school_code]
    if missing_code:
        print(f"\n[!] {len(missing_code)} rows had no school code and cannot be fetched")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
