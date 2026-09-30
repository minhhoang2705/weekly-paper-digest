from __future__ import annotations

import calendar
import re
import time
from datetime import datetime, timezone

import feedparser

from ..models import Item
from . import PartialFailure, SourceContext

API = "https://export.arxiv.org/api/query"
PAGE = 200
ABS_TERMS = ("speech", "spoken", "voice", "TTS", "ASR")
EMPTY_RETRIES = 2


def _query(categories: list[str], keyword_categories: list[str]) -> str:
    parts = [f"cat:{c}" for c in categories]
    if keyword_categories:
        cats = " OR ".join(f"cat:{c}" for c in keyword_categories)
        terms = " OR ".join(f"abs:{t}" for t in ABS_TERMS)
        parts.append(f"(({cats}) AND ({terms}))")
    return " OR ".join(parts)


def _entry_to_item(e) -> Item:
    arxiv_id = re.sub(r"v\d+$", "", e.id.rsplit("/abs/", 1)[-1])
    published = datetime.fromtimestamp(calendar.timegm(e.published_parsed), tz=timezone.utc)
    signals: dict = {"arxiv_category": e.get("arxiv_primary_category", {}).get("term", "")}
    comment = e.get("arxiv_comment")
    if comment:
        signals["arxiv_comment"] = " ".join(comment.split())
    return Item(
        id=f"arxiv:{arxiv_id}",
        kind="paper",
        title=" ".join(e.title.split()),
        url=f"https://arxiv.org/abs/{arxiv_id}",
        sources=["arXiv"],
        published=published,
        authors=[a.name for a in e.get("authors", [])],
        abstract=" ".join(e.summary.split()),
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
    )


def _page(ctx: SourceContext, query: str, start: int) -> list:
    """One result page. The export API intermittently returns an empty 200 feed, so retry."""
    for attempt in range(EMPTY_RETRIES + 1):
        time.sleep(3 if start or attempt else 0)  # arXiv API etiquette
        resp = ctx.client.get(API, params={
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": start,
            "max_results": PAGE,
        })
        resp.raise_for_status()
        entries = feedparser.parse(resp.content).entries
        if entries:
            return entries
    return []


def fetch(ctx: SourceContext) -> list[Item]:
    src = ctx.cfg.source("arxiv")
    query = _query(src["categories"], src.get("keyword_categories", []))
    items: list[Item] = []
    start = 0
    while start < src["max_results"]:
        entries = _page(ctx, query, start)
        if not entries:
            # The window is never empty for these categories: an empty page is an API failure.
            raise PartialFailure(items, [f"feed rỗng tại start={start} sau {EMPTY_RETRIES + 1} lần thử"])
        page = [_entry_to_item(e) for e in entries]
        items.extend(i for i in page if i.published >= ctx.since)
        if page[-1].published < ctx.since:
            break
        start += PAGE
    return items
