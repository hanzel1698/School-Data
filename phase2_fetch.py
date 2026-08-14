#!/usr/bin/env python3
"""Phase 2 - fetch one detail page per working-set school.

Cache-first and resumable: every response body is written to
data/cache/{school_code}.html *before* anything parses it, and a school already
in cache is never re-requested. Killing and restarting this script costs no
extra requests, so the Phase 3 parser can be iterated on freely.

Provenance (url, fetched_at, status) is appended to data/raw/fetch_manifest.jsonl,
which is committed - data/cache/ itself is gitignored.

    python phase2_fetch.py            # fetch what's missing
    python phase2_fetch.py --dry-run  # report what would be fetched
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scraper.config import Config, load_config
from scraper.fetcher import RateLimitedFetcher

PROGRESS_EVERY = 25


def load_working_set(config: Config) -> list[dict[str, object]]:
    source = config.path("raw") / f"{config.district_name.lower()}_schools.jsonl"
    if not source.exists():
        raise FileNotFoundError(f"{source} missing - run phase1_enumerate.py first")

    schools: list[dict[str, object]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("in_working_set"):
                schools.append(record)
    return schools


def cache_path(config: Config, school_code: str) -> Path:
    return config.path("cache") / f"{school_code}.html"


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    config = load_config()
    schools = load_working_set(config)
    manifest = config.path("raw") / "fetch_manifest.jsonl"

    pending = [s for s in schools if not cache_path(config, str(s["school_code"])).exists()]
    cached = len(schools) - len(pending)

    print(f"Working set:    {len(schools)}")
    print(f"Already cached: {cached}  (will be skipped, 0 requests)")
    print(f"To fetch:       {len(pending)}")
    estimate_s = len(pending) * config.http.delay_seconds
    print(f"Estimated time: {estimate_s / 60:.1f} min at {config.http.delay_seconds}s/request\n")

    if dry_run or not pending:
        return 0

    failures: list[tuple[str, str]] = []

    with RateLimitedFetcher(config, verbose=False) as fetcher:
        fetcher.logger.info("Phase 2 start: %d to fetch, %d cached", len(pending), cached)

        with manifest.open("a", encoding="utf-8", newline="\n") as manifest_handle:
            for index, school in enumerate(pending, start=1):
                code = str(school["school_code"])
                url = config.url("school_detail", school_code=code)
                result = fetcher.get(url)
                fetched_at = datetime.now(timezone.utc).isoformat()

                if result.ok:
                    # Write the body before any parsing touches it.
                    cache_path(config, code).write_text(result.text, encoding="utf-8")
                else:
                    failures.append((code, result.reason))
                    fetcher.logger.error(
                        "school %s not cached: %s", code, result.reason
                    )

                manifest_handle.write(
                    json.dumps(
                        {
                            "school_code": code,
                            "source_url": url,
                            "fetched_at": fetched_at,
                            "status_code": result.status_code,
                            "ok": result.ok,
                            "reason": result.reason,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                manifest_handle.flush()

                if index % PROGRESS_EVERY == 0 or index == len(pending):
                    remaining = (len(pending) - index) * config.http.delay_seconds / 60
                    print(
                        f"  {index}/{len(pending)} fetched "
                        f"({len(failures)} failed, ~{remaining:.1f} min left)",
                        flush=True,
                    )

    print(f"\nDone. {len(pending) - len(failures)} cached, {len(failures)} failed.")
    if failures:
        print("Failures (logged, not fatal):")
        for code, reason in failures[:20]:
            print(f"  {code}: {reason}")
        print("Re-run this script to retry them; cached schools will be skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
