#!/usr/bin/env python3
"""Dump the raw markup of the 'Staff Details' table from a saved sample.

Offline. Used to work out exactly how designation/count pairs are encoded
before committing to a parser.
"""

from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup

SAMPLES = Path(__file__).resolve().parent / "data" / "samples"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <school_code>", file=sys.stderr)
        return 64

    path = SAMPLES / f"school_{argv[1]}.html"
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")

    staff_tables = [
        t for t in soup.find_all("table")
        if "staff details" in t.get_text(" ", strip=True).lower()[:200]
    ]
    print(f"{path.name}: {len(staff_tables)} table(s) whose head mentions 'Staff Details'\n")

    for idx, table in enumerate(staff_tables):
        print(f"{'=' * 70}\nSTAFF TABLE [{idx}] raw markup\n{'=' * 70}")
        print(table.prettify()[:6000])

        print(f"\n--- anchors in staff table[{idx}] ---")
        for anchor in table.find_all("a")[:40]:
            print(f"  text={anchor.get_text(' ', strip=True)!r}")
            print(f"    href={anchor.get('href')!r} onclick={anchor.get('onclick')!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
