from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

from ..config import Config
from ..models import Item
from ..state import State


@dataclass
class SourceContext:
    client: httpx.Client
    cfg: Config
    since: datetime
    now: datetime
    week: str
    state: State


class PartialFailure(Exception):
    """Some sub-sources failed; carries the items that did load."""

    def __init__(self, items: list[Item], failures: list[str]):
        super().__init__("; ".join(failures))
        self.items = items


Fetcher = Callable[[SourceContext], list[Item]]


def registry() -> dict[str, Fetcher]:
    from . import arxiv, github, hf, isca, rss

    return {
        "arxiv": arxiv.fetch,
        "hf_papers": hf.fetch_papers,
        "hf_models": hf.fetch_models,
        "github": github.fetch,
        "rss": rss.fetch,
        "isca": isca.fetch,
    }
