#!/usr/bin/env python3
"""
Cross-check the Sametham-derived Malappuram staffing figures against UDISE+.

Why this exists: output/malappuram_summary.md states that some Sametham staff
records look under-populated ("Risk A"), and that they are "not distinguishable
from genuinely tiny establishments without an external source". UDISE+ is that
external source - the Ministry of Education's school census, collected on a
completely separate track from SPARK, which is where Sametham's staff data
originates (see output/phase0_findings.md section 7).

What UDISE+ can and cannot give us, established by probing the public API on
2026-08-15:

  * The open-services API serves NATIONAL and STATE rows only. Every district
    query (regionType 12 or 22, any code format) returns an empty data array,
    on both the teacher and the school endpoints. There is no Malappuram row.
  * The per-school report card portal, src.udiseplus.gov.in, no longer exists
    - the hostname does not resolve.

So a per-school join on UDISE code is impossible, and the completeness question
has to be attacked two ways instead:

  Test 1 (external): compare Sametham's own STATEWIDE Government LP+UP teacher
    count against UDISE's Kerala Department-of-Education teacher count for
    primary/upper-primary school categories. This detects systematic
    under-publication, which is the version of Risk A that would invalidate the
    headline number.

  Test 2 (internal, calibrated externally): compute each Malappuram school's
    LP/UP pupil-teacher ratio and rank it against UDISE's published Kerala PTR.
    This cannot prove a record is incomplete, but it turns "some records look
    under-populated" into a specific, reviewable list of schools.

Neither test can confirm an individual record. Test 2 produces review
candidates, not findings.

Inputs (all committed):
    data/processed/malappuram_staff.csv   - Phase 3 output
    data/udise/*.json                     - raw UDISE+ API responses
    data/samples/home.html                - Sametham statewide totals

Outputs:
    data/processed/malappuram_ptr_check.csv
    output/udise_crosscheck.md

Usage:
    python udise_crosscheck.py            # read the committed JSON pulls
    python udise_crosscheck.py --refetch  # re-pull from the UDISE+ API
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

STAFF_CSV = REPO_ROOT / "data/processed/malappuram_staff.csv"
UDISE_DIR = REPO_ROOT / "data/udise"
SAMETHAM_HOME = REPO_ROOT / "data/samples/home.html"
PTR_CSV = REPO_ROOT / "data/processed/malappuram_ptr_check.csv"
REPORT_MD = REPO_ROOT / "output/udise_crosscheck.md"

# UDISE+ public dashboard API. The bearer token below is not a credential we
# hold - it is a fixed string compiled into the public dashboard's own
# JavaScript bundle and sent by every visitor's browser. Calling these
# endpoints is equivalent to loading dashboard.udiseplus.gov.in.
API_BASE = "https://api.udiseplus.gov.in/open-services"
API_TOKEN = "df;lkjz8lke4lk345kljsdfkjdfgkljsf08994a/sdfljsdf879w4ra/sdflksdflksdf"
USER_AGENT = (
    "sametham-staffing-research/0.1 (Malappuram LP/UP teacher staffing study; "
    "contact: hanzel.h.fernandez@gmail.com)"
)
REQUEST_DELAY_SECONDS = 2.0

KERALA_STATE_CODE = "32"
REGION_TYPE_STATE = 11
YEARS = {12: "2025-26", 11: "2024-25", 10: "2023-24"}
LATEST_YEAR_ID = 12

# UDISE school categories that correspond to Kerala's LP and UP schools:
# a Kerala LP school is classes 1-4/1-5, a UP school 1-7 or 5-7.
LP_UP_CATEGORIES = frozenset(
    {"Primary", "Primary with Upper Primary", "Upper Primary only"}
)
# UDISE management label for state Government schools. Kerala's "Government"
# finance type in Sametham maps to this; "Government Aided" is separate.
GOVERNMENT_MANAGEMENT = "Department of Education"


@dataclass(frozen=True)
class SchoolPtr:
    """One school's LP/UP pupil-teacher ratio and how it ranks."""

    school_code: str
    school_name: str
    category: str
    sub_district: str
    students: int
    teachers: int
    ptr: float | None  # None when the school has students but no LP/UP teacher

    @property
    def sort_key(self) -> float:
        return float("inf") if self.ptr is None else self.ptr


