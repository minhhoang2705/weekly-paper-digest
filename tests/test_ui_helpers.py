import re

from weekly_paper_digest.fulltext import excerpt
from weekly_paper_digest.site.build import ranking_basis, safe_url, slug
from weekly_paper_digest.site.radar import AXES, CX, CY, R, radar_svg, vertex


def test_item_slugs_are_distinct_and_file_safe():
    ids = ["arxiv:2609.1", "arxiv:2609.2", "gh:a/b", "gh:a-b", "url:https://x.io/p?q=1"]
    slugs = [slug(i) for i in ids]
    assert len(set(slugs)) == len(ids)
    assert all(re.fullmatch(r"[a-z0-9-]+", s) for s in slugs)


def test_only_http_links_reach_href():
    assert safe_url("https://arxiv.org/abs/1") == "https://arxiv.org/abs/1"
    assert safe_url("javascript:alert(1)") == "#"
    assert safe_url(None) == "#"


def test_ranking_basis_never_claims_full_text_it_did_not_read():
    assert ranking_basis({"fulltext": True}) == "full-text analysis"
    assert ranking_basis({"fulltext": False}).startswith("abstract only")
    assert "earlier pipeline" in ranking_basis({})   # data written before full-text ranking


def test_radar_axis_order_matches_spec():
    # Clockwise from the top: novelty, technical, evidence, impact, credibility.
    assert AXES == ("novelty", "technical", "evidence", "impact", "credibility")
    top, upper_right, lower_right, lower_left, upper_left = (vertex(i, 5) for i in range(5))
    assert top.x == CX and top.y == CY - R
    assert upper_right.x > CX and upper_right.y < CY
    assert lower_right.x > CX and lower_right.y > CY
    assert lower_left.x < CX and lower_left.y > CY
    assert upper_left.x < CX and upper_left.y < CY


def test_radar_polygon_scales_with_scores():
    assert vertex(0, 0) == vertex(3, 0)            # zero collapses to the centre
    assert vertex(0, 2.5).y == CY - R / 2          # linear 0..5 scale
    assert vertex(0, 9) == vertex(0, 5)            # clamped to the outer ring
    svg = radar_svg({a: 5 for a in AXES}, {})
    area = re.search(r'class="radar-area" points="([^"]+)"', svg).group(1)
    assert tuple(map(float, area.split()[0].split(","))) == (CX, CY - R)


def test_excerpt_keeps_prose_and_numbers_drops_markup():
    card = (
        "---\nlicense: cc-by-4.0\n---\n# Model\n[![badge](b.svg)](x) **4.46% WER** on "
        "[Common Voice](https://cv)\n\n```python\nimport torch\n```\n| a | b |\n|---|---|\n| 1.2 | 3.4 |\n"
    )
    text = excerpt(card)
    assert "4.46% WER on Common Voice" in text and "1.2 | 3.4" in text
    for junk in ("license:", "badge", "import torch", "**", "|---|", "https://"):
        assert junk not in text
