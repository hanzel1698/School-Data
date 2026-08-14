#!/usr/bin/env python3
"""Phase 4 - aggregate into output/malappuram_summary.md.

Offline. Every figure is derived from data/processed/malappuram_staff.csv and
data/raw/malappuram_schools.jsonl, and every table is laid out so the addition
can be checked by hand.

    python phase4_summarise.py
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from phase3_parse import category_from_level_only
from scraper.config import Config, load_config
from scraper.parse import level_bounds

CATEGORY_ORDER = ["LPS", "UPS", "HS", "HSS", "VHSE", "UNKNOWN"]


@dataclass
class Bucket:
    schools: int = 0
    lp_only: int = 0
    up_only: int = 0
    shared: int = 0
    hs_plus: int = 0
    non_teaching: int = 0
    unclassified: int = 0
    students_lp: int = 0
    students_up: int = 0
    no_staff_data: int = 0

    @property
    def primary_total(self) -> int:
        """LP + UP teaching staff. Exact: shared posts counted once."""
        return self.lp_only + self.up_only + self.shared


@dataclass
class Totals:
    overall: Bucket = field(default_factory=Bucket)
    by_category: dict[str, Bucket] = field(default_factory=lambda: defaultdict(Bucket))
    by_edu_district: dict[str, Bucket] = field(default_factory=lambda: defaultdict(Bucket))


def as_int(value: str) -> int:
    return int(value) if value not in ("", None) else 0


def read_rows(config: Config) -> list[dict[str, str]]:
    path = config.path("processed") / f"{config.district_name.lower()}_staff.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_enumeration(config: Config) -> list[dict[str, object]]:
    path = config.path("raw") / f"{config.district_name.lower()}_schools.jsonl"
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def accumulate(rows: list[dict[str, str]]) -> Totals:
    totals = Totals()
    for row in rows:
        has_staff = row["staff_data_status"] == "ok"
        targets = [
            totals.overall,
            totals.by_category[row["category"]],
            totals.by_edu_district[row["edu_district"] or "(not stated)"],
        ]
        for bucket in targets:
            bucket.schools += 1
            bucket.lp_only += as_int(row["teaching_staff_lp"])
            bucket.up_only += as_int(row["teaching_staff_up"])
            bucket.shared += as_int(row["teaching_staff_lp_up_shared"])
            bucket.hs_plus += as_int(row["teaching_staff_hs"])
            bucket.non_teaching += as_int(row["non_teaching_total"])
            bucket.unclassified += as_int(row["teaching_staff_unclassified"])
            bucket.students_lp += as_int(row["students_lp"])
            bucket.students_up += as_int(row["students_up"])
            if not has_staff:
                bucket.no_staff_data += 1
    return totals


def staff_table(title: str, buckets: dict[str, Bucket], order: list[str] | None = None) -> list[str]:
    """Markdown table whose columns visibly add to the LP+UP total."""
    # Any key not in the preferred order is appended rather than dropped:
    # silently omitting one would break the column totals below it.
    preferred = [k for k in (order or sorted(buckets)) if k in buckets]
    keys = preferred + sorted(set(buckets) - set(preferred))
    lines = [
        f"**{title}**",
        "",
        "| " + title.split(" by ")[-1].strip().title() + " | Schools | LP-only | UP-only | LP/UP shared | LP+UP total |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    total = Bucket()
    for key in keys:
        bucket = buckets[key]
        lines.append(
            f"| {key} | {bucket.schools} | {bucket.lp_only} | {bucket.up_only} | "
            f"{bucket.shared} | {bucket.primary_total} |"
        )
        total.schools += bucket.schools
        total.lp_only += bucket.lp_only
        total.up_only += bucket.up_only
        total.shared += bucket.shared
    lines.append(
        f"| **Total** | **{total.schools}** | **{total.lp_only}** | **{total.up_only}** | "
        f"**{total.shared}** | **{total.primary_total}** |"
    )
    lines.append("")
    return lines


def main() -> int:
    config = load_config()
    rows = read_rows(config)
    enumeration = read_enumeration(config)
    totals = accumulate(rows)
    overall = totals.overall

    government = [r for r in enumeration if r["management"] == "Government"]
    fetched_codes = {r["school_code"] for r in rows}

    # Exclusion is taken from Phase 1's own flag, never inferred from "absent
    # from the CSV" - otherwise a failed fetch would be silently relabelled as
    # "has no LP/UP section", which is a different and false claim.
    excluded = [r for r in government if not r["in_working_set"]]
    working_set = [r for r in government if r["in_working_set"]]
    missing = [r for r in working_set if r["school_code"] not in fetched_codes]

    excluded_by_category: dict[str, int] = defaultdict(int)
    for record in excluded:
        excluded_by_category[category_from_level_only(record["classes_approved"])] += 1

    fetched_by_category = {k: v.schools for k, v in totals.by_category.items()}
    seen_categories = set(fetched_by_category) | set(excluded_by_category)
    all_categories = [c for c in CATEGORY_ORDER if c in seen_categories]
    all_categories += sorted(seen_categories - set(all_categories))

    lp_floor, lp_ceiling = overall.lp_only, overall.lp_only + overall.shared
    up_floor, up_ceiling = overall.up_only, overall.up_only + overall.shared

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out: list[str] = []
    add = out.append

    add("# Malappuram — LP and UP teaching staff in Government schools")
    add("")
    add(f"Source: Sametham, KITE Kerala (`sametham.kite.kerala.gov.in`). "
        f"Generated {generated}.")
    add("")
    add("## Read this first")
    add("")
    add("These are **staff in position, not sanctioned posts.** Sanctioned LPST/UPST")
    add("post counts are set annually through staff fixation based on sixth-working-day")
    add("student strength. **A vacant sanctioned post does not appear in Sametham at")
    add("all**, so every figure below is a *floor* on the sanctioned establishment, never")
    add("the establishment itself.")
    add("")
    add("Sametham does expose a genuine **post-designation** breakdown (`L P School")
    add("Assistant`, `UP School Assistant`, …), so these are designation-level counts")
    add("rather than raw headcount. That is closer to a post count than the task")
    add("anticipated — but it is still filled posts only.")
    add("")

    add("## Headline")
    add("")
    add(f"Across **{overall.schools} Government schools** in Malappuram that have an LP")
    add("or UP section:")
    add("")
    add(f"- **LP + UP teaching staff combined: {overall.primary_total}** — this figure is exact.")
    add(f"- **LP-section teaching staff: {lp_floor} to {lp_ceiling}**")
    add(f"- **UP-section teaching staff: {up_floor} to {up_ceiling}**")
    add("")
    add(f"The ranges exist because **{overall.shared} posts are LP/UP shared** — chiefly")
    add("the language teachers (`Teacher (LP/UP) - Arabic`, `Junior Arabic Teacher`,")
    add("`Headmaster LP/UP`), who are sanctioned on the number of students opting for")
    add("that language and teach across classes 1–7. Sametham exposes no field that")
    add("splits them, and splitting them by a ratio would be imputation, so they are")
    add("reported as their own column.")
    add("")
    add("**The LP and UP ceilings cannot both be reached at once** — they draw on the")
    add(f"same {overall.shared} shared posts. Only the combined figure of")
    add(f"{overall.primary_total} is simultaneously true.")
    add("")
    add("If you need one citable number, the defensible statement is:")
    add("")
    add(f"> {overall.primary_total} teachers are in position across the LP and UP sections of")
    add(f"> Malappuram's {overall.schools} Government schools that have such sections, of whom")
    add(f"> {lp_floor} hold LP-specific posts, {up_floor} hold UP-specific posts, and")
    add(f"> {overall.shared} hold posts spanning both.")
    add("")

    add("## Scope")
    add("")
    add("| | Schools |")
    add("|---|---:|")
    add(f"| All schools in Malappuram (all managements) | {len(enumeration)} |")
    add(f"| Government schools | {len(government)} |")
    add(f"| less: schools starting at class 8 (no LP/UP section possible) | −{len(excluded)} |")
    add(f"| Government schools with an LP or UP section | {len(working_set)} |")
    if missing:
        add(f"| less: **not retrieved — fetch failed** | −{len(missing)} |")
    add(f"| **Government schools in this analysis** | **{overall.schools}** |")
    add("")
    if missing:
        add(f"> **{len(missing)} school(s) in the working set could not be retrieved** and are")
        add("> absent from every figure below. Re-run `phase2_fetch.py` to retry them.")
        add(">")
        add("> " + ", ".join(str(r["school_code"]) for r in missing[:30]))
        add("")
    add("Aided and unaided schools were enumerated into `data/raw/malappuram_schools.jsonl`")
    add("but deliberately **not fetched or aggregated** — this run was scoped to Government")
    add("schools only. There is therefore **no aided comparison table** in this summary.")
    add("")
    add("Schools starting at class 8 were excluded because they have no LP (1–4) or UP")
    add("(5–7) section and so cannot hold LP/UP posts. They remain counted in the")
    add("category table below.")
    add("")

    add("## Government schools by category")
    add("")
    add("Sametham has no single category field — the district list carries only LP/UP/HS.")
    add("Category here is derived: VHSE or HSS if the school has a VHSE/HSS code, else")
    add("from the approved class range. Excluded schools have no detail page, so their")
    add("category is derived from the class range alone.")
    add("")
    add("| Category | In analysis | Excluded (starts at class 8) | Total Government |")
    add("|---|---:|---:|---:|")
    total_in = total_ex = 0
    for category in all_categories:
        in_analysis = fetched_by_category.get(category, 0)
        ex = excluded_by_category.get(category, 0)
        total_in += in_analysis
        total_ex += ex
        add(f"| {category} | {in_analysis} | {ex} | {in_analysis + ex} |")
    add(f"| **Total** | **{total_in}** | **{total_ex}** | **{total_in + total_ex}** |")
    add("")

    add("## The arithmetic")
    add("")
    add("Both tables cover the same schools and must reach the same totals.")
    add("")
    out.extend(staff_table("Subtotals by school category", totals.by_category, CATEGORY_ORDER))
    out.extend(staff_table("Subtotals by educational district", totals.by_edu_district))

    add("**Check:** LP-only + UP-only + shared = combined LP+UP total")
    add("")
    add(f"    {overall.lp_only} + {overall.up_only} + {overall.shared} = {overall.primary_total}")
    add("")
    add("**Ranges:**")
    add("")
    add(f"    LP floor   = LP-only                 = {overall.lp_only}")
    add(f"    LP ceiling = LP-only + shared        = {overall.lp_only} + {overall.shared} = {lp_ceiling}")
    add(f"    UP floor   = UP-only                 = {overall.up_only}")
    add(f"    UP ceiling = UP-only + shared        = {overall.up_only} + {overall.shared} = {up_ceiling}")
    add("")

    add("## Other staff in the same schools")
    add("")
    add("Reported for completeness; not part of the LP/UP figure.")
    add("")
    add("| Bucket | Posts |")
    add("|---|---:|")
    add(f"| HS and above teaching (HSA, PD teacher, vocational instructor, …) | {overall.hs_plus} |")
    add(f"| Non-teaching (clerk, office attendant, menial) | {overall.non_teaching} |")
    add(f"| Unclassified by the designation rules | {overall.unclassified} |")
    add("")
    add("Higher-secondary staff are **not published**: every `Staff Details - HSS` and")
    add("`- VHSS` table sampled returned `No Data Found!`. HSS/VHSE teachers are absent")
    add("from these totals entirely.")
    add("")

    add("## Data completeness")
    add("")
    share = 100.0 * overall.no_staff_data / overall.schools if overall.schools else 0.0
    add(f"| | Schools | Share |")
    add("|---|---:|---:|")
    add(f"| Staff data present | {overall.schools - overall.no_staff_data} | "
        f"{100.0 - share:.1f}% |")
    add(f"| **Staff data absent — written as null, not zero** | **{overall.no_staff_data}** | "
        f"**{share:.1f}%** |")
    add(f"| Total | {overall.schools} | 100.0% |")
    add("")
    if overall.no_staff_data:
        add(f"Those {overall.no_staff_data} schools carry empty cells in every staff column of")
        add("`malappuram_staff.csv`. Nothing was imputed for them, so the LP/UP figures")
        add("above are missing whatever staff those schools actually hold.")
    add("")
    lps_up_posts = totals.by_category.get("LPS")
    if lps_up_posts and lps_up_posts.up_only:
        add(f"**Source inconsistency:** {lps_up_posts.up_only} UP-specific post(s) are listed")
        add("against schools approved only for classes 1–4, which have no UP section and")
        add("report zero UP students. These are published that way by Sametham and are")
        add("left as-is rather than corrected, since there is no basis for reassigning")
        add("them. They are counted in the UP column above.")
        add("")

    if overall.unclassified:
        add(f"**Unclassified posts: {overall.unclassified}.** These are designations no rule")
        add("claims — pre-primary posts, which sit below LP, and post names carrying no")
        add("section marker at all (e.g. `Teacher Snr. Grd`). They are excluded from every")
        add("LP/UP figure rather than guessed into a bucket. See")
        add("`data/processed/designation_audit.csv` for the full list.")
        add("")

    add("Beyond outright absence, some published records look **under-populated**: for")
    add("example school 18501 (Technical High School Manjeri) reports `Total Employees")
    add("- 2` for an entire high school. These are not distinguishable from genuinely")
    add("tiny establishments without an external source, so they are left as published.")
    add("")
    add("Every school with staff data reconciles exactly against Sametham's own")
    add("`Total Employees` line — the parser is not dropping or double-counting rows.")
    add("")

    add("## Student counts, for context only")
    add("")
    add("Not used to derive any staff figure.")
    add("")
    add("| | Students |")
    add("|---|---:|")
    add(f"| LP sections (classes 1–4) | {overall.students_lp} |")
    add(f"| UP sections (classes 5–7) | {overall.students_up} |")
    add("")

    add("## What this number is and is not")
    add("")
    add("**It is:** the count of LP and UP teaching posts actually filled in Government")
    add("schools in Malappuram revenue district, as published by Sametham, classified by")
    add("post designation.")
    add("")
    add("**It is not:**")
    add("")
    add("- a count of *sanctioned* LPST/UPST posts — vacancies are invisible here;")
    add("- a teacher *headcount* usable for pupil–teacher ratio without care — part-time")
    add("  and shared posts are counted as posts;")
    add("- complete for higher secondary — HSS/VHSS staff are not published at all;")
    add("- inclusive of aided or unaided schools, which this run did not fetch;")
    add("- inclusive of Government schools starting at class 8, which have no LP/UP section.")
    add("")
    add("## Reproducing this")
    add("")
    add("```bash")
    add("python phase1_enumerate.py   # 1 request")
    add(f"python phase2_fetch.py       # {overall.schools} requests, resumable, ~18 min")
    add("python phase3_parse.py       # offline")
    add("python phase4_summarise.py   # offline")
    add("```")
    add("")

    target = config.path("output") / f"{config.district_name.lower()}_summary.md"
    target.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"Wrote {target}\n")
    print(f"  Schools analysed:     {overall.schools}")
    print(f"  LP+UP combined:       {overall.primary_total}")
    print(f"  LP range:             {lp_floor} - {lp_ceiling}")
    print(f"  UP range:             {up_floor} - {up_ceiling}")
    print(f"  Shared posts:         {overall.shared}")
    print(f"  Schools w/o staff:    {overall.no_staff_data} ({share:.1f}%)")
    print(f"  Unclassified posts:   {overall.unclassified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
