from __future__ import annotations

import math

from .models import CRITERIA, Item, title_key


def dedupe(items: list[Item]) -> list[Item]:
    """Merge the same work across sources: first by id, then by normalized title."""
    by_id: dict[str, Item] = {}
    for item in items:
        if item.id in by_id:
            by_id[item.id].merge(item)
        else:
            by_id[item.id] = item
    by_title: dict[str, Item] = {}
    for item in by_id.values():
        key = title_key(item.title)
        if key and key in by_title:
            keeper = by_title[key]
            # Prefer arXiv identity: it has a stable PDF and HF signals.
            if item.arxiv_id and not keeper.arxiv_id:
                item.merge(keeper)
                by_title[key] = item
            else:
                keeper.merge(item)
        else:
            by_title[key] = item
    return list(by_title.values())


def popularity(item: Item) -> float:
    """Log-scaled community signal, used only to break triage ties."""
    raw = sum(int(item.signals.get(k, 0) or 0) for k in ("hf_upvotes", "github_stars", "hf_likes"))
    return math.log1p(raw)


def shortlist(items: list[Item], size: int) -> list[Item]:
    ranked = sorted(items, key=lambda i: (i.promise, popularity(i)), reverse=True)
    return ranked[:size]


def weighted_total(scores: dict[str, int], weights: dict[str, float]) -> float:
    """Weighted mean of 1-5 criterion scores, mapped to 0-100."""
    wsum = sum(weights[c] for c in CRITERIA)
    mean = sum(weights[c] * scores[c] for c in CRITERIA) / wsum
    return round((mean - 1) / 4 * 100, 1)


def top_k(items: list[Item], k: int) -> list[Item]:
    scored = [i for i in items if i.scores]
    return sorted(scored, key=lambda i: (i.total, popularity(i)), reverse=True)[:k]
