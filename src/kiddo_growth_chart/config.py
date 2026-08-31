"""Runtime configuration. The app knows nothing until it is pointed at something."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ENV_CONFIG = "KIDDO_CONFIG"


@dataclass(slots=True)
class Config:
    dataset: str | None = None          # path; None -> $KIDDO_DATASET -> sample
    provider: str = "none"
    provider_options: dict = field(default_factory=dict)
    units: str = "imperial"             # "imperial" | "metric" -- display only
    show_percentile_bands: bool = False  # off by default, deliberately

    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "Config":
        path = path or os.environ.get(ENV_CONFIG)
        if not path:
            return cls()
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__slots__}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**raw)
