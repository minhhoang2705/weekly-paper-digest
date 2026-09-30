from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Config
from .http import make_client
from .models import Item
from .ranking import dedupe, shortlist, top_k
from .render import render
from .sources import PartialFailure, SourceContext, registry
from .state import State

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    week: str
    digest_path: Path | None
    stats: dict[str, int]
    warnings: list[str]
    candidates: list[Item]


def iso_week(now: datetime) -> str:
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def crawl(ctx: SourceContext, week: str) -> tuple[list[Item], dict[str, int], list[str]]:
    """All enabled sources -> deduped, unseen, keyword-matching candidates."""
    raw: list[Item] = []
    stats: dict[str, int] = {}
    warnings: list[str] = []
    for name, fetch in registry().items():
        if not ctx.cfg.source(name):
            continue
        log.info("crawling %s", name)
        try:
            got = fetch(ctx)
        except PartialFailure as exc:
            got = exc.items
            warnings.append(f"{name}: lỗi một phần — {exc}")
        except Exception as exc:  # noqa: BLE001 - a dead source must not kill the digest
            got = []
            warnings.append(f"{name}: không crawl được — {type(exc).__name__}: {exc}")
        stats[f"crawled · {name}"] = len(got)
        raw.extend(got)

    items = dedupe(raw)
    stats["sau dedup"] = len(items)
    items = [i for i in items if not ctx.state.is_seen(i, week)]
    kw = ctx.cfg.keyword_regex()
    # Repos/models already come from speech-specific topics/tags.
    items = [i for i in items if i.kind in ("repo", "model") or kw.search(f"{i.title} {i.abstract}")]
    stats["qua keyword filter (chưa từng đăng)"] = len(items)
    return items, stats, warnings


def run(cfg: Config, root: Path, *, lookback_days: int | None = None, dry_run: bool = False) -> RunResult:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=lookback_days or cfg.lookback_days)
    week = iso_week(now)
    state = State.load(root / "state" / "seen.json")

    with make_client() as client:
        ctx = SourceContext(client=client, cfg=cfg, since=since, now=now, week=week, state=state)
        items, stats, warnings = crawl(ctx, week)
        if dry_run:
            return RunResult(week, None, stats, warnings, items)

        from .llm import LLM
        from .stages import score, summarize, triage

        llm = LLM()
        relevant = triage(llm, cfg, items)
        stats["LLM triage: liên quan"] = len(relevant)
        short = shortlist(relevant, cfg.shortlist_size)
        scored = score(llm, cfg, short)
        stats["được chấm điểm"] = len(scored)
        if len(scored) < len(short):
            warnings.append(f"{len(short) - len(scored)} mục chấm điểm thất bại (lỗi LLM).")
        top = top_k(scored, cfg.top_k)
        summarize(llm, cfg, client, top)
        missing = [i.title for i in top if i.summary is None]
        if missing:
            warnings.append(f"Không tóm tắt được: {'; '.join(missing)}")

    digest = root / "digests" / f"{week}.md"
    digest.parent.mkdir(parents=True, exist_ok=True)
    digest.write_text(render(cfg, week, since, now, top, stats, warnings), encoding="utf-8")
    state.mark_published(top, week)
    state.save()
    return RunResult(week, digest, stats, warnings, top)
