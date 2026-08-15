#!/usr/bin/env python3
"""
Parse the DDE Malappuram 2026-27 LPST/UPST redeployment order into a CSV, and
join each school named in it to its Sametham school code.

Source: `data/sources/DEPLOYMENT_ORDER_2026-27_LPST_UPST_DDE_MPM.pdf`, order
No. DDEMPM/7383/2026-A4 dated 14.07.2026. It redeploys 91 named LPST and UPST
teachers out of schools that lost posts in the 2026-27 staff fixation and into
schools with posts available, with effect from 15.07.2026.

Why this matters to the rest of the project: it is the first source here that
speaks to *sanctioned* posts rather than filled ones, and it carries an
authoritative LPST/UPST split - the very distinction Sametham cannot make for
its LP/UP shared designations.

Extraction notes:

  * The order is a ruled table, so rows and columns are taken from the table's
    own drawn rules rather than guessed from text positions.
  * Words are assigned to a row by their vertical midpoint. Several cells are
    set in a slightly larger face that overhangs the rule above them, and
    banding on the top edge alone pulls those cells into the previous row.
  * A row split across a page boundary leaves its opening text in an unnumbered
    band at the foot of the earlier page. That band is carried forward and
    prepended to the first row of the next page (serial 25 is the only case).
  * On page 5 the rule separating serials 64 and 65 is not drawn at all, so the
    grid reports one band holding both. That split cannot be recovered from the
    geometry, so it is stated explicitly below; it is unambiguous against the
    Sametham school list, where all four schools exist separately.
  * Cells are joined at wrap points without a space, so a name carried across a
    page break can read "GLPSMARAVANCHERY". School matching runs on a
    whitespace-stripped form, so this does not affect the join.

Serial 61 has no PEN printed in the source. That is a gap in the order itself,
not a parse failure, and is left empty.

Usage:
    python parse_deployment_order.py
"""

from __future__ import annotations

import csv
import difflib
import json
import re
import sys
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parent
ORDER_PDF = REPO_ROOT / "data/sources/DEPLOYMENT_ORDER_2026-27_LPST_UPST_DDE_MPM.pdf"
SCHOOLS_JSONL = REPO_ROOT / "data/raw/malappuram_schools.jsonl"
OUTPUT_CSV = REPO_ROOT / "data/processed/malappuram_deployment_2026_27.csv"

COLUMNS = ["sl", "name", "pen", "post", "from", "to"]

# Keyed on the raw serial cell text, which wraps to "6465" for the merged band.
MERGED_BAND_OVERRIDE = {
    "6465": [
        # GUPS PULLIYIL = Pulliyil GUPS 48482, GUPS MYLADI = Myladi GUPS 48463
        {"sl": 64, "name": "SREEDEVI P", "pen": "1013101", "post": "UPST",
         "from": "GUPS PULLIYIL", "to": "GUPS MYLADI"},
        # GLPS CHOLAMUNDA = Cholamunda GLPS 48406, GLPS MAMANKARA = 48419
        {"sl": 65, "name": "JAMSHIYA.M", "pen": "977285", "post": "LPST",
         "from": "GLPS CHOLAMUNDA", "to": "GLPS MAMANKARA"},
    ]
}


def grid(page) -> tuple[list[int], list[int]]:
    """Row and column boundaries, read off the table's drawn rules."""
    horizontal: set[int] = set()
    vertical: set[int] = set()
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] != "re":
                continue
            rect = item[1]
            if rect.height < 2 and rect.width > 50:
                horizontal.add(round(rect.y0))
            if rect.width < 2 and rect.height > 10:
                vertical.add(round(rect.x0))

    def dedupe(values: set[int]) -> list[int]:
        out: list[int] = []
        for value in sorted(values):
            if not out or value - out[-1] > 3:
                out.append(value)
        return out

    return dedupe(horizontal), dedupe(vertical)


def cell_text(words) -> str:
    """Space between words on one line, nothing across a wrap."""
    lines: dict[int, list[tuple[float, str]]] = {}
    for x0, y0, _x1, _y1, text, *_ in words:
        lines.setdefault(round(y0 / 4), []).append((x0, text))
    joined = "".join(
        " ".join(text for _, text in sorted(lines[key])) for key in sorted(lines)
    )
    return re.sub(r"\s+", " ", joined).strip()