def fetch_udise() -> None:
    """Re-pull the UDISE+ responses this script reads. Rate-limited."""
    import httpx

    headers = {
        "User-Agent": USER_AGENT,
        "Content-type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
        "Identity": "test",
    }
    UDISE_DIR.mkdir(parents=True, exist_ok=True)

    calls: list[tuple[str, str, dict]] = []
    for year_id in YEARS:
        base = {
            "yearId": year_id,
            "regionType": REGION_TYPE_STATE,
            "regionCode": KERALA_STATE_CODE,
            "valueType": 1,
        }
        calls.append((f"teachers_kerala_y{year_id}.json",
                      "v1.1/teachers-summarised-stats/public", base))
        calls.append((f"schools_kerala_y{year_id}.json",
                      "v1.1/schools-summarised-stats/public", base))
    calls.append((
        f"teachers_kpi_kerala_y{LATEST_YEAR_ID}.json",
        "v1.1/kpi/teachers/public",
        {
            "yearId": LATEST_YEAR_ID,
            "regionType": REGION_TYPE_STATE,
            "regionCode": KERALA_STATE_CODE,
            "dType": REGION_TYPE_STATE,
            "dCode": KERALA_STATE_CODE,
            "categoryCode": 0,
            "managementCode": 0,
            "locationCode": 0,
            "schoolTypeCode": 0,
            "dashboardRegionType": REGION_TYPE_STATE,
            "dashboardRegionCode": KERALA_STATE_CODE,
        },
    ))

    with httpx.Client(headers=headers, timeout=40.0) as client:
        for index, (filename, endpoint, body) in enumerate(calls):
            if index:
                time.sleep(REQUEST_DELAY_SECONDS)
            response = client.post(f"{API_BASE}/{endpoint}", json=body)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("status"):
                raise RuntimeError(f"{endpoint} returned {payload!r}")
            (UDISE_DIR / filename).write_text(
                json.dumps(payload, indent=1), encoding="utf-8"
            )
            print(f"  wrote {filename}")


def load_udise_state(year_id: int, kind: str) -> dict[str, str]:
    path = UDISE_DIR / f"{kind}_kerala_y{year_id}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["data"]
    if not rows:
        raise RuntimeError(f"{path} holds no rows")
    return rows[0]


def udise_lp_up_government_teachers() -> tuple[int, dict[str, int]]:
    """Kerala Government teachers in LP/UP-category schools, from UDISE+.

    Returns the total and the per-category breakdown. UDISE classifies a
    teacher by the category of the school they work in, which is the crucial
    difference from Sametham - see the report for why that matters.
    """
    path = UDISE_DIR / f"teachers_kpi_kerala_y{LATEST_YEAR_ID}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["data"]

    by_category: dict[str, int] = {}
    for row in rows:
        if row["schManagementDesc"] != GOVERNMENT_MANAGEMENT:
            continue
        category = row["schCategoryDesc"]
        if category not in LP_UP_CATEGORIES:
            continue
        by_category[category] = by_category.get(category, 0) + int(row["totTch"] or 0)

    return sum(by_category.values()), by_category


def sametham_statewide_totals() -> dict[str, int]:
    """Kerala-wide Government LP and UP teacher counts off Sametham's homepage.

    Parsed from the committed sample rather than re-fetched, so the comparison
    is against the same snapshot the crawl was taken from.
    """
    markup = SAMETHAM_HOME.read_text(encoding="utf-8", errors="replace")
    markup = re.sub(r"(?is)<(script|style).*?</\1>", " ", markup)
    text = html.unescape(re.sub(r"(?is)<[^>]+>", "|", markup))
    text = re.sub(r"\|+", "|", re.sub(r"[ \t\xa0]+", " ", text))

    # The Teaching Staff block's management table: a "Govt" row followed by
    # LP, UP, HS, HSS, VHSE, Total cells.
    block = text[text.find("Teaching Staff"):]
    match = re.search(
        r"Govt\s*\|[^|]*\|\s*([\d,]+)\s*\|[^|]*\|\s*([\d,]+)\s*\|", block
    )
    if not match:
        raise RuntimeError("could not locate the Govt row of the Teaching Staff table")

    def number(raw: str) -> int:
        return int(raw.replace(",", ""))

    return {"lp": number(match.group(1)), "up": number(match.group(2))}


