"""Structured per-week run data (data/YYYY-Www.json): the source of truth for the web UI."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .config import Config
from .models import Item


def save_run(
    path: Path,
    cfg: Config,
    week: str,
    since: datetime,
    now: datetime,
    scored: list[Item],
    top: list[Item],
    stats: dict[str, int],
    warnings: list[str],
) -> None:
    ranks = {item.id: n for n, item in enumerate(top, 1)}
    items = []
    for item in sorted(scored, key=lambda i: (ranks.get(i.id, 10**6), -i.total)):
        row = asdict(item)
        row["published"] = item.published.isoformat() if item.published else None
        row["rank"] = ranks.get(item.id)
        items.append(row)
    payload = {
        "week": week,
        "generated_at": now.isoformat(),
        "since": since.isoformat(),
        "weights": cfg.weights,
        "models": cfg.models,
        "stats": stats,
        "warnings": warnings,
        "items": items,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_runs(data_dir: Path) -> list[dict]:
    """All runs, newest week first."""
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in data_dir.glob("*-W*.json")]
    return sorted(runs, key=lambda r: r["week"], reverse=True)
