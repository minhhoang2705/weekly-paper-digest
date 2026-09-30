from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Kind = Literal["paper", "blog", "repo", "model"]
CRITERIA = ("novelty", "credibility", "technical", "impact", "evidence")


def title_key(title: str) -> str:
    """Normalized title used to merge the same work seen via different sources."""
    return re.sub(r"[^a-z0-9]+", "", title.lower())


@dataclass
class Item:
    id: str                      # stable identity, e.g. "arxiv:2509.01234", "gh:owner/repo"
    kind: Kind
    title: str
    url: str
    sources: list[str]
    published: datetime | None = None
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    pdf_url: str | None = None
    code_url: str | None = None
    signals: dict[str, int | str | bool] = field(default_factory=dict)

    # Filled by the LLM stages.
    topic: str | None = None
    promise: int = 0
    scores: dict[str, int] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    total: float = 0.0
    summary: dict | None = None
    fulltext_source: str | None = None
    fulltext: bool = False       # analysis (and thus ranking) read the full document

    @property
    def arxiv_id(self) -> str | None:
        return self.id.removeprefix("arxiv:") if self.id.startswith("arxiv:") else None

    def merge(self, other: Item) -> None:
        """Absorb metadata from a duplicate of the same work."""
        for s in other.sources:
            if s not in self.sources:
                self.sources.append(s)
        for k, v in other.signals.items():
            self.signals.setdefault(k, v)
        if len(other.abstract) > len(self.abstract):
            self.abstract = other.abstract
        self.authors = self.authors or other.authors
        self.pdf_url = self.pdf_url or other.pdf_url
        self.code_url = self.code_url or other.code_url
        self.published = self.published or other.published
