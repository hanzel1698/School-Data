"""Rate-limited, resumable HTTP fetching against Sametham.

Design constraints this module enforces (from the task spec):

* One request every ``http.delay_seconds`` seconds, hard, process-wide.
  Single-threaded, no concurrency.
* Descriptive User-Agent with a contact address.
* Retry on 5xx and timeouts with exponential backoff, ``max_attempts`` total,
  then log and give up on that one URL rather than failing the whole run.
* Every request, status and skip reason goes to logs/scrape.log.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import Config

LOGGER_NAME = "sametham"

RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def configure_logging(config: Config, verbose: bool = True) -> logging.Logger:
    """Attach file (and optionally console) handlers to the package logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:  # idempotent across repeated calls in one process
        return logger

    log_path: Path = config.path("log_file")
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if verbose:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console)

    return logger


@dataclass
class FetchResult:
    """Outcome of a fetch attempt. ``ok`` is False for give-up cases."""

    url: str
    ok: bool
    status_code: int | None
    text: str
    content_type: str
    reason: str = ""

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type.lower()

    @property
    def is_json(self) -> bool:
        return "json" in self.content_type.lower()


class RateLimitedFetcher:
    """A single-threaded httpx client that never exceeds the configured rate.

    The delay is applied *between* requests based on a monotonic clock, so time
    spent parsing counts toward the interval rather than being added to it.
    """

    def __init__(self, config: Config, verbose: bool = True) -> None:
        self.config = config
        self.logger = configure_logging(config, verbose=verbose)
        self._last_request_at: float | None = None
        self._request_count = 0
        self._client = httpx.Client(
            headers={
                "User-Agent": config.http.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9",
            },
            timeout=config.http.timeout_seconds,
            follow_redirects=True,
        )

    def __enter__(self) -> "RateLimitedFetcher":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()
        self.logger.info("Fetcher closed after %d request(s).", self._request_count)

    @property
    def request_count(self) -> int:
        return self._request_count

    def _throttle(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.config.http.delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def get(self, url: str) -> FetchResult:
        """GET a URL, honouring the rate limit and retry policy."""
        max_attempts = self.config.http.max_attempts

        for attempt in range(1, max_attempts + 1):
            self._throttle()
            self._last_request_at = time.monotonic()
            self._request_count += 1

            try:
                response = self._client.get(url)
            except RETRYABLE_EXCEPTIONS as exc:
                reason = f"{type(exc).__name__}: {exc}"
                self.logger.warning(
                    "GET %s attempt %d/%d failed: %s", url, attempt, max_attempts, reason
                )
                if attempt == max_attempts:
                    self.logger.error("GET %s giving up: %s", url, reason)
                    return FetchResult(url, False, None, "", "", reason)
                self._backoff(attempt)
                continue
            except httpx.HTTPError as exc:  # non-retryable client-side error
                reason = f"{type(exc).__name__}: {exc}"
                self.logger.error("GET %s non-retryable failure: %s", url, reason)
                return FetchResult(url, False, None, "", "", reason)

            status = response.status_code
            content_type = response.headers.get("content-type", "")
            self.logger.info(
                "GET %s -> %d (%d bytes, %s)",
                url,
                status,
                len(response.content),
                content_type or "no content-type",
            )

            if status >= 500:
                if attempt == max_attempts:
                    self.logger.error("GET %s giving up after HTTP %d", url, status)
                    return FetchResult(
                        url, False, status, "", content_type, f"HTTP {status}"
                    )
                self._backoff(attempt)
                continue

            if status >= 400:
                # 4xx is a real answer about this URL; retrying will not help.
                self.logger.warning("GET %s client error HTTP %d", url, status)
                return FetchResult(
                    url, False, status, response.text, content_type, f"HTTP {status}"
                )

            return FetchResult(url, True, status, response.text, content_type)

        # Unreachable: the loop either returns or continues to exhaustion above.
        raise RuntimeError(f"retry loop fell through for {url}")

    def _backoff(self, attempt: int) -> None:
        delay = self.config.http.backoff_base**attempt
        self.logger.info("Backing off %.1fs before retry", delay)
        time.sleep(delay)
