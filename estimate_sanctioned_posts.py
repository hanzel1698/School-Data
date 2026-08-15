#!/usr/bin/env python3
"""
Estimate LP/UP division entitlement per school, and validate the estimate
against the department's own 2026-27 staff-fixation decisions.

The problem this addresses: every figure in output/malappuram_summary.md is
staff *in position*. A vacant sanctioned post appears in no public source, so
vacancies cannot be read off Sametham. They can be approached from the other
side - reconstruct how many class divisions each school's enrolment earns, and
compare against who is actually in place.

## The rule

The division tables below are transcribed from the Kerala staff-fixation ready
reckoner and strength-wise division tables in data/sources/, cross-checked
against muralipanamanna.in. They are not flat ratios: LP plateaus at 5
divisions across the whole 121-200 band and then moves in steps of 40 rather
than 30. Per standard those upper bands are almost never reached, so on this
data the tables and a flat ceil(n/ratio) differ by only a division or two
district-wide - but the tables are what the rule says, so the tables are used.

The ratio bands do **not** line up with the sections. The reckoner applies
1:30 to standards I-V and 1:35 to VI-VIII, so standard 5 sits in the UP section
but forms divisions at the LP ratio. Modelling it that way rather than by
section is worth a little accuracy (AUC 0.879 against 0.878).

Three further choices were tested against the department's decisions rather
than assumed, and one of them overturned this script's first attempt:

  * **Divisions are counted per standard, on combined-medium strength.** Not
    per section total (AUC 0.837), and not per standard *and* medium
    (AUC 0.862). Counting each standard once, across all media, scores 0.879.
    Sametham publishes a Standard x Medium table and it is tempting to split on
    it - this script originally did - but the fixation decisions say do not.
    Pass --medium-wise to see the rejected variant.
  * **Every LP/UP-attached teaching post counts**, including the headmaster and
    the Arabic/Urdu/Hindi language teachers that malappuram_summary.md reports
    as the shared column. Excluding them drops separation to 0.827. A Kerala
    LP/UP headmaster commonly holds a division, and the reckoner shows language
    posts are sanctioned on periods-per-division, so they scale with divisions
    rather than sitting outside them. Pass --exclude-shared for that variant.
  * **1:30 and 1:35 are correct.** Sweeping both from 1:24 to 1:45 peaks at
    LP 1:31 / UP 1:35 (AUC 0.882); the rule's own values score 0.879, inside
    the noise, so the rule is kept rather than a fitted approximation to it.

## What is not modelled

  * **Effective strength.** The reckoner defines it as
    `Verified Strength + (Roll Strength x 5%)`, capped at roll strength.
    Sametham publishes one enrolment figure and does not say which of the two
    it is, so no adjustment is applied. Adding a flat 5% moves the district
    total by about 120 posts and *lowers* separation to 0.874, which suggests
    Sametham's figure already behaves like the effective one - but that is
    inference, not evidence.
  * The pupils-opting threshold for language teachers - the reckoner requires a
    minimum of 30 pupils in the UP section for one Hindi/Sanskrit/Arabic post,
    and Sametham does not publish language options per school.
  * Specialist posts (PD teacher, drawing, sewing), excluded from both sides.
  * Relaxations for hilly, coastal and single-teacher schools. Sametham carries
    Is Hilly Area and Is Coastal Area flags, so this remains testable.
  * Post protection: a teacher whose post is abolished is redeployed, not
    removed, so a school can hold protected staff above its entitlement.

The result is a signed **imbalance**, not a vacancy count. Positive means more
teachers in place than divisions earn; negative means fewer. Both are common.

## Validation

The DDE order of 14.07.2026 gives 134 schools a known verdict: 65 lost posts
(carrying surplus) and 69 received redeployed teachers (posts available). Both
the fixation and this estimate run off the same sixth-working-day enrolment,
and the staff figures predate the 15.07.2026 redeployment, so the comparison is
aligned in time.

Scoring is threshold-free: the reported AUC is the probability that a school
the department found surplus scores above one it sent teachers to. The
department's own cut-off is not at zero and is not published, so a straight
sign-agreement figure would understate a model that ranks correctly but sits
off-centre. Both are printed.

Usage:
    python estimate_sanctioned_posts.py
    python estimate_sanctioned_posts.py --calibrate
    python estimate_sanctioned_posts.py --medium-wise --exclude-shared
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from scraper.parse import parse_school_detail

REPO_ROOT = Path(__file__).resolve().parent
CACHE_DIR = REPO_ROOT / "data/cache"
STAFF_CSV = REPO_ROOT / "data/processed/malappuram_staff.csv"
DEPLOYMENT_CSV = REPO_ROOT / "data/processed/malappuram_deployment_2026_27.csv"
OUTPUT_CSV = REPO_ROOT / "data/processed/malappuram_division_estimate.csv"

# Section membership, as Kerala organises schools: LP is standards 1-4, UP is
# 5-7. Used for reporting subtotals and for matching the rest of the project.
LP_STANDARDS = ("1", "2", "3", "4")
UP_STANDARDS = ("5", "6", "7")

# Division *ratio* bands, which do not line up with the sections. The ready
# reckoner applies 1:30 to standards I-V and 1:35 to VI-VIII, so standard 5 is
# a UP-section standard whose divisions are formed at the LP ratio.
RATIO_30_STANDARDS = ("1", "2", "3", "4", "5")
RATIO_35_STANDARDS = ("6", "7")
DEFAULT_LP_STRENGTH = 30
DEFAULT_UP_STRENGTH = 35

# KER staff-fixation division tables, as (from, to, divisions). Note the LP
# plateau at 121-200 and the switch to 40-pupil steps above it; UP is a clean
# 1:35 throughout. Beyond the last band the step continues (LP 40, UP 35).
LP_DIVISION_TABLE = [
    (1, 30, 1), (31, 60, 2), (61, 90, 3), (91, 120, 4), (121, 150, 5),
    (151, 200, 5), (201, 240, 6), (241, 280, 7), (281, 320, 8), (321, 360, 9),
    (361, 400, 10), (401, 440, 11), (441, 480, 12), (481, 520, 13),
    (521, 560, 14), (561, 600, 15), (601, 640, 16), (641, 680, 17),
    (681, 720, 18), (721, 760, 19), (761, 800, 20), (801, 840, 21),
    (841, 880, 22), (881, 920, 23), (921, 960, 24), (961, 1000, 25),
    (1001, 1040, 26),
]
LP_TAIL_STEP = 40
UP_DIVISION_TABLE = [
    (1, 35, 1), (36, 70, 2), (71, 105, 3), (106, 140, 4), (141, 175, 5),
    (176, 210, 6), (211, 245, 7), (246, 280, 8), (281, 315, 9), (316, 350, 10),
    (351, 385, 11), (386, 420, 12), (421, 455, 13), (456, 490, 14),
    (491, 525, 15), (526, 560, 16), (561, 595, 17), (596, 630, 18),
    (631, 665, 19), (666, 700, 20), (701, 735, 21), (736, 770, 22),
    (771, 805, 23), (806, 840, 24), (841, 875, 25), (876, 910, 26),
    (911, 945, 27),
]
UP_TAIL_STEP = 35


@dataclass
class SchoolEstimate:
    school_code: str
    school_name: str
    category: str
    sub_district: str
    students_lp: int
    students_up: int
    divisions_lp: int
    divisions_up: int
    actual_lp: int
    actual_up: int
    shared: int
    count_shared: bool = True

    @property
    def divisions(self) -> int:
        return self.divisions_lp + self.divisions_up

    @property
    def actual(self) -> int:
        """LP/UP teaching posts filled, counted against divisions."""
        total = self.actual_lp + self.actual_up
        return total + self.shared if self.count_shared else total

    @property
    def imbalance(self) -> int:
        """Staff in place minus divisions earned. Positive means surplus."""
        return self.actual - self.divisions

    @property
    def verdict(self) -> str:
        if self.imbalance > 0:
            return "surplus"
        if self.imbalance < 0:
            return "shortfall"
        return "balanced"


def divisions_from_table(
    pupils: int, table: list[tuple[int, int, int]], tail_step: int, strength: int
) -> int:
    """Divisions for a strength, from the KER table.

    `strength` is honoured only when it differs from the table's own ratio, so
    that --calibrate can sweep the ratio without discarding the table shape.
    """
    if pupils <= 0:
        return 0
    table_ratio = table[0][1]
    if strength != table_ratio:
        return math.ceil(pupils / strength)
    for low, high, divisions in table:
        if low <= pupils <= high:
            return divisions
    low, high, divisions = table[-1]
    return divisions + math.ceil((pupils - high) / tail_step)


def count_divisions(
    by_standard: dict[str, int],
    by_standard_medium: dict[str, dict[str, int]],
    standards: tuple[str, ...],
    lp_strength: int,
    up_strength: int,
    medium_wise: bool,
) -> int:
    """Divisions for the given standards, each at its own ratio band."""
    total = 0
    for standard in standards:
        if standard in RATIO_30_STANDARDS:
            table, tail_step, strength = LP_DIVISION_TABLE, LP_TAIL_STEP, lp_strength
        else:
            table, tail_step, strength = UP_DIVISION_TABLE, UP_TAIL_STEP, up_strength
        if medium_wise:
            strengths = [n for n in by_standard_medium.get(standard, {}).values() if n > 0]
        else:
            pupils = by_standard.get(standard, 0)
            strengths = [pupils] if pupils > 0 else []
        for pupils in strengths:
            total += divisions_from_table(pupils, table, tail_step, strength)
    return total


def integer(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    return int(value) if value not in ("", "None", None) else 0


_PARSED_CACHE: dict[str, tuple[dict[str, int], dict[str, dict[str, int]]]] = {}


def _enrolment(code: str) -> tuple[dict[str, int], dict[str, dict[str, int]]] | None:
    """Cached parse, so a calibration sweep reads each page only once."""
    if code not in _PARSED_CACHE:
        cached = CACHE_DIR / f"{code}.html"
        if not cached.exists():
            return None
        detail = parse_school_detail(cached.read_text(encoding="utf-8", errors="replace"))
        _PARSED_CACHE[code] = (
            detail.students_by_standard, detail.students_by_standard_medium
        )
    return _PARSED_CACHE[code]


def load_estimates(
    lp_strength: int = DEFAULT_LP_STRENGTH,
    up_strength: int = DEFAULT_UP_STRENGTH,
    quiet: bool = False,
    count_shared: bool = True,
    medium_wise: bool = False,
) -> list[SchoolEstimate]:
    staff = {r["school_code"]: r for r in csv.DictReader(STAFF_CSV.open(encoding="utf-8"))}
    estimates: list[SchoolEstimate] = []
    missing: list[str] = []

    for code, row in staff.items():
        parsed = _enrolment(code)
        if parsed is None:
            missing.append(code)
            continue
        by_standard, by_medium = parsed
        if not by_standard:
            missing.append(code)
            continue

        estimates.append(SchoolEstimate(
            school_code=code,
            school_name=row["school_name"],
            category=row["category"],
            sub_district=row["sub_district"],
            students_lp=sum(by_standard.get(s, 0) for s in LP_STANDARDS),
            students_up=sum(by_standard.get(s, 0) for s in UP_STANDARDS),
            divisions_lp=count_divisions(
                by_standard, by_medium, LP_STANDARDS,
                lp_strength, up_strength, medium_wise,
            ),
            divisions_up=count_divisions(
                by_standard, by_medium, UP_STANDARDS,
                lp_strength, up_strength, medium_wise,
            ),
            actual_lp=integer(row, "teaching_staff_lp"),
            actual_up=integer(row, "teaching_staff_up"),
            shared=integer(row, "teaching_staff_lp_up_shared"),
            count_shared=count_shared,
        ))

    if missing and not quiet:
        print(f"warning: {len(missing)} school(s) skipped for want of cached "
              f"enrolment data: {missing[:5]}")
    return estimates


def load_ground_truth() -> tuple[set[str], set[str]]:
    """Schools that lost posts, and schools that received teachers."""
    lost: set[str] = set()
    received: set[str] = set()
    with DEPLOYMENT_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["from_school_code"]:
                lost.add(row["from_school_code"])
            if row["to_school_code"]:
                received.add(row["to_school_code"])
    both = lost & received  # no clean verdict; drop from the test
    return lost - both, received - both


def separation(estimates: list[SchoolEstimate]) -> float:
    """AUC of the imbalance as a ranking statistic over the known verdicts."""
    lost, received = load_ground_truth()
    by_code = {e.school_code: e for e in estimates}
    surplus = [by_code[c].imbalance for c in lost if c in by_code]
    shortfall = [by_code[c].imbalance for c in received if c in by_code]
    if not surplus or not shortfall:
        return 0.5
    wins = sum(
        1.0 if a > b else 0.5 if a == b else 0.0
        for a in surplus for b in shortfall
    )
    return wins / (len(surplus) * len(shortfall))


def validate(estimates: list[SchoolEstimate]) -> dict:
    lost, received = load_ground_truth()
    by_code = {e.school_code: e for e in estimates}
    labelled = [(c, "surplus") for c in lost if c in by_code]
    labelled += [(c, "shortfall") for c in received if c in by_code]

    matrix: dict[tuple[str, str], int] = {}
    for code, truth in labelled:
        key = (truth, by_code[code].verdict)
        matrix[key] = matrix.get(key, 0) + 1

    correct = sum(n for (truth, predicted), n in matrix.items() if truth == predicted)
    backwards = sum(
        n for (truth, predicted), n in matrix.items()
        if predicted != "balanced" and truth != predicted
    )
    return {
        "labelled": len(labelled),
        "lost": len([c for c in lost if c in by_code]),
        "received": len([c for c in received if c in by_code]),
        "matrix": matrix,
        "correct": correct,
        "backwards": backwards,
        "agreement": correct / len(labelled) if labelled else 0.0,
    }


def write_csv(estimates: list[SchoolEstimate], lost: set[str], received: set[str]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "school_code", "school_name", "category", "sub_district",
            "students_lp", "students_up", "divisions_lp", "divisions_up",
            "divisions_total", "staff_lp", "staff_up", "staff_lp_up_shared",
            "staff_counted", "imbalance", "verdict", "fixation_2026_27",
        ])
        for e in sorted(estimates, key=lambda e: e.imbalance):
            truth = "lost posts" if e.school_code in lost else (
                "received teachers" if e.school_code in received else "")
            writer.writerow([
                e.school_code, e.school_name, e.category, e.sub_district,
                e.students_lp, e.students_up, e.divisions_lp, e.divisions_up,
                e.divisions, e.actual_lp, e.actual_up, e.shared, e.actual,
                e.imbalance, e.verdict, truth,
            ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lp-strength", type=int, default=DEFAULT_LP_STRENGTH)
    parser.add_argument("--up-strength", type=int, default=DEFAULT_UP_STRENGTH)
    parser.add_argument(
        "--medium-wise", action="store_true",
        help="form divisions separately per medium (tested and rejected: "
             "AUC 0.862 against 0.878)",
    )
    parser.add_argument(
        "--exclude-shared", action="store_true",
        help="omit the headmaster and language teachers from the staff side "
             "(tested and rejected: AUC 0.814)",
    )
    parser.add_argument(
        "--calibrate", action="store_true",
        help="sweep division strengths against the department's decisions",
    )
    args = parser.parse_args()
    options = dict(count_shared=not args.exclude_shared, medium_wise=args.medium_wise)

    if args.calibrate:
        scored = sorted(
            (separation(load_estimates(lp, up, quiet=True, **options)), lp, up)
            for lp in range(24, 41) for up in range(24, 46)
        )
        print("Best division strengths by separation against the department")
        print(f"{'AUC':>6}  {'LP':>3}  {'UP':>3}")
        for auc, lp, up in list(reversed(scored))[:10]:
            print(f"{auc:6.3f}  {lp:>3}  {up:>3}")
        default = next(
            (a for a, lp, up in scored
             if (lp, up) == (DEFAULT_LP_STRENGTH, DEFAULT_UP_STRENGTH)), None
        )
        if default is not None:
            print(f"\nDefault 1:{DEFAULT_LP_STRENGTH} / 1:{DEFAULT_UP_STRENGTH} "
                  f"scores {default:.3f}")
        return 0

    estimates = load_estimates(args.lp_strength, args.up_strength, **options)
    if not estimates:
        print("No estimates - run phase2_fetch.py to populate data/cache/ first.")
        return 1

    lost, received = load_ground_truth()
    write_csv(estimates, lost, received)
    result = validate(estimates)

    divisions = sum(e.divisions for e in estimates)
    actual = sum(e.actual for e in estimates)
    counts = {v: sum(1 for e in estimates if e.verdict == v)
              for v in ("shortfall", "balanced", "surplus")}

    print(f"schools estimated            : {len(estimates)}")
    print(f"divisions earned             : {divisions:,}")
    print(f"LP/UP posts filled           : {actual:,}")
    print(f"district imbalance           : {actual - divisions:+,}")
    print(f"  short / balanced / surplus : {counts['shortfall']} / "
          f"{counts['balanced']} / {counts['surplus']}")
    print()
    print(f"labelled schools from the order: {result['labelled']} "
          f"({result['lost']} lost posts, {result['received']} received)")
    print(f"ranking separation (AUC)       : {separation(estimates):.3f}  "
          f"(0.5 = no signal, 1.0 = perfect)")
    print(f"estimate agrees with department: {result['correct']} "
          f"({100.0 * result['agreement']:.0f}%)")
    print(f"estimate got the sign backwards: {result['backwards']}")
    print("\nconfusion (department verdict -> estimate verdict):")
    for (truth, predicted), count in sorted(result["matrix"].items()):
        print(f"    {truth:10} -> {predicted:10} {count:>4}")
    print(f"\nWrote {OUTPUT_CSV.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
