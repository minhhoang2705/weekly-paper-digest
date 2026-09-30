from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import Item, title_key


@dataclass
class State:
    """What earlier digests already published, and which ISCA volumes were scanned.

    Committed to the repo by the workflow so weekly runs never repeat an item.
    """

    path: Path
    seen: dict[str, str] = field(default_factory=dict)          # item id / title key -> digest week
    isca_volumes: dict[str, str] | None = None                  # volume -> week scanned; None: first run
    scanned_isca: dict[str, str] = field(default_factory=dict)  # this run; persisted on save

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls(path=path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(path=path, seen=raw.get("seen", {}), isca_volumes=raw.get("isca_volumes"))

    def is_seen(self, item: Item, current_week: str) -> bool:
        """Published in an EARLIER digest; re-running the same week reproduces its picks."""
        keys = (item.id, f"title:{title_key(item.title)}")
        return any(self.seen.get(k, current_week) != current_week for k in keys)

    def mark_published(self, items: list[Item], week: str) -> None:
        for item in items:
            self.seen[item.id] = week
            self.seen[f"title:{title_key(item.title)}"] = week

    def save(self) -> None:
        volumes = {**(self.isca_volumes or {}), **self.scanned_isca}
        payload = {"seen": dict(sorted(self.seen.items())), "isca_volumes": dict(sorted(volumes.items()))}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
