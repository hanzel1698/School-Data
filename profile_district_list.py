#!/usr/bin/env python3
"""Offline profile of the saved district-wide school list sample.

Answers: how many schools, what section/management/level values exist, and
which school codes make good Phase 0 detail-page samples. No network access.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

SAMPLE = Path(__file__).resolve().parent / "data" / "samples" / "probe_districtWiseSchools.html"

HEADER_TOKENS = {"#", "School Code", "School Name"}


def main() -> int:
    soup = BeautifulSoup(SAMPLE.read_text(encoding="utf-8"), "html.parser")
    table = soup.find("table")
    rows = table.find_all("tr")

    schools: list[dict[str, str]] = []
    for row in rows:
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) < 12:
            continue
        if HEADER_TOKENS & set(cells):
            continue

        raw_code = cells[1]
        section, _, code = raw_code.partition(":")
        schools.append(
            {
                "section": section.strip() if code else "",
                "code": (code or raw_code).strip(),
                "name": cells[2],
                "block": cells[3],
                "local_body": cells[4],
                "finance_type": cells[7],
                "level": cells[8],
            }
        )

    print(f"Parsed {len(schools)} school rows\n")

    for field in ("section", "finance_type", "level"):
        print(f"--- {field} ---")
        for value, count in Counter(s[field] for s in schools).most_common():
            print(f"  {count:5d}  {value!r}")
        print()

    print("--- section x finance_type ---")
    cross = Counter((s["section"], s["finance_type"]) for s in schools)
    for (section, finance), count in sorted(cross.items()):
        print(f"  {count:5d}  {section:4s} | {finance}")
    print()

    print("--- section x level (Government only) ---")
    govt = [s for s in schools if s["finance_type"] == "Government"]
    print(f"  Government schools: {len(govt)}")
    for (section, level), count in sorted(
        Counter((s["section"], s["level"]) for s in govt).items()
    ):
        print(f"  {count:5d}  {section:4s} | {level}")
    print()

    print("--- candidate Phase 0 detail samples (Government) ---")
    wanted = [
        ("LP", "1 - 4", "Govt LP school"),
        ("UP", "1 - 7", "Govt UP school with LP section"),
        ("HS", "1 -10", "Govt HS with attached LP+UP sections"),
        ("HS", "8 - 10", "Govt HS, no primary section"),
        ("HSS", "1 - 12", "Govt HSS with attached LP+UP sections"),
        ("UP", "5 - 7", "Govt UP standalone, no LP"),
    ]
    for section, level, label in wanted:
        match = next(
            (s for s in govt if s["section"] == section and s["level"] == level), None
        )
        if match:
            print(f"  {label:42s} -> {match['code']:8s} {match['name'][:40]} [{match['level']}]")
        else:
            print(f"  {label:42s} -> (none found with section={section} level={level})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
