#!/usr/bin/env python3
"""Offline inspection of files already saved under data/samples/.

Makes no network requests - this exists so parser questions can be answered
without re-hitting the server.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

SAMPLES = Path(__file__).resolve().parent / "data" / "samples"


def show_ajax_urls(filename: str) -> None:
    text = (SAMPLES / filename).read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "html.parser")
    inline = "\n".join(s.get_text() for s in soup.find_all("script") if not s.get("src"))
    urls = sorted(set(re.findall(r"""url\s*:\s*["']([^"']+)["']""", inline)))
    print(f"\n=== ajax url: targets in {filename} ===")
    for url in urls:
        print(f"  {url}")
    base_vars = sorted(set(re.findall(r"""(?:var|let|const)\s+(\w*[Uu]rl\w*)\s*=\s*["']([^"']+)["']""", inline)))
    for name, value in base_vars:
        print(f"  {name} = {value}")


def show_table_shape(filename: str, max_tables: int = 6) -> None:
    text = (SAMPLES / filename).read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "html.parser")
    tables = soup.find_all("table")
    print(f"\n=== tables in {filename} ({len(text)} chars, {len(tables)} tables) ===")

    title = soup.find("title")
    print(f"  <title>: {title.get_text(strip=True) if title else '(none)'}")
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        htext = heading.get_text(" ", strip=True)
        if htext:
            print(f"  heading: {htext[:140]}")

    for idx, table in enumerate(tables[:max_tables]):
        rows = table.find_all("tr")
        print(f"\n  --- table[{idx}] id={table.get('id')!r} class={table.get('class')!r}: {len(rows)} rows")
        for row in rows[:3]:
            cells = [c.get_text(" ", strip=True)[:34] for c in row.find_all(["td", "th"])]
            print(f"      {cells}")
        if len(rows) > 3:
            last = rows[-1].find_all(["td", "th"])
            print(f"      ... last row: {[c.get_text(' ', strip=True)[:34] for c in last]}")


def show_pagination(filename: str) -> None:
    text = (SAMPLES / filename).read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "html.parser")
    print(f"\n=== pagination signals in {filename} ===")
    pagers = soup.find_all(class_=re.compile(r"pag", re.I))
    print(f"  elements with class matching /pag/i: {len(pagers)}")
    for pager in pagers[:5]:
        print(f"    <{pager.name} class={pager.get('class')}>: {pager.get_text(' ', strip=True)[:160]}")
    inline = "\n".join(s.get_text() for s in soup.find_all("script") if not s.get("src"))
    for token in ("DataTable", "pageLength", "paging", "lengthMenu", "serverSide"):
        if token.lower() in inline.lower():
            for match in re.findall(rf".{{0,70}}{re.escape(token)}.{{0,70}}", inline, re.I)[:3]:
                print(f"    [{token}] ...{' '.join(match.split())}...")


COMMANDS = {
    "ajax": show_ajax_urls,
    "tables": show_table_shape,
    "paging": show_pagination,
}


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in COMMANDS:
        print(f"usage: {argv[0]} [{'|'.join(COMMANDS)}] <sample-filename>", file=sys.stderr)
        return 64
    COMMANDS[argv[1]](argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
