from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import CRITERIA


@dataclass
class Config:
    lookback_days: int
    top_k: int
    shortlist_size: int
    language: str
    models: dict[str, str]
    weights: dict[str, float]
    topics: dict[str, str]
    keywords: list[str]
    sources: dict[str, dict[str, Any]]

    def source(self, name: str) -> dict[str, Any] | None:
        """Source settings, or None when disabled."""
        cfg = self.sources.get(name) or {}
        return cfg if cfg.get("enabled", False) else None

    def keyword_regex(self) -> re.Pattern[str]:
        alts = "|".join(re.escape(k) for k in self.keywords)
        return re.compile(rf"(?<![a-z0-9])(?:{alts})(?![a-z0-9])", re.IGNORECASE)


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg = Config(**raw)
    missing = set(CRITERIA) - set(cfg.weights)
    if missing:
        raise ValueError(f"config.weights missing criteria: {sorted(missing)}")
    if cfg.top_k > cfg.shortlist_size:
        raise ValueError("top_k must be <= shortlist_size")
    return cfg
