"""LLM stages: triage (cheap relevance on abstracts), analysis (full-text scoring + detailed summary)."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor

import httpx
from pydantic import BaseModel, Field

from .config import Config
from .fulltext import fetch_fulltext
from .llm import LLM, pdf_part
from .models import CRITERIA, Item
from .ranking import weighted_total

log = logging.getLogger(__name__)
TRIAGE_BATCH = 40


def _topics(cfg: Config) -> str:
    return "\n".join(f"- {name}: {desc}" for name, desc in cfg.topics.items())


def _signals(item: Item) -> str:
    return ", ".join(f"{k}={v}" for k, v in item.signals.items()) or "none"


# ---------------------------------------------------------------- triage

class TriageRow(BaseModel):
    id: str
    relevant: bool
    topic: str = Field(description="One of the topic names, or 'Other'")
    promise: int = Field(description="1-5: how likely this is among the most important items of the week")


class TriageBatch(BaseModel):
    items: list[TriageRow]


def triage(llm: LLM, cfg: Config, items: list[Item]) -> tuple[list[Item], list[str]]:
    """Keep items whose main contribution is in scope; attach topic and a promise score.

    A failed batch or ids the model silently omitted get one retry; what still fails is
    reported as a warning instead of killing the run.
    """
    system = (
        "You screen candidates for a weekly speech-technology digest.\n"
        f"In-scope topics:\n{_topics(cfg)}\n"
        "Mark relevant=true only when the item's MAIN contribution falls in one of these topics. "
        "Pure music/general audio, speaker verification alone, or incidental mentions of speech are not relevant. "
        "promise: 1 = routine/incremental, 3 = solid, 5 = likely a standout of the week. "
        "Return exactly one row per input id."
    )
    by_id = {i.id: i for i in items}
    batches = [items[n:n + TRIAGE_BATCH] for n in range(0, len(items), TRIAGE_BATCH)]

    def ask(batch: list[Item]) -> list[TriageRow]:
        payload = [
            {"id": i.id, "kind": i.kind, "title": i.title, "text": i.abstract[:900], "signals": _signals(i)}
            for i in batch
        ]
        result = llm.structured(cfg.models["triage"], system, [json.dumps(payload, ensure_ascii=False)], TriageBatch)
        return result.items

    def run(batch: list[Item]) -> tuple[list[TriageRow], int]:
        rows: dict[str, TriageRow] = {}
        pending = batch
        for _ in range(2):
            try:
                wanted = {i.id for i in pending}
                rows.update({r.id: r for r in ask(pending) if r.id in wanted})
            except Exception as exc:  # noqa: BLE001 - retried, then reported
                log.warning("triage batch failed: %s", exc)
            pending = [i for i in batch if i.id not in rows]
            if not pending:
                break
            log.warning("triage: %d/%d ids unanswered, retrying", len(pending), len(batch))
        return list(rows.values()), len(pending)

    kept: list[Item] = []
    unanswered = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows, missing in pool.map(run, batches):
            unanswered += missing
            for row in rows:
                item = by_id[row.id]
                if row.relevant and row.topic in cfg.topics:
                    item.topic = row.topic
                    item.promise = max(1, min(5, row.promise))
                    kept.append(item)
    if items and unanswered == len(items):
        # Nothing triaged at all (bad key, quota, outage): fail rather than publish an empty digest.
        raise RuntimeError("triage failed for every item; see log for the LLM error")
    warnings = [f"Triage bỏ sót {unanswered}/{len(items)} mục (lỗi LLM hoặc model bỏ qua id)."] if unanswered else []
    return kept, warnings


# ---------------------------------------------------------------- full-text analysis

class Criterion(BaseModel):
    score: int = Field(description="Integer 1-5")
    reason: str = Field(description="One sentence justification citing what the document shows")


class ScoreCard(BaseModel):
    novelty: Criterion
    credibility: Criterion
    technical: Criterion
    impact: Criterion
    evidence: Criterion


class Summary(BaseModel):
    tldr: str = Field(description="2-3 sentences: what it is and why it matters")
    problem: str = Field(description="Problem and motivation")
    method: str = Field(description="Detailed method: architecture, key components, training objectives, data, what is new vs prior work")
    setup: str = Field(description="Experimental setup: datasets, baselines, metrics, compute; for blogs/repos/models: usage, supported languages, requirements")
    results: list[str] = Field(description="Key quantitative results, each with the exact numbers, metric and comparison baseline")
    limitations: str = Field(description="Limitations, caveats, what is not evaluated")
    takeaways: str = Field(description="Practical implications for speech engineers/researchers")
    strengths: list[str] = Field(description="3-5 short phrases (max ~8 words each): main strengths")
    weaknesses: list[str] = Field(description="2-4 short phrases (max ~8 words each): main weaknesses or risks")
    context: str = Field(description="One line: who made it (authors/lab and affiliations as stated) and venue/release context")


class Analysis(BaseModel):
    # Field order matters: the model writes the analysis first, then scores what it just analyzed.
    summary: Summary
    scores: ScoreCard


RUBRIC = """Score each criterion as an integer 1-5 (1 = very weak, 3 = typical good work, 5 = exceptional):
- novelty: how new the idea/capability is versus prior work (5 = new paradigm or first-of-its-kind; 1 = rehash).
- credibility: trustworthiness of the source: author/lab track record, peer-reviewed venue, official release, reputable publisher.
- technical: depth and rigor of the method or engineering (architecture, training recipe, systems design).
- impact: expected effect on speech research or products; use adoption signals (HF upvotes, GitHub stars, likes) when given.
- evidence: strength of empirical support in the document: benchmarks against strong baselines, ablations, human evals,
  released code/weights. Claims without numbers score low.
