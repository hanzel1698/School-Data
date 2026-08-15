#!/usr/bin/env python3
"""
Estimate division-based LP/UP teaching posts per school, and validate the
estimate against the department's own 2026-27 staff-fixation decisions.

The problem this addresses: every figure in output/malappuram_summary.md is
staff *in position*. A vacant sanctioned post appears in no public source, so
vacancies cannot be read off Sametham directly. They can, however, be
approached from the other side - reconstruct how many posts the school's
enrolment entitles it to, and compare against who is actually in place.

How Kerala sanctions LP/UP teaching posts, and what this script models:

  * Posts follow **class divisions**, not a pupil-teacher ratio applied to a
    section total. Divisions are formed **per standard** and **per medium**, so
    a standard with 19 Malayalam-medium and 34 English-medium pupils is three
    divisions, not the two that 53/30 would suggest. The script computes
    ceil(pupils / strength) for every (standard, medium) cell with pupils in
    it. The naive aggregate is also reported, purely to show the size of the
    error it would introduce.
  * Division strength defaults to 30 for LP (standards 1-4) and 35 for UP
    (standards 5-7). Sweeping both against the department's own 2026-27
    verdicts (see --calibrate) peaks at LP 1:31 / UP 1:39 with AUC 0.867, and
    1:30/1:35 scores 0.862 - inside the noise, so the conventional figures are
    kept rather than fitted ones. **Confirm against the current KER text before
    citing any output**; division norms carry relaxations this does not model.

  * The comparison counts **every LP/UP-attached teaching post against
    divisions, including the shared column** - the headmaster and the
    Arabic/Urdu/Hindi language teachers. That is an empirical choice too, and it
    matters more than the strength does. Excluding them, on the theory that
    only LP-specific and UP-specific designations hold divisions, drops the
    separation from 0.862 to 0.814 and leaves the model calling 25 of the 65
    known-surplus schools a shortfall. In practice a Kerala LP/UP headmaster
    commonly holds a division and language teachers take classes across
    standards 1-7, and the fixation decisions bear that out. Pass
    --exclude-shared to see the weaker variant.

What the estimate does NOT model, because these are not division-derived and no
public source gives their basis per school:

  * The separate entitlement basis for language teachers - they are sanctioned
    on the number of pupils opting for that language, so a school can hold one
    for reasons this model cannot see.
  * Specialist posts - PD teacher, drawing, sewing. These are excluded from
    both sides of the comparison.
  * Relaxations for hilly, coastal and single-teacher schools.
  * Post protection: a teacher whose post is abolished is redeployed, not
    removed, so a school can legitimately hold more staff than its fixation
    warrants until the surplus is cleared.

The result is a signed **imbalance**, not a vacancy count. Positive means more
teachers in place than divisions earn; negative means fewer. Both occur, and
the 2026-27 order shows surplus was the commoner case in Malappuram this year.

## Validation

The DDE order of 14.07.2026 gives 137 schools with a known verdict from the
department's own fixation: 68 lost posts (they were carrying surplus) and 71
received redeployed teachers (they had posts available). Both that fixation and
this estimate run off the same sixth-working-day enrolment, and the staff
figures here predate the 15.07.2026 redeployment, so the comparison is properly
aligned in time. If the estimate reproduces the department's verdict on those
schools, it is worth something on the other 385. That agreement rate is the
headline output - not the vacancy numbers.

Scoring is threshold-free: the reported AUC is the probability that a school
the department found surplus scores above one it sent teachers to. The
department's own cut-off is not at zero and is not published, so a straight
sign-agreement figure would understate a model that ranks correctly but sits
off-centre. Both are printed.

Usage:
    python estimate_sanctioned_posts.py
    python estimate_sanctioned_posts.py --calibrate
    python estimate_sanctioned_posts.py --lp-strength 33 --exclude-shared
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

LP_STANDARDS = ("1", "2", "3", "4")
UP_STANDARDS = ("5", "6", "7")
# Confirmed against the department's 2026-27 decisions rather than assumed;
# see the module docstring and --calibrate.
DEFAULT_LP_STRENGTH = 30
DEFAULT_UP_STRENGTH = 35


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
    naive_divisions_lp: int
    naive_divisions_up: int
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


def divisions_for(
    by_standard_medium: dict[str, dict[str, int]],
    standards: tuple[str, ...],
    strength: int,
) -> int:
    """Divisions across the given standards, formed per standard and medium."""
    total = 0
    for standard in standards:
        for pupils in by_standard_medium.get(standard, {}).values():
            if pupils > 0:
                total += math.ceil(pupils / strength)
    return total


def naive_divisions_for(
    by_standard: dict[str, int], standards: tuple[str, ...], strength: int
) -> int:
    """What you get by dividing the whole section total. Shown for contrast."""
    pupils = sum(by_standard.get(standard, 0) for standard in standards)
    return math.ceil(pupils / strength) if pupils else 0


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
        _PARSED_CACHE[code] = (detail.students_by_standard, detail.students_by_standard_medium)
    return _PARSED_CACHE[code]


def load_estimates(
    lp_strength: int, up_strength: int, quiet: bool = False,
    count_shared: bool = True,
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
        if not by_medium:
            missing.append(code)
            continue

        estimates.append(SchoolEstimate(
            school_code=code,
            school_name=row["school_name"],
            category=row["category"],
            sub_district=row["sub_district"],
            students_lp=sum(by_standard.get(s, 0) for s in LP_STANDARDS),
            students_up=sum(by_standard.get(s, 0) for s in UP_STANDARDS),
            divisions_lp=divisions_for(by_medium, LP_STANDARDS, lp_strength),
            divisions_up=divisions_for(by_medium, UP_STANDARDS, up_strength),
            naive_divisions_lp=naive_divisions_for(by_standard, LP_STANDARDS, lp_strength),
            naive_divisions_up=naive_divisions_for(by_standard, UP_STANDARDS, up_strength),
            actual_lp=integer(row, "teaching_staff_lp"),
            actual_up=integer(row, "teaching_staff_up"),
            shared=integer(row, "teaching_staff_lp_up_shared"),
            count_shared=count_shared,
        ))

    if missing and not quiet:
        print(f"warning: {len(missing)} school(s) skipped for want of cached "
              f"standard x medium data: {missing[:5]}")
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
    # A school on both sides carries no clean verdict; drop it from the test.
    both = lost & received
    return lost - both, received - both


def validate(estimates: list[SchoolEstimate]) -> dict:
    lost, received = load_ground_truth()
    by_code = {e.school_code: e for e in estimates}
    labelled = [(code, "surplus") for code in lost if code in by_code]
    labelled += [(code, "shortfall") for code in received if code in by_code]

    matrix: dict[tuple[str, str], int] = {}
    for code, truth in labelled:
        predicted = by_code[code].verdict
        matrix[(truth, predicted)] = matrix.get((truth, predicted), 0) + 1

    correct = sum(count for (truth, predicted), count in matrix.items() if truth == predicted)
    wrong_sign = sum(
        count for (truth, predicted), count in matrix.items()
        if predicted != "balanced" and truth != predicted
    )
    return {
        "labelled": len(labelled),
        "lost": len([c for c in lost if c in by_code]),
        "received": len([c for c in received if c in by_code]),
        "matrix": matrix,
        "correct": correct,
        "wrong_sign": wrong_sign,
        "agreement": correct / len(labelled) if labelled else 0.0,
    }


def write_csv(estimates: list[SchoolEstimate], lost: set[str], received: set[str]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "school_code", "school_name", "category", "sub_district",
            "students_lp", "students_up",
            "divisions_lp", "divisions_up", "divisions_total",
            "naive_divisions_total",
            "staff_lp", "staff_up", "staff_lp_up_shared", "staff_division_based",
            "imbalance", "verdict", "fixation_2026_27",
        ])
        for e in sorted(estimates, key=lambda e: e.imbalance):
            truth = "lost posts" if e.school_code in lost else (
                "received teachers" if e.school_code in received else "")
            writer.writerow([
                e.school_code, e.school_name, e.category, e.sub_district,
                e.students_lp, e.students_up,
                e.divisions_lp, e.divisions_up, e.divisions,
                e.naive_divisions_lp + e.naive_divisions_up,
                e.actual_lp, e.actual_up, e.shared, e.actual,
                e.imbalance, e.verdict, truth,
            ])


def separation(estimates: list[SchoolEstimate]) -> tuple[float, int, int]:
    """How well the imbalance ranks the department's own verdicts.

    Returns the probability that a randomly chosen school the department found
    surplus in scores higher than a randomly chosen school it sent teachers to
    (ties counted as half) - the AUC of the imbalance as a ranking statistic.
    0.5 means the estimate carries no information about the decisions; 1.0
    means it orders them perfectly. This is threshold-free on purpose: the
    department's own cut-off is not at zero and is not published.
    """
    lost, received = load_ground_truth()
    by_code = {e.school_code: e for e in estimates}
    surplus = [by_code[c].imbalance for c in lost if c in by_code]
    shortfall = [by_code[c].imbalance for c in received if c in by_code]
    if not surplus or not shortfall:
        return 0.5, len(surplus), len(shortfall)

    wins = sum(
        1.0 if a > b else 0.5 if a == b else 0.0
        for a in surplus for b in shortfall
    )
    return wins / (len(surplus) * len(shortfall)), len(surplus), len(shortfall)


def calibrate(
    lp_range: range, up_range: range, count_shared: bool = True
) -> list[tuple[float, int, int]]:
    """Sweep division strengths and score each against the department."""
    scored: list[tuple[float, int, int]] = []
    for lp in lp_range:
        for up in up_range:
            estimates = load_estimates(lp, up, quiet=True, count_shared=count_shared)
            auc, _, _ = separation(estimates)
            scored.append((auc, lp, up))
    return sorted(scored, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lp-strength", type=int, default=DEFAULT_LP_STRENGTH)
    parser.add_argument("--up-strength", type=int, default=DEFAULT_UP_STRENGTH)
    parser.add_argument(
        "--exclude-shared", action="store_true",
        help="count only LP-specific and UP-specific designations against "
             "divisions, omitting the headmaster and language teachers",
    )
    parser.add_argument(
        "--calibrate", action="store_true",
        help="sweep division strengths and report which best reproduces the "
             "department's 2026-27 decisions",
    )
    args = parser.parse_args()

    count_shared = not args.exclude_shared

    if args.calibrate:
        scored = calibrate(range(22, 46), range(22, 46), count_shared)
        print("Best division strengths by separation against the department's verdicts")
        print(f"{'AUC':>6}  {'LP':>3}  {'UP':>3}")
        for auc, lp, up in scored[:15]:
            print(f"{auc:6.3f}  {lp:>3}  {up:>3}")
        baseline = next(
            (auc for auc, lp, up in scored
             if lp == DEFAULT_LP_STRENGTH and up == DEFAULT_UP_STRENGTH), None
        )
        print(f"\nAssumed 1:{DEFAULT_LP_STRENGTH} / 1:{DEFAULT_UP_STRENGTH} scores "
              f"{baseline:.3f}" if baseline else "")
        return 0

    estimates = load_estimates(args.lp_strength, args.up_strength,
                               count_shared=count_shared)
    if not estimates:
        print("No estimates - run phase2_fetch.py to populate data/cache/ first.")
        return 1

    lost, received = load_ground_truth()
    write_csv(estimates, lost, received)
    result = validate(estimates)

    divisions = sum(e.divisions for e in estimates)
    naive = sum(e.naive_divisions_lp + e.naive_divisions_up for e in estimates)
    actual = sum(e.actual for e in estimates)

    print(f"schools estimated            : {len(estimates)}")
    print(f"divisions (per standard+medium): {divisions:,}")
    print(f"divisions (naive aggregate)  : {naive:,}  "
          f"({divisions - naive:+,}, {100.0 * (divisions - naive) / naive:+.1f}%)")
    print(f"division-based staff in place: {actual:,}")
    print(f"district imbalance           : {actual - divisions:+,}")
    print()
    auc, n_surplus, n_shortfall = separation(estimates)
    print(f"labelled schools from the order: {result['labelled']} "
          f"({result['lost']} lost posts, {result['received']} received)")
    print(f"ranking separation (AUC)       : {auc:.3f}  "
          f"(0.5 = no signal, 1.0 = perfect)")
    print(f"estimate agrees with department: {result['correct']} "
          f"({100.0 * result['agreement']:.0f}%)")
    print(f"estimate got the sign backwards: {result['wrong_sign']}")
    print("\nconfusion (department verdict -> estimate verdict):")
    for (truth, predicted), count in sorted(result["matrix"].items()):
        print(f"    {truth:10} -> {predicted:10} {count:>4}")
    print(f"\nWrote {OUTPUT_CSV.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
