#!/usr/bin/env python3
"""
Add a "Controlling Officer" column (AEO / DEO) to
schools_malappuram_sub_district.csv, derived from each school's Level Name.

Why this is derived and not scraped: Sametham publishes the educational
sub-district a school sits in, but no field for which officer controls it.
Under the Kerala Education Rules the educational sub-district is the AEO's
(Assistant Educational Officer) jurisdiction and the educational district is
the DEO's (District Educational Officer) - but the AEO controls LP and UP
schools only. A school with a high school section comes under the DEO
directly, even though Sametham still prints a sub-district name against it.

So the rule applied here is on the school's highest approved class:

    highest class <= 7   ->  AEO   (LP / UP school)
    highest class >= 8   ->  DEO   (has a high school section)

This is an administrative-structure inference, NOT data published by
Sametham. Anything load-bearing should be confirmed against a departmental
source. Rows whose Level Name cannot be parsed are left blank and reported
rather than guessed into a bucket.

The source CSV covers only schools starting at class 1, so every row here is
an LP-start school; the split is purely about where the school ends.

Usage:
    python add_controlling_officer_column.py
"""

import csv
import re

PATH = "schools_malappuram_sub_district.csv"
NEW_COLUMN = "Controlling Officer"
AFTER_COLUMN = "Level Name"


def highest_class(level_name):
    """Last integer in a "1 - 4" / "1 -10" / "1 to 12" level range."""
    numbers = re.findall(r"\d+", level_name)
    return int(numbers[-1]) if numbers else None


def controlling_officer(level_name):
    top = highest_class(level_name)
    if top is None:
        return ""
    return "AEO" if top <= 7 else "DEO"


def main():
    with open(PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    if NEW_COLUMN not in fieldnames:
        fieldnames.insert(fieldnames.index(AFTER_COLUMN) + 1, NEW_COLUMN)

    counts = {"AEO": 0, "DEO": 0, "": 0}
    for row in rows:
        officer = controlling_officer(row[AFTER_COLUMN])
        row[NEW_COLUMN] = officer
        counts[officer] += 1

    with open(PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {PATH}: "
          f"{counts['AEO']} AEO, {counts['DEO']} DEO.")
    if counts[""]:
        print(f"WARNING: {counts['']} row(s) had an unparseable "
              f"{AFTER_COLUMN} and were left blank.")


if __name__ == "__main__":
    main()
