from datetime import datetime, timezone
from types import SimpleNamespace

from weekly_paper_digest.sources import SourceContext
from weekly_paper_digest.sources.isca import _new_volumes
from weekly_paper_digest.state import State

INDEX = """
<a href="interspeech_2024/index.html">x</a>
<a href="interspeech_2025/index.html">x</a>
<a href="ssw_2026/index.html">x</a>
<a href="interspeech_2026/index.html">x</a>
"""


class StubClient:
    def get(self, url):
        return SimpleNamespace(text=INDEX, raise_for_status=lambda: None)


def _ctx(state: State, week: str) -> SourceContext:
    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    return SourceContext(client=StubClient(), cfg=None, since=now, now=now, week=week, state=state)


def test_first_run_treats_only_current_year_as_new(tmp_path):
    state = State.load(tmp_path / "seen.json")
    assert _new_volumes(_ctx(state, "2026-W40")) == ["interspeech_2026", "ssw_2026"]


def test_volume_rescanned_on_same_week_rerun_but_not_later(tmp_path):
    path = tmp_path / "seen.json"
    state = State.load(path)
    _new_volumes(_ctx(state, "2026-W40"))
    state.scanned_isca.update({"interspeech_2026": "2026-W40", "ssw_2026": "2026-W40"})
    state.save()

    assert _new_volumes(_ctx(State.load(path), "2026-W40")) == ["interspeech_2026", "ssw_2026"]
    assert _new_volumes(_ctx(State.load(path), "2026-W41")) == []
