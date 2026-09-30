from __future__ import annotations

import html
import re
import time

from ..models import Item
from . import PartialFailure, SourceContext

BASE = "https://www.isca-archive.org"
VOLUME_RE = re.compile(r'href="([a-z0-9_]+?_(\d{4}))/index\.html"')
ENTRY_RE = re.compile(
    r'<a class="w3-text" href="([^"/]+)\.html">\s*<p>\s*(.*?)\s*<br>\s*'
    r'<span[^>]*>\s*(.*?)\s*</span>',
    re.S,
)
ABSTRACT_RE = re.compile(r'<div id="abstract">.*?<h4>Abstract</h4>(.*?)(?:<h4>|</div>)', re.S)
META_RE = re.compile(r'<meta name="(citation_pdf_url|citation_conference_title)" content="([^"]*)"')


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _new_volumes(ctx: SourceContext) -> list[str]:
    resp = ctx.client.get(f"{BASE}/")
    resp.raise_for_status()
    volumes = {name: int(year) for name, year in VOLUME_RE.findall(resp.text)}
    if ctx.state.isca_volumes is None:
        # First ever run: only this year's volumes count as new; older ones are history.
        ctx.state.scanned_isca.update({v: "baseline" for v, y in volumes.items() if y < ctx.now.year})
        known = set(ctx.state.scanned_isca)
    else:
        # A volume scanned earlier this same week is rescanned so reruns reproduce the digest.
        known = {v for v, week in ctx.state.isca_volumes.items() if week != ctx.week}
    return sorted(v for v in volumes if v not in known)


def fetch(ctx: SourceContext) -> list[Item]:
    """Scan each newly published ISCA volume once; ISCA publishes per conference, not weekly."""
    src = ctx.cfg.source("isca")
    kw = ctx.cfg.keyword_regex()
    items: list[Item] = []
    failures: list[str] = []
    volumes = _new_volumes(ctx)
    budget = src["max_candidates"]
    for volume in volumes:
        resp = ctx.client.get(f"{BASE}/{volume}/index.html")
        resp.raise_for_status()
        entries = [
            (slug, _text(title), _text(authors))
            for slug, title, authors in ENTRY_RE.findall(resp.text)
        ]
        matched = [e for e in entries if kw.search(e[1])][: max(budget // len(volumes), 1)]
        for slug, title, authors in matched:
            url = f"{BASE}/{volume}/{slug}.html"
            try:
                page = ctx.client.get(url)
                page.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - reported via PartialFailure
                failures.append(f"{slug}: {type(exc).__name__}")
                continue
            meta = dict(META_RE.findall(page.text))
            abstract = ABSTRACT_RE.search(page.text)
            items.append(Item(
                id=f"isca:{volume}/{slug}",
                kind="paper",
                title=title,
                url=url,
                sources=["ISCA Archive"],
                published=ctx.now,
                authors=[a.strip() for a in authors.split(",") if a.strip()],
                abstract=_text(abstract.group(1)) if abstract else "",
                pdf_url=meta.get("citation_pdf_url"),
                signals={"venue": meta.get("citation_conference_title", volume)},
            ))
            time.sleep(0.3)
        ctx.state.scanned_isca[volume] = ctx.week
    if failures:
        raise PartialFailure(items, failures)
    return items
