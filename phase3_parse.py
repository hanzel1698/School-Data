#!/usr/bin/env python3
"""Phase 3 - parse cached pages into data/processed/malappuram_staff.csv.

Reads only from data/cache/ - makes no network requests, so it can be re-run
freely while the parser is being tuned.

Where a value is not exposed by the page it is written as an empty cell
(null). Nothing is imputed, estimated, or back-filled from ratios: a null is a
finding, a fabricated number is a bug.

    python phase3_parse.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from scraper.classify import Section, classify
from scraper.config import Config, load_config
from scraper.parse import SchoolDetail, level_bounds, parse_school_detail

LP_STANDARDS = {"1", "2", "3", "4"}
UP_STANDARDS = {"5", "6", "7"}

FIELDNAMES = [
    "school_code",
    "school_name",
    "category",
    "management",
    "edu_district",
    "sub_district",
    "local_body",
    "classes_approved",
    "students_total",
    "students_lp",
    "students_up",
    "teaching_staff_total",
    "teaching_staff_lp",
    "teaching_staff_up",
    "teaching_staff_lp_up_shared",
    "teaching_staff_hs",
    "teaching_staff_unclassified",
    "non_teaching_total",
    "reported_total_employees",
    "staff_data_status",
    "total_reconciles",
    "has_hss",
    "has_vhse",
    "source_url",
    "fetched_at",
]


@dataclass
class Manifest:
    source_url: dict[str, str]
    fetched_at: dict[str, str]


def load_manifest(config: Config) -> Manifest:
    """Last successful fetch per school wins."""
    path = config.path("raw") / "fetch_manifest.jsonl"
    source_url: dict[str, str] = {}
    fetched_at: dict[str, str] = {}
    if not path.exists():
        return Manifest(source_url, fetched_at)

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if not record.get("ok"):
                continue
            code = str(record["school_code"])
            source_url[code] = record.get("source_url", "")
            fetched_at[code] = record.get("fetched_at", "")
    return Manifest(source_url, fetched_at)


def load_enumeration(config: Config) -> dict[str, dict[str, object]]:
    path = config.path("raw") / f"{config.district_name.lower()}_schools.jsonl"
    records: dict[str, dict[str, object]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                record = json.loads(line)
                records[str(record["school_code"])] = record
    return records


def derive_category(detail: SchoolDetail, level: str | None) -> str:
    """LPS / UPS / HS / HSS / VHSE, highest stage wins.

    Sametham has no single category field: the district list carries only
    LP/UP/HS, so the higher-secondary stages have to be derived from the
    HSS/VHSE codes on the detail page plus the approved class range.
    """
    if detail.vhse_code:
        return "VHSE"
    if detail.hss_code:
        return "HSS"

    bounds = level_bounds(level)
    if bounds is None:
        return "UNKNOWN"
    high = bounds[1]
    if high >= 11:
        return "HSS"
    if high >= 8:
        return "HS"
    if high >= 5:
        return "UPS"
    return "LPS"


def category_from_level_only(level: str | None) -> str:
    """Category for schools never fetched (no detail page to read codes from)."""
    bounds = level_bounds(level)
    if bounds is None:
        return "UNKNOWN"
    high = bounds[1]
    if high >= 11:
        return "HSS"
    if high >= 8:
        return "HS"
    if high >= 5:
        return "UPS"
    return "LPS"


def summarise_staff(detail: SchoolDetail) -> tuple[dict[Section, int], Counter[str]]:
    """Sum staff counts per section bucket; also tally unclassified names."""
    totals: dict[Section, int] = {section: 0 for section in Section}
    unknown: Counter[str] = Counter()

    for entry in detail.staff:
        section, _note = classify(entry.designation)
        totals[section] += entry.count
        if section is Section.UNCLASSIFIED:
            unknown[entry.designation] += entry.count

    return totals, unknown


def staff_status(detail: SchoolDetail) -> str:
    if detail.staff:
        return "ok"
    if detail.staff_tables_empty:
        return "empty_staff_table"
    if detail.staff_tables_seen:
        return "staff_table_unparsed"
    return "no_staff_table"


def main() -> int:
    config = load_config()
    cache_dir = config.path("cache")
    manifest = load_manifest(config)
    enumeration = load_enumeration(config)

    cached_files = sorted(cache_dir.glob("*.html"))
    print(f"Parsing {len(cached_files)} cached pages from {cache_dir}\n")

    rows: list[dict[str, object]] = []
    unknown_designations: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    reconcile_failures: list[tuple[str, int, int]] = []
    parse_errors: list[tuple[str, str]] = []
    designation_audit: dict[str, Counter[str]] = defaultdict(Counter)

    for path in cached_files:
        code = path.stem
        try:
            detail = parse_school_detail(path.read_text(encoding="utf-8"))
        except (ValueError, AttributeError) as exc:
            parse_errors.append((code, f"{type(exc).__name__}: {exc}"))
            continue

        listed = enumeration.get(code, {})
        totals, unknown = summarise_staff(detail)
        unknown_designations.update(unknown)

        for entry in detail.staff:
            section, _ = classify(entry.designation)
            designation_audit[section.value][entry.designation] += entry.count

        status = staff_status(detail)
        status_counter[status] += 1

        teaching_total = sum(
            totals[section] for section in Section if section.is_teaching
        )
        parsed_grand_total = teaching_total + totals[Section.NON_TEACHING] + totals[Section.UNCLASSIFIED]
        reported_total = sum(detail.reported_totals.values()) or None

        reconciles: bool | None = None
        if reported_total is not None and detail.staff:
            reconciles = parsed_grand_total == reported_total
            if not reconciles:
                reconcile_failures.append((code, parsed_grand_total, reported_total))

        students_lp = sum(
            count for std, count in detail.students_by_standard.items() if std in LP_STANDARDS
        )
        students_up = sum(
            count for std, count in detail.students_by_standard.items() if std in UP_STANDARDS
        )

        level = detail.level or listed.get("classes_approved")
        has_staff = bool(detail.staff)

        rows.append(
            {
                "school_code": detail.school_code or code,
                "school_name": detail.school_name or listed.get("school_name", ""),
                "category": derive_category(detail, level),
                "management": detail.management or listed.get("management", ""),
                "edu_district": detail.edu_district or "",
                "sub_district": detail.sub_district or "",
                "local_body": detail.local_body or listed.get("local_body", ""),
                "classes_approved": level or "",
                "students_total": detail.students_total if detail.students_total is not None else "",
                "students_lp": students_lp if detail.students_by_standard else "",
                "students_up": students_up if detail.students_by_standard else "",
                # Staff columns are null - not zero - when the page published no
                # staff data at all. Zero would assert "we looked and there are
                # none"; null says "the source does not tell us".
                "teaching_staff_total": teaching_total if has_staff else "",
                "teaching_staff_lp": totals[Section.LP] if has_staff else "",
                "teaching_staff_up": totals[Section.UP] if has_staff else "",
                "teaching_staff_lp_up_shared": totals[Section.LP_UP_SHARED] if has_staff else "",
                "teaching_staff_hs": totals[Section.HS_PLUS] if has_staff else "",
                "teaching_staff_unclassified": totals[Section.UNCLASSIFIED] if has_staff else "",
                "non_teaching_total": totals[Section.NON_TEACHING] if has_staff else "",
                "reported_total_employees": reported_total if reported_total is not None else "",
                "staff_data_status": status,
                "total_reconciles": "" if reconciles is None else str(reconciles).lower(),
                "has_hss": "true" if detail.hss_code else "false",
                "has_vhse": "true" if detail.vhse_code else "false",
                "source_url": manifest.source_url.get(code, config.url("school_detail", school_code=code)),
                "fetched_at": manifest.fetched_at.get(code, ""),
            }
        )

    rows.sort(key=lambda r: str(r["school_code"]))

    target = config.path("processed") / f"{config.district_name.lower()}_staff.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    audit_path = config.path("processed") / "designation_audit.csv"
    with audit_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section_bucket", "designation", "total_posts"])
        for section in sorted(designation_audit):
            for designation, count in designation_audit[section].most_common():
                writer.writerow([section, designation, count])

    print(f"Wrote {len(rows)} rows to {target}")
    print(f"Wrote designation audit to {audit_path}\n")

    print("Staff data status:")
    for status, count in status_counter.most_common():
        print(f"  {count:5d}  {status}")

    print("\nTotals across parsed schools:")
    for column in (
        "teaching_staff_lp",
        "teaching_staff_up",
        "teaching_staff_lp_up_shared",
        "teaching_staff_hs",
        "teaching_staff_unclassified",
        "non_teaching_total",
    ):
        total = sum(int(r[column]) for r in rows if r[column] != "")
        print(f"  {total:6d}  {column}")

    if unknown_designations:
        print(f"\n[!] {len(unknown_designations)} UNCLASSIFIED designations "
              f"({sum(unknown_designations.values())} posts) - add rules for these:")
        for designation, count in unknown_designations.most_common(40):
            print(f"      {count:4d}  {designation!r}")
    else:
        print("\nNo unclassified designations.")

    if reconcile_failures:
        print(f"\n[!] {len(reconcile_failures)} schools where parsed staff != "
              f"site's own 'Total Employees':")
        for code, parsed, reported in reconcile_failures[:15]:
            print(f"      {code}: parsed {parsed}, site says {reported}")
    else:
        print("Every school with staff data reconciles against the site's own total.")

    if parse_errors:
        print(f"\n[!] {len(parse_errors)} pages failed to parse:")
        for code, error in parse_errors[:10]:
            print(f"      {code}: {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
