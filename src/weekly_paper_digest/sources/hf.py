from __future__ import annotations

from datetime import datetime, timedelta

from ..fulltext import excerpt, hf_model_card
from ..models import Item
from . import SourceContext

DAILY_API = "https://huggingface.co/api/daily_papers"
MODELS_API = "https://huggingface.co/api/models"


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def fetch_papers(ctx: SourceContext) -> list[Item]:
    """HF Daily Papers for every day in the window; upvotes are a community-impact signal."""
    items: list[Item] = []
    day = ctx.since.date()
    while day <= ctx.now.date():
        resp = ctx.client.get(DAILY_API, params={"date": day.isoformat(), "limit": 100})
        resp.raise_for_status()
        for entry in resp.json():
            p = entry["paper"]
            signals: dict = {"hf_upvotes": int(p.get("upvotes") or 0)}
            if p.get("githubStars") is not None:
                signals["github_stars"] = int(p["githubStars"])
            items.append(Item(
                id=f"arxiv:{p['id']}",
                kind="paper",
                title=" ".join(p["title"].split()),
                url=f"https://huggingface.co/papers/{p['id']}",
                sources=["HF Daily Papers"],
                published=_dt(p.get("publishedAt")),
                authors=[a["name"] for a in p.get("authors", []) if a.get("name")],
                abstract=" ".join((p.get("summary") or "").split()),
                pdf_url=f"https://arxiv.org/pdf/{p['id']}",
                code_url=p.get("githubRepo") or None,
                signals=signals,
            ))
        day += timedelta(days=1)
    return items


def fetch_models(ctx: SourceContext) -> list[Item]:
    """Trending speech models created recently."""
    src = ctx.cfg.source("hf_models")
    created_after = ctx.now - timedelta(days=src["created_within_days"])
    items: dict[str, Item] = {}
    for tag in src["pipeline_tags"]:
        resp = ctx.client.get(MODELS_API, params={
            "pipeline_tag": tag, "sort": "trendingScore", "limit": src["per_tag"],
        })
        resp.raise_for_status()
        for m in resp.json():
            created = _dt(m.get("createdAt"))
            likes = int(m.get("likes") or 0)
            if created is None or created < created_after or likes < src["min_likes"] or m["id"] in items:
                continue
            card = hf_model_card(ctx.client, m["id"])
            items[m["id"]] = Item(
                id=f"hf-model:{m['id']}",
                kind="model",
                title=m["id"],
                url=f"https://huggingface.co/{m['id']}",
                sources=["HF Models"],
                published=created,
                authors=[m["id"].split("/")[0]],
                # The model card is the only description: triage/scoring would otherwise see just the id.
                abstract=excerpt(card) if card else f"Hugging Face model, pipeline: {tag} (no model card).",
                signals={
                    "hf_likes": likes,
                    "hf_downloads": int(m.get("downloads") or 0),
                    "hf_trending": int(m.get("trendingScore") or 0),
                    "pipeline_tag": tag,
                },
            )
    return list(items.values())
