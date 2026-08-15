#!/usr/bin/env python3
"""
Date Sametham's staff data by testing it against a redeployment of known date.

output/phase0_findings.md section 7 established that Sametham publishes no
update date for staff: the homepage "Data updated on" stamp covers only the
school and student panels, HTTP Last-modified is a page-cache build time, and
no per-record timestamp exists anywhere. The recommendation there was to
measure the currency externally instead. This does that.

The probe: order No. DDEMPM/7383/2026-A4 dated 14.07.2026 moved 91 named LPST
and UPST teachers between named Malappuram schools, with relieving and joining
both on 15.07.2026. Every one of those teachers is a dated, checkable fact
about who should appear on which school's Sametham roster. If the moves are
absent, Sametham's staff data predates 15.07.2026.

Sampled rather than exhaustive, deliberately. Confirming all 91 would mean
fetching roughly 180 school rosters, and the answer does not change after the
first few. The cases below were picked to spread across sub-districts, school
types and both post categories, and include two schools flagged by
udise_crosscheck.py as having implausibly few LP/UP staff.

On personal data: the teachers' names are already public in the order itself.
The rosters fetched here name other staff who are not, so they are cached
outside the repository (data/cache_rosters/, git-ignored) and only the
per-case verdict is written to output. Nothing beyond the eight sampled names
is recorded.

Usage:
    python check_sametham_currency.py
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent
CACHE_DIR = REPO_ROOT / "data/cache_rosters"
RESULT_JSON = REPO_ROOT / "data/processed/sametham_currency_cases.json"

BASE_URL = "https://sametham.kite.kerala.gov.in"
USER_AGENT = (
    "sametham-staffing-research/0.1 (Malappuram LP/UP teacher staffing study; "
    "contact: hanzel.h.fernandez@gmail.com)"
)
DELAY_SECONDS = 2.0

# (serial in the order, name as printed there, post, origin code, destination code)
CASES = [
    (1,  "SHEENA.KP",                        "LPST", "48049", "18525"),
    (3,  "DEEPU P B",                        "UPST", "48100", "48077"),
    (7,  "RASHIDA CHELLAPPURATH VADAKKANIL", "UPST", "18373", "19859"),
    (8,  "SAKKEENA BAHJATP H",               "UPST", "18384", "18375"),
    (9,  "ANU P",                            "UPST", "18384", "18375"),
    (10, "SABIRA KOPPILAN",                  "LPST", "18302", "18318"),
    (12, "LIVYA L V",                        "UPST", "18380", "18072"),
    (65, "JAMSHIYA.M",                       "LPST", "48406", "48419"),
]

_last_request_at = [0.0]


def _get(client: httpx.Client, url: str) -> str:
    remaining = DELAY_SECONDS - (time.monotonic() - _last_request_at[0])
    if remaining > 0:
        time.sleep(remaining)
    _last_request_at[0] = time.monotonic()
    response = client.get(url)
    response.raise_for_status()
    return response.text


def roster(school_code: str) -> dict[str, list[list[str]]]:
    """Every named employee at a school, by post code. Cached on disk."""
    cached = CACHE_DIR / f"{school_code}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=40.0, follow_redirects=True
    ) as client:
        page = _get(client, f"{BASE_URL}/{school_code}")
        posts = sorted(set(re.findall(
            rf"/publicView/employees/{school_code}/16B/(\d+)", page
        )))
        out: dict[str, list[list[str]]] = {}
        for post in posts:
            markup = _get(
                client, f"{BASE_URL}/publicView/employees/{school_code}/16B/{post}"
            )
            table = re.search(r"(?is)Employee Details.*?</table>", markup)
            cells = re.findall(r"(?is)<td[^>]*>(.*?)</td>", table.group(0) if table else "")
            cells = [
                re.sub(r"\s+", " ", html.unescape(re.sub(r"(?is)<[^>]+>", " ", c))).strip()
                for c in cells
            ]
            # Rows are (serial, name, designation).
            out[post] = [
                [cells[i + 1], cells[i + 2]]
                for i in range(0, len(cells) - 2, 3)
                if cells[i].isdigit()
            ]

    cached.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^A-Za-z]+", name.upper()) if len(t) > 2]


def same_person(printed: str, listed: str) -> bool:
    """Match across spelling drift between the order and Sametham.

    The two sources transliterate differently - the order's SAKKEENA BAHJATP H
    is Sametham's SAKEENA BAHJATH P - so this matches on token overlap with a
    five-character prefix, allowing one token to differ.
    """
    left, right = _tokens(printed), _tokens(listed)
    if not left or not right:
        return False
    hits = 0
    for token in left:
        for other in right:
            if token == other or (
                len(token) > 4 and len(other) > 4
                and (token.startswith(other[:5]) or other.startswith(token[:5]))
            ):
                hits += 1
                break
    return hits >= max(1, min(len(left), len(right)) - 1)


def listed_at(school_code: str, name: str) -> tuple[list[str], int]:
    names = [n for entries in roster(school_code).values() for n, _ in entries]
    return [n for n in names if same_person(name, n)], len(names)


def main() -> int:
    results = []
    for serial, name, post, origin, destination in CASES:
        at_origin, origin_size = listed_at(origin, name)
        at_destination, destination_size = listed_at(destination, name)
        results.append({
            "sl": serial, "name_in_order": name, "post": post,
            "origin_code": origin, "origin_staff": origin_size,
            "still_at_origin": bool(at_origin), "origin_match": at_origin,
            "destination_code": destination, "destination_staff": destination_size,
            "at_destination": bool(at_destination), "destination_match": at_destination,
        })
        print(
            f"{serial:3} {name[:33]:33} {post}  "
            f"origin {origin}: {'listed as ' + at_origin[0] if at_origin else 'absent':<38} "
            f"destination {destination}: {'listed as ' + at_destination[0] if at_destination else 'absent'}"
        )

    still = sum(1 for r in results if r["still_at_origin"])
    arrived = sum(1 for r in results if r["at_destination"])
    both = sum(1 for r in results if r["at_destination"] and r["still_at_origin"])

    RESULT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.write_text(json.dumps(results, indent=1), encoding="utf-8")

    print()
    print(f"cases                                : {len(results)}")
    print(f"still listed at the school they left : {still}")
    print(f"listed at the school they joined     : {arrived} "
          f"({both} of those also still at the origin, so not evidence of a move)")
    print(f"\nWrote {RESULT_JSON.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
