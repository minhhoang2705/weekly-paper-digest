from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone

import feedparser

from ..models import Item
from . import PartialFailure, SourceContext

TAG_RE = re.compile(r"<[^>]+>")


def _published(e) -> datetime | None:
    t = e.get("published_parsed") or e.get("updated_parsed")
    return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc) if t else None


def fetch(ctx: SourceContext) -> list[Item]:
    """Blog/news posts from configured feeds; one broken feed must not sink the rest."""
    src = ctx.cfg.source("rss")
    items: list[Item] = []
    failures: list[str] = []
    for name, url in src["feeds"].items():
        try:
            resp = ctx.client.get(url)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            failures.append(f"{name}: {type(exc).__name__}")
            continue
        for e in feedparser.parse(resp.content).entries:
            published = _published(e)
            link = e.get("link")
            if not link or published is None or published < ctx.since:
                continue
            summary = TAG_RE.sub(" ", e.get("summary", ""))
            items.append(Item(
                id=f"url:{link.split('?')[0].rstrip('/')}",
                kind="blog",
                title=" ".join(e.get("title", "").split()),
                url=link,
                sources=[name],
                published=published,
                authors=[a.get("name") for a in e.get("authors", []) if a.get("name")] or [name],
                abstract=" ".join(summary.split())[:2000],
                signals={"publisher": name},
            ))
    if failures:
        raise PartialFailure(items, failures)
    return items