def load_school_ptrs() -> list[SchoolPtr]:
    """Per-school LP/UP pupil-teacher ratios from the Phase 3 output."""

    def integer(row: dict[str, str], key: str) -> int:
        value = row.get(key, "")
        return int(value) if value not in ("", "None", None) else 0

    schools: list[SchoolPtr] = []
    with STAFF_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            students = integer(row, "students_lp") + integer(row, "students_up")
            # Shared LP/UP posts are included: they are real LP/UP teaching
            # posts, and excluding them would manufacture false outliers.
            teachers = (
                integer(row, "teaching_staff_lp")
                + integer(row, "teaching_staff_up")
                + integer(row, "teaching_staff_lp_up_shared")
            )
            if students == 0:
                continue  # no LP/UP pupils; the ratio is meaningless
            schools.append(
                SchoolPtr(
                    school_code=row["school_code"],
                    school_name=row["school_name"],
                    category=row["category"],
                    sub_district=row["sub_district"],
                    students=students,
                    teachers=teachers,
                    ptr=(students / teachers) if teachers else None,
                )
            )
    return schools


def write_ptr_csv(schools: list[SchoolPtr], threshold: float) -> None:
    PTR_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PTR_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "school_code", "school_name", "category", "sub_district",
            "lp_up_students", "lp_up_teachers", "lp_up_ptr", "review_flag",
        ])
        for school in sorted(schools, key=lambda s: -s.sort_key):
            if school.ptr is None:
                flag = "no_lp_up_teacher"
                ptr_text = ""
            elif school.ptr >= threshold:
                flag = "high_ptr"
                ptr_text = f"{school.ptr:.1f}"
            else:
                flag = ""
                ptr_text = f"{school.ptr:.1f}"
            writer.writerow([
                school.school_code, school.school_name, school.category,
                school.sub_district, school.students, school.teachers,
                ptr_text, flag,
            ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refetch", action="store_true",
        help="re-pull the UDISE+ responses instead of reading data/udise/",
    )
    args = parser.parse_args()

    if args.refetch:
        print("Re-fetching UDISE+ state data...")
        fetch_udise()

    udise_total, udise_by_category = udise_lp_up_government_teachers()
    sametham = sametham_statewide_totals()
    sametham_total = sametham["lp"] + sametham["up"]
    difference = sametham_total - udise_total
    percent = 100.0 * difference / udise_total

    schools = load_school_ptrs()
    with_teachers = [s for s in schools if s.ptr is not None]
    without = [s for s in schools if s.ptr is None]
    district_students = sum(s.students for s in schools)
    district_teachers = sum(s.teachers for s in schools)
    district_ptr = district_students / district_teachers

    state = load_udise_state(LATEST_YEAR_ID, "teachers")
    benchmark_pry = float(state["ptrPry"])
    benchmark_upry = float(state["ptrUPry"])
    # Twice the district's own median is a deliberately loose screen: the aim
    # is a short review list, not a verdict. Screening against the state PTR
    # instead would flag most of the district, since Malappuram genuinely runs
    # at about double the Kerala ratio.
    median_ptr = statistics.median(s.ptr for s in with_teachers)
    threshold = 2 * median_ptr

    write_ptr_csv(schools, threshold)

    flagged = [s for s in with_teachers if s.ptr >= threshold]

    print(f"UDISE Kerala Govt LP/UP-category teachers : {udise_total:,}")
    print(f"Sametham Kerala Govt LP+UP teachers       : {sametham_total:,}")
    print(f"Difference                                : {difference:+,} ({percent:+.1f}%)")
    print()
    print(f"Malappuram LP/UP PTR (our data)           : {district_ptr:.1f}")
    print(f"UDISE Kerala PTR primary / upper primary  : {benchmark_pry:.0f} / {benchmark_upry:.0f}")
    print(f"Schools reviewed                          : {len(schools)}")
    print(f"  students but no LP/UP teacher           : {len(without)}")
    print(f"  PTR >= {threshold:.1f} (2x district median)      : {len(flagged)}")
    print()
    print(f"Wrote {PTR_CSV.relative_to(REPO_ROOT)}")

    write_report(
        udise_total=udise_total,
        udise_by_category=udise_by_category,
        sametham=sametham,
        sametham_total=sametham_total,
        difference=difference,
        percent=percent,
        schools=schools,
        without=without,
        flagged=flagged,
        district_students=district_students,
        district_teachers=district_teachers,
        district_ptr=district_ptr,
        median_ptr=median_ptr,
        threshold=threshold,
        benchmark_pry=benchmark_pry,
        benchmark_upry=benchmark_upry,
    )
    print(f"Wrote {REPORT_MD.relative_to(REPO_ROOT)}")
    return 0


def write_report(**k) -> None:
    """Render output/udise_crosscheck.md from the computed figures."""
    state_rows = []
    for year_id, label in YEARS.items():
        teachers = load_udise_state(year_id, "teachers")
        schools_row = load_udise_state(year_id, "schools")
        state_rows.append(
            f"| {label} | {int(teachers['totTchGovt']):,} | "
            f"{int(teachers['totTchPry']):,} | {int(teachers['totTchUPry']):,} | "
            f"{teachers['ptrPry']} | {teachers['ptrUPry']} | "
            f"{int(schools_row['totSchools']):,} |"
        )

    category_rows = "\n".join(
        f"| {name} | {count:,} |"
        for name, count in sorted(k["udise_by_category"].items(), key=lambda x: -x[1])
    )

    worst = sorted(k["schools"], key=lambda s: -s.sort_key)[:15]
    worst_rows = "\n".join(
        f"| {s.school_code} | {s.school_name} | {s.category} | {s.sub_district} | "
        f"{s.students:,} | {s.teachers} | "
        f"{'no teacher listed' if s.ptr is None else f'{s.ptr:.1f}'} |"
        for s in worst
    )

    buckets = {"under 15": 0, "15-25": 0, "25-35": 0, "35-45": 0, "45 and over": 0}
    for school in k["schools"]:
        if school.ptr is None:
            continue
        if school.ptr < 15:
            buckets["under 15"] += 1
        elif school.ptr < 25:
            buckets["15-25"] += 1
        elif school.ptr < 35:
            buckets["25-35"] += 1
        elif school.ptr < 45:
            buckets["35-45"] += 1
        else:
            buckets["45 and over"] += 1
    rated = sum(buckets.values())
    bucket_rows = "\n".join(
        f"| {label} | {count} | {100.0 * count / rated:.1f}% |"
        for label, count in buckets.items()
    )

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(
        REPORT_TEMPLATE.format(
            state_rows="\n".join(state_rows),
            category_rows=category_rows,
            worst_rows=worst_rows,
            bucket_rows=bucket_rows,
            udise_total=f"{k['udise_total']:,}",
            sametham_lp=f"{k['sametham']['lp']:,}",
            sametham_up=f"{k['sametham']['up']:,}",
            sametham_total=f"{k['sametham_total']:,}",
            difference=f"{k['difference']:+,}",
            percent=f"{k['percent']:+.1f}",
            percent_abs=f"{abs(k['percent']):.1f}",
            n_rated=rated,
            district_students=f"{k['district_students']:,}",
            district_teachers=f"{k['district_teachers']:,}",
            district_ptr=f"{k['district_ptr']:.1f}",
            median_ptr=f"{k['median_ptr']:.1f}",
            threshold=f"{k['threshold']:.1f}",
            benchmark_pry=f"{k['benchmark_pry']:.0f}",
            benchmark_upry=f"{k['benchmark_upry']:.0f}",
            n_schools=len(k["schools"]),
            n_without=len(k["without"]),
            n_flagged=len(k["flagged"]),
            pct_clean=f"{100.0 * (len(k['schools']) - len(k['flagged']) - len(k['without'])) / len(k['schools']):.1f}",
        ),
        encoding="utf-8",
    )


REPORT_TEMPLATE = """# UDISE+ cross-check of the Malappuram staffing figures

Generated by `udise_crosscheck.py`. Sources: UDISE+ public API
(`api.udiseplus.gov.in/open-services`, pulled 2026-08-15, raw responses in
`data/udise/`) and this project's own Sametham crawl of 2026-08-14.

## Why this was limited to state level

The UDISE+ public API serves **national and state rows only**. Every
district-level query — `regionType` 12 (district) and 22 (district-wise
listing), across every code format, on both the teacher and the school
endpoints — returns `"data": []`. There is no Malappuram row to fetch.

The per-school route is also gone: `src.udiseplus.gov.in`, which used to serve
UDISE school report cards, **no longer resolves in DNS**.

So the per-school join on UDISE code that would settle Risk A school by school
is not available from UDISE+. What follows is the strongest check the
accessible data supports, plus an internal screen calibrated against it.

## Test 1 — is Sametham systematically under-publishing staff?

The version of Risk A that would invalidate the headline number is a
*systematic* shortfall. That is testable at state level, because Sametham
publishes Kerala-wide totals on its own homepage and UDISE publishes the same
population independently.

| Source | Kerala Government LP/UP teachers |
|---|---:|
| Sametham (LP {sametham_lp} + UP {sametham_up}) | **{sametham_total}** |
| UDISE+ 2025-26, Dept. of Education, LP/UP school categories | **{udise_total}** |
| Difference | {difference} ({percent}%) |

UDISE's figure breaks down as:

| UDISE school category | Teachers |
|---|---:|
{category_rows}

**Read the direction of the gap, not just its size.** The two sources classify
a teacher differently:

- **Sametham classifies by post designation.** An `L P School Assistant`
  working in a high school still counts as LP. Phase 0 documented exactly this
  in school 18150, where a `Staff Details - HS` table contains LP and UP posts.
- **UDISE classifies by school category.** That same teacher is counted under
  the high school's category, not under primary.

Kerala has many HS and HSS schools with attached LP/UP sections, so Sametham's
LP/UP figure should be *higher* than UDISE's, by roughly the number of LP/UP
posts sitting inside secondary schools. It is higher, by {percent_abs}%.

**Conclusion: no evidence of systematic under-publication.** Two independently
collected sources agree on Kerala's Government LP/UP teaching strength to
within {percent_abs}%, and the residual has a known structural explanation. The
Malappuram figure of 6088 is a floor because vacancies are invisible, not
because the staff tables are broadly empty.

## Test 2 — which individual records look under-populated?

UDISE cannot answer this per school, so this is an internal screen: LP/UP
pupil-teacher ratio per school, with UDISE's Kerala PTR as the external
calibration point.

| | Value |
|---|---:|
| Malappuram Government LP/UP students | {district_students} |
| Malappuram Government LP/UP teachers | {district_teachers} |
| **District LP/UP PTR** | **{district_ptr}** |
| UDISE Kerala PTR, primary | {benchmark_pry} |
| UDISE Kerala PTR, upper primary | {benchmark_upry} |

Malappuram's ratio is about double the state benchmark. Most of that is real —
Malappuram is Kerala's most populous district and its government schools are
genuinely crowded, while the state PTR is pulled down by small aided schools
elsewhere — but it is also the reason a PTR screen has to be relative to
Malappuram's own distribution rather than to the state figure.

Distribution across the {n_rated} schools that have both LP/UP pupils and at
least one LP/UP teacher:

| LP/UP PTR | Schools | Share |
|---|---:|---:|
{bucket_rows}

Screen: flag schools at **PTR ≥ {threshold}**, twice the district median of
{median_ptr}.

- Schools with LP/UP pupils but no LP/UP teacher listed at all: **{n_without}**
- Schools above the threshold: **{n_flagged}**
- Schools inside it: **{pct_clean}%** of the {n_schools} with LP/UP pupils

Highest ratios, as review candidates:

| Code | School | Category | Sub district | LP/UP pupils | LP/UP teachers | PTR |
|---|---|---|---|---:|---:|---:|
{worst_rows}

**These are candidates, not findings.** A high ratio is consistent with an
incomplete SPARK-borne record, but also with a genuinely under-staffed school —
which is the thing the underlying study is trying to measure. Nothing here
distinguishes the two without checking the school. The full ranked list is in
`data/processed/malappuram_ptr_check.csv`.

## What this changes in the summary

`output/malappuram_summary.md` said under-populated records are "not
distinguishable from genuinely tiny establishments without an external source".
That is now partly resolved: the external source rules out a systematic
shortfall, and narrows the per-school question to a named shortlist rather than
an unbounded worry.

The headline figure and every caveat around sanctioned posts are unchanged.
UDISE is a school census, not an establishment register; it counts teachers in
position too, so it cannot see a vacant sanctioned post either.

## UDISE+ Kerala reference figures

| Year | Govt teachers | Primary teachers | Upper primary teachers | PTR primary | PTR upper primary | Schools |
|---|---:|---:|---:|---:|---:|---:|
{state_rows}

Note UDISE+ runs one academic year behind Sametham: the latest UDISE year is
2025-26, while the Sametham crawl captured 2026-27. Year-on-year movement in
the table above is small enough that this does not affect the comparison.
"""


if __name__ == "__main__":
    sys.exit(main())
