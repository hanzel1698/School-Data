#!/usr/bin/env python3
"""Phase 0 - discovery and audit. Read-only, no bulk requests.

Runs in stages so each answer can be inspected before the next request is made:

    python phase0_discover.py robots     # robots.txt - the gate
    python phase0_discover.py landscape  # home, advanced search, district probes
    python phase0_discover.py schools    # three school detail pages

Every response body is saved verbatim under data/samples/ before anything is
parsed, so the parser can be iterated on without re-hitting the server.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.robotparser import RobotFileParser

from scraper.config import load_config
from scraper.fetcher import FetchResult, RateLimitedFetcher


def save_sample(directory: Path, name: str, result: FetchResult) -> Path:
    suffix = ".json" if result.is_json else ".html" if result.is_html else ".txt"
    target = directory / f"{name}{suffix}"
    target.write_text(result.text, encoding="utf-8")
    return target


def stage_robots() -> int:
    """Fetch and interpret robots.txt. Returns a shell exit code."""
    config = load_config()
    samples = config.path("samples")

    with RateLimitedFetcher(config) as fetcher:
        url = config.url("robots")
        result = fetcher.get(url)

        if result.status_code == 404:
            print("\nrobots.txt: HTTP 404 - no robots.txt published.")
            print("Interpretation: nothing is disallowed; crawl is permitted.")
            save_sample(samples, "robots_404", result)
            return 0

        if not result.ok:
            print(f"\nrobots.txt: FAILED ({result.reason}). Treat as blocking; stop.")
            return 1

        path = save_sample(samples, "robots", result)
        print(f"\nrobots.txt saved to {path}\n")
        print("--- verbatim ---")
        print(result.text.strip() or "(empty body)")
        print("--- end ---\n")

        parser = RobotFileParser()
        parser.parse(result.text.splitlines())

        agent = config.http.user_agent
        probes = [
            "/",
            f"/publicView/schoolsLists/all/dist/{config.district_id}/1",
            "/18232",
            "/search/advanced_search_interface",
        ]
        print("Path permission check for our User-Agent:")
        blocked = False
        for probe in probes:
            allowed = parser.can_fetch(agent, config.base_url.rstrip("/") + probe)
            blocked = blocked or not allowed
            print(f"  {'ALLOW' if allowed else 'DISALLOW':9s} {probe}")

        delay = parser.crawl_delay(agent)
        print(f"\nDeclared Crawl-delay: {delay if delay is not None else 'none'}")
        print(f"Our configured delay: {config.http.delay_seconds}s")

        if blocked:
            print("\nAt least one required path is disallowed. STOP - report back.")
            return 2
        print("\nAll required paths allowed.")
        return 0


def _describe_html(label: str, result: FetchResult) -> None:
    """Print structural facts that decide server-rendered vs client-hydrated."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(result.text, "html.parser")
    tables = soup.find_all("table")
    scripts = soup.find_all("script")
    script_src = [s.get("src", "") for s in scripts if s.get("src")]
    inline_js = "\n".join(s.get_text() for s in scripts if not s.get("src"))

    print(f"\n=== {label} ===")
    print(f"  HTTP {result.status_code}, {len(result.text)} chars, {result.content_type}")
    title = soup.find("title")
    print(f"  <title>: {title.get_text(strip=True) if title else '(none)'}")

    heading = next(
        (
            h.get_text(" ", strip=True)
            for h in soup.find_all(["h1", "h2", "h3", "h4"])
            if h.get_text(strip=True)
        ),
        "(none)",
    )
    print(f"  first heading: {heading[:120]}")
    print(f"  <table> count: {len(tables)}")
    for idx, table in enumerate(tables[:4]):
        rows = table.find_all("tr")
        print(f"    table[{idx}]: {len(rows)} <tr>")
    print(f"  <script src> count: {len(script_src)}")
    for src in script_src[:12]:
        print(f"    - {src}")

    markers = {
        "DataTable": "DataTables (client-side paging of a fully rendered table)",
        "ajax": "ajax call in inline JS",
        "$.get": "jQuery GET in inline JS",
        "$.post": "jQuery POST in inline JS",
        "fetch(": "fetch() in inline JS",
        "XMLHttpRequest": "XHR in inline JS",
    }
    hits = [desc for token, desc in markers.items() if token.lower() in inline_js.lower()]
    print(f"  hydration markers: {', '.join(hits) if hits else 'none found'}")

    forms = soup.find_all("form")
    print(f"  <form> count: {len(forms)}")
    for form in forms[:4]:
        selects = form.find_all("select")
        print(
            f"    action={form.get('action', '')!r} method={form.get('method', '')!r} "
            f"selects={[s.get('name') for s in selects]}"
        )