def parse_order(path: Path) -> list[dict]:
    doc = pymupdf.open(path)
    rows: list[dict] = []
    carried: dict | None = None  # opening text of a row split across a page break

    for page in doc:
        row_bounds, col_bounds = grid(page)
        if len(col_bounds) != 7 or len(row_bounds) < 2:
            continue  # prose page, no table on it
        words = page.get_text("words")
        bands = list(zip(row_bounds, row_bounds[1:]))

        for index, (top, bottom) in enumerate(bands):
            band = [w for w in words if top <= (w[1] + w[3]) / 2 < bottom]
            if not band:
                continue
            cells = [
                cell_text([w for w in band if left <= w[0] < right])
                for left, right in zip(col_bounds, col_bounds[1:])
            ]
            row = dict(zip(COLUMNS, cells))
            serial = row["sl"]

            if not serial.isdigit():
                # Only the last band on a page can be a row continuing overleaf;
                # an unnumbered band anywhere else is the column header.
                if index == len(bands) - 1 and any(
                    row[c] for c in ("name", "from", "to")
                ):
                    carried = row
                continue

            if serial in MERGED_BAND_OVERRIDE:
                rows.extend(MERGED_BAND_OVERRIDE[serial])
                continue
            if len(serial) > 3:
                raise RuntimeError(f"unhandled merged band {serial!r}: {row}")

            if carried is not None:
                for column in COLUMNS[1:]:
                    row[column] = (carried[column] + row[column]).strip()
                carried = None
            row["sl"] = int(serial)
            rows.append(row)

    return sorted(rows, key=lambda r: r["sl"])


def load_schools() -> dict[str, dict]:
    index: dict[str, dict] = {}
    with SCHOOLS_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            school = json.loads(line)
            index[normalise(school["school_name"])] = school
    return index


def normalise(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def resolve_school(name: str, index: dict[str, dict]) -> tuple[dict | None, str]:
    """Match an order's school name to a Sametham record.

    The order writes "GUPS MYLADI" where Sametham has "Myladi GUPS", so the
    school-type prefix is moved to the end before the second attempt.
    """
    key = normalise(name)
    if key in index:
        return index[key], "exact"

    candidates = [k for k in index if k.startswith(key) or key.startswith(k)]
    if len(candidates) == 1:
        return index[candidates[0]], "prefix"

    match = re.match(r"^([A-Z]*?(?:LPS|UPS|HSS|HS|VHSS|LP|UP))([A-Z].*)$", key)
    if match:
        reordered = match.group(2) + match.group(1)
        if reordered in index:
            return index[reordered], "reordered"
        candidates = [k for k in index if k.startswith(reordered)]
        if len(candidates) == 1:
            return index[candidates[0]], "reordered-prefix"

    close = difflib.get_close_matches(key, list(index), n=1, cutoff=0.86)
    if close:
        return index[close[0]], "fuzzy"
    return None, "unresolved"


def main() -> int:
    rows = parse_order(ORDER_PDF)
    serials = [r["sl"] for r in rows]
    gaps = sorted(set(range(1, max(serials) + 1)) - set(serials))
    if gaps or len(set(serials)) != len(serials):
        raise RuntimeError(f"serial numbering is not 1..{max(serials)}: gaps {gaps}")

    index = load_schools()
    unresolved: set[str] = set()

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "sl", "teacher_name", "pen", "post",
            "from_school_as_printed", "from_school_code", "from_school_name",
            "to_school_as_printed", "to_school_code", "to_school_name",
        ])
        for row in rows:
            source, _ = resolve_school(row["from"], index)
            target, _ = resolve_school(row["to"], index)
            for name, resolved in ((row["from"], source), (row["to"], target)):
                if resolved is None:
                    unresolved.add(name)
            writer.writerow([
                row["sl"], row["name"], row["pen"], row["post"],
                row["from"],
                source["school_code"] if source else "",
                source["school_name"] if source else "",
                row["to"],
                target["school_code"] if target else "",
                target["school_name"] if target else "",
            ])

    posts = {p: sum(1 for r in rows if r["post"] == p) for p in ("LPST", "UPST")}
    schools = {r["from"] for r in rows} | {r["to"] for r in rows}
    print(f"rows parsed              : {len(rows)} (serials 1-{max(serials)}, no gaps)")
    print(f"posts                    : LPST {posts['LPST']}, UPST {posts['UPST']}")
    print(f"PEN missing in the source: {[r['sl'] for r in rows if not r['pen']]}")
    print(f"distinct schools named   : {len(schools)}")
    print(f"resolved to a school code: {len(schools) - len(unresolved)}")
    if unresolved:
        print("unresolved school names  :")
        for name in sorted(unresolved):
            print(f"    {name}")
    print(f"\nWrote {OUTPUT_CSV.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
