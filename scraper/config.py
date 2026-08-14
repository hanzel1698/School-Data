"""Configuration loading for the Sametham scraper.

Every tunable (base URL, district id, delay, paths) lives in config.yaml at the
repo root; nothing here hardcodes a literal that the operator might want to
change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH: Path = REPO_ROOT / "config.yaml"


@dataclass(frozen=True)
class HttpConfig:
    delay_seconds: float
    timeout_seconds: float
    max_attempts: int
    backoff_base: float
    user_agent: str


@dataclass(frozen=True)
class Config:
    base_url: str
    district_id: int
    district_name: str
    finance_types: dict[str, str]
    working_management: list[str]
    comparison_management: list[str]
    skip_if_lowest_class_at_least: int
    endpoints: dict[str, str]
    http: HttpConfig
    paths: dict[str, Path]

    def url(self, endpoint_key: str, **params: Any) -> str:
        """Build an absolute URL for a named endpoint from config.yaml."""
        try:
            template = self.endpoints[endpoint_key]
        except KeyError as exc:
            raise KeyError(
                f"No endpoint {endpoint_key!r} in config.yaml; "
                f"known: {sorted(self.endpoints)}"
            ) from exc
        return self.base_url.rstrip("/") + template.format(**params)

    def path(self, key: str) -> Path:
        """Absolute path for a named directory, created if missing."""
        target = self.paths[key]
        if target.suffix:
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target.mkdir(parents=True, exist_ok=True)
        return target


def load_config(config_path: Path | None = None) -> Config:
    path = config_path or DEFAULT_CONFIG_PATH
    with path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)

    http_raw: dict[str, Any] = raw["http"]
    paths_raw: dict[str, str] = raw["paths"]

    return Config(
        base_url=raw["base_url"],
        district_id=int(raw["district"]["id"]),
        district_name=raw["district"]["name"],
        finance_types=dict(raw["finance_types"]),
        working_management=list(raw["working_management"]),
        comparison_management=list(raw["comparison_management"] or []),
        skip_if_lowest_class_at_least=int(
            raw["working_set"]["skip_if_lowest_class_at_least"]
        ),
        endpoints=dict(raw["endpoints"]),
        http=HttpConfig(
            delay_seconds=float(http_raw["delay_seconds"]),
            timeout_seconds=float(http_raw["timeout_seconds"]),
            max_attempts=int(http_raw["max_attempts"]),
            backoff_base=float(http_raw["backoff_base"]),
            user_agent=" ".join(str(http_raw["user_agent"]).split()),
        ),
        paths={key: REPO_ROOT / value for key, value in paths_raw.items()},
    )
