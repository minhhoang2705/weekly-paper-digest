from pathlib import Path

from weekly_paper_digest.models import Item
from weekly_paper_digest.ranking import dedupe, top_k, weighted_total
from weekly_paper_digest.state import State

WEIGHTS = {"novelty": 25, "technical": 20, "evidence": 20, "impact": 20, "credibility": 15}


def _item(id_, title="T", **kw):
    return Item(id=id_, kind="paper", title=title, url="u", sources=[kw.pop("source", "s")], **kw)


def _scored(id_, **scores):
    item = _item(id_, title=id_)
    item.scores = {c: scores.get(c, 3) for c in WEIGHTS}
    item.total = weighted_total(item.scores, WEIGHTS)
    return item


def test_weighted_total_bounds():
    assert weighted_total({c: 1 for c in WEIGHTS}, WEIGHTS) == 0.0
    assert weighted_total({c: 5 for c in WEIGHTS}, WEIGHTS) == 100.0


def test_weights_decide_ranking():
    novel = _scored("novel", novelty=5, credibility=1)       # heavy weight up, light weight down
    credible = _scored("credible", novelty=1, credibility=5)
    assert [i.id for i in top_k([credible, novel], 2)] == ["novel", "credible"]


def test_top_k_skips_unscored_and_truncates():
    items = [_scored(f"p{n}", novelty=1 + n % 5) for n in range(12)] + [_item("unscored")]
    top = top_k(items, 10)
    assert len(top) == 10 and all(i.scores for i in top)
    assert [i.total for i in top] == sorted((i.total for i in top), reverse=True)


def test_dedupe_merges_arxiv_and_hf_signals():
    arxiv = _item("arxiv:2509.1", title="Fast ASR", source="arXiv", abstract="short")
    hf = _item("arxiv:2509.1", title="Fast ASR", source="HF Daily Papers", abstract="a longer abstract",
               signals={"hf_upvotes": 42}, code_url="https://github.com/x/y")
    [merged] = dedupe([arxiv, hf])
    assert merged.sources == ["arXiv", "HF Daily Papers"]
    assert merged.signals["hf_upvotes"] == 42 and merged.code_url and merged.abstract == "a longer abstract"


def test_dedupe_by_title_prefers_arxiv_identity():
    isca = _item("isca:interspeech_2026/x", title="Streaming TTS, Revisited!", source="ISCA Archive",
                 signals={"venue": "Proc. Interspeech 2026"})
    arxiv = _item("arxiv:2606.9", title="Streaming TTS revisited", source="arXiv")
    [merged] = dedupe([isca, arxiv])
    assert merged.id == "arxiv:2606.9"
    assert merged.signals["venue"] == "Proc. Interspeech 2026"


def test_state_excludes_earlier_weeks_but_not_current(tmp_path: Path):
    path = tmp_path / "seen.json"
    state = State.load(path)
    state.mark_published([_item("arxiv:1", title="Old Paper")], "2026-W39")
    state.save()

    state = State.load(path)
    assert state.is_seen(_item("arxiv:1", title="Old Paper"), "2026-W40")
    # Same work reached via a different source is still recognized by title.
    assert state.is_seen(_item("url:blog/old", title="Old paper"), "2026-W40")
    # Re-running the week that published it must reproduce, not exclude, its picks.
    assert not state.is_seen(_item("arxiv:1", title="Old Paper"), "2026-W39")