def stage_landscape() -> int:
    """Home page, advanced search, and district-endpoint probes."""
    from bs4 import BeautifulSoup

    config = load_config()
    samples = config.path("samples")

    with RateLimitedFetcher(config) as fetcher:
        home = fetcher.get(config.base_url)
        save_sample(samples, "home", home)
        _describe_html("HOME /", home)

        adv = fetcher.get(config.url("advanced_search"))
        save_sample(samples, "advanced_search", adv)
        _describe_html("ADVANCED SEARCH /search/advanced_search_interface", adv)

        if adv.ok:
            soup = BeautifulSoup(adv.text, "html.parser")
            for select in soup.find_all("select"):
                name = select.get("name") or select.get("id") or "(unnamed)"
                options = [
                    (o.get("value", ""), o.get_text(strip=True))
                    for o in select.find_all("option")
                ]
                print(f"\n  <select name={name!r}> - {len(options)} options")
                for value, text in options[:20]:
                    print(f"      {value!r:8s} = {text}")
                if len(options) > 20:
                    print(f"      ... and {len(options) - 20} more")

        # Probe the endpoint shape the task spec listed as "confirmed", to see
        # whether it actually exists alongside the publicView route.
        spec_url = f"{config.base_url}/search/districtWiseSchools/{config.district_id}"
        spec_probe = fetcher.get(spec_url)
        print(
            f"\n=== SPEC-CLAIMED ROUTE /search/districtWiseSchools/{config.district_id} ==="
        )
        print(f"  HTTP {spec_probe.status_code} ok={spec_probe.ok} ({spec_probe.reason})")
        print(f"  {len(spec_probe.text)} chars")
        save_sample(samples, "probe_districtWiseSchools", spec_probe)

    return 0


SAMPLE_SCHOOLS: list[tuple[str, str]] = [
    ("18205", "Govt LP - GLPS Kuzhimanna (level 1 - 4)"),
    ("18232", "Govt UP - G U P S Cheecode (level 1 - 7)"),
    ("18150", "Govt HS with attached LP+UP - GHS Cheriyam Mankada (level 1 - 10)"),
]


def _dump_every_field(label: str, code: str, result: FetchResult) -> None:
    """Print the complete visible field inventory of a school detail page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(result.text, "html.parser")
    print(f"\n{'=' * 78}\n{label}  [/{code}]  HTTP {result.status_code}  {len(result.text)} chars\n{'=' * 78}")

    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        htext = heading.get_text(" ", strip=True)
        if htext and htext not in {"Related Links", "Contact No"}:
            print(f"  HEADING: {htext[:120]}")

    for idx, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        caption = table.find("caption")
        print(f"\n  --- table[{idx}] class={table.get('class')!r} rows={len(rows)}"
              f"{' caption=' + caption.get_text(strip=True) if caption else ''}")
        for row in rows:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            cells = [c for c in cells if c != ""]
            if cells:
                print(f"      {cells}")


def stage_schools() -> int:
    """Fetch the three sample detail pages and dump their full field lists."""
    config = load_config()
    samples = config.path("samples")

    with RateLimitedFetcher(config) as fetcher:
        for code, label in SAMPLE_SCHOOLS:
            result = fetcher.get(config.url("school_detail", school_code=code))
            save_sample(samples, f"school_{code}", result)
            if not result.ok:
                print(f"\n[!] {label} [/{code}] FAILED: {result.reason}")
                continue
            _dump_every_field(label, code, result)

    return 0


EXTRA_SCHOOLS: list[tuple[str, str]] = [
    ("18010", "Govt VHSS - G.V.H.S.S. Pullanur (level 1 - 12, LP+UP+HS+HSS+VHSE)"),
    ("18023", "Govt HSS - G.G.H.S.S. Manjeri (level 1 - 12)"),
    ("18501", "Govt HS only - Technical High School Manjeri (level 8 - 10, no primary)"),
]


def stage_extra() -> int:
    """Fetch multi-section schools to see whether extra staff tables appear."""
    config = load_config()
    samples = config.path("samples")

    with RateLimitedFetcher(config) as fetcher:
        for code, label in EXTRA_SCHOOLS:
            result = fetcher.get(config.url("school_detail", school_code=code))
            save_sample(samples, f"school_{code}", result)
            if not result.ok:
                print(f"\n[!] {label} [/{code}] FAILED: {result.reason}")
                continue
            _dump_every_field(label, code, result)

    return 0


STAGES = {
    "robots": stage_robots,
    "landscape": stage_landscape,
    "schools": stage_schools,
    "extra": stage_extra,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in STAGES:
        print(f"usage: {argv[0]} [{'|'.join(STAGES)}]", file=sys.stderr)
        return 64
    return STAGES[argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