Judge from the full document, not the abstract's claims; when information is missing, score conservatively and say so."""


def _analysis_system(cfg: Config) -> str:
    return (
        "You are a senior speech-technology reviewer writing detailed technical briefs of papers, posts, repos and "
        f"models for expert engineers, then ranking them. Write all text in {cfg.language}.\n"
        "Rules for the summary:\n"
        "- Use ONLY the provided document. Never invent numbers, datasets, baselines or claims.\n"
        "- Copy numbers exactly as written (WER, MOS, latency, params, hours of data...).\n"
        "- Go beyond the abstract: explain the method concretely enough that a reader could sketch it.\n"
        "- If the document does not state something, write 'Không được nêu trong tài liệu'.\n"
        "- Markdown inside fields is allowed (bold, inline code, short lists).\n"
        f"Scoring:\n{RUBRIC}"
    )


def analyze(llm: LLM, cfg: Config, client: httpx.Client, items: list[Item]) -> list[Item]:
    """Read each shortlisted item's full text once; produce both its detailed summary and its 5 scores.

    Ranking therefore reflects the full document. Items whose analysis fails are dropped (and reported).
    """
    system = _analysis_system(cfg)

    def run(item: Item) -> Item | None:
        header = (
            f"Kind: {item.kind}\nTopic: {item.topic}\nTitle: {item.title}\nURL: {item.url}\n"
            f"Authors/owner: {', '.join(item.authors[:15]) or 'unknown'}\n"
            f"Sources: {', '.join(item.sources)}\nSignals: {_signals(item)}\n"
            f"Code: {item.code_url or 'none listed'}\n"
        )
        try:
            ft = fetch_fulltext(client, item)
        except httpx.HTTPError as exc:
            log.warning("full text fetch failed for %s: %s", item.id, exc)
            ft = None
        if ft is None:
            item.fulltext_source = "abstract/mô tả (không lấy được full-text)"
            contents = [header + "Only the abstract/description is available:\n" + item.abstract]
        elif ft.pdf is not None:
            contents = [pdf_part(ft.pdf), header + "The attached PDF is the full document."]
        else:
            contents = [header + "Full document:\n" + (ft.text or "")]
        if ft is not None:
            item.fulltext_source, item.fulltext = ft.label, True
        try:
            result = llm.structured(cfg.models["analyze"], system, contents, Analysis)
        except Exception as exc:  # noqa: BLE001 - one failed item must not sink the run
            log.warning("analysis failed for %s: %s", item.id, exc)
            return None
        item.summary = result.summary.model_dump()
        for c in CRITERIA:
            crit: Criterion = getattr(result.scores, c)
            item.scores[c] = max(1, min(5, crit.score))
            item.reasons[c] = crit.reason
        item.total = weighted_total(item.scores, cfg.weights)
        return item

    with ThreadPoolExecutor(max_workers=4) as pool:
        return [i for i in pool.map(run, items) if i is not None]
