from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

from ..fulltext import excerpt, github_readme
from ..http import github_headers
from ..models import Item
from . import SourceContext

SEARCH_API = "https://api.github.com/search/repositories"


def fetch(ctx: SourceContext) -> list[Item]:
    """Recently created, already-popular speech repos (one search per topic)."""
    src = ctx.cfg.source("github")
    created_after = (ctx.now - timedelta(days=src["created_within_days"])).date().isoformat()
    # Search API: 30 req/min with a token, 10 without.
    pause = 2.5 if os.environ.get("GITHUB_TOKEN") else 7.0
    items: dict[str, Item] = {}
    for i, topic in enumerate(src["topics"]):
        if i:
            time.sleep(pause)
        resp = ctx.client.get(SEARCH_API, headers=github_headers(), params={
            "q": f"topic:{topic} created:>={created_after} stars:>={src['min_stars']}",
            "sort": "stars", "order": "desc", "per_page": 20,
        })
        resp.raise_for_status()
        for r in resp.json().get("items", []):
            if r["full_name"] in items or r.get("fork") or r.get("archived"):
                continue
            items[r["full_name"]] = Item(
                id=f"gh:{r['full_name'].lower()}",
                kind="repo",
                title=r["full_name"],
                url=r["html_url"],
                sources=["GitHub"],
                published=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                authors=[r["owner"]["login"]],
                abstract=r.get("description") or "",
                code_url=r["html_url"],
                signals={
                    "github_stars": int(r["stargazers_count"]),
                    "github_forks": int(r["forks_count"]),
                    "topics": ", ".join(r.get("topics", [])),
                },
            )
    for item in items.values():
        # One-line descriptions are too thin to triage/score; the README carries the substance.
        readme = github_readme(ctx.client, item.id.removeprefix("gh:"))
        if readme:
            item.abstract = f"{item.abstract}\n\nREADME: {excerpt(readme)}".strip()
    return list(items.values())
