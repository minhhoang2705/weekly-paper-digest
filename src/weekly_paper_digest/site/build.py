"""Build the static web UI (docs/) from data/*.json. Served by GitHub Pages from main:/docs."""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup

from ..config import Config, load_config
from ..models import CRITERIA
from ..store import load_runs
from .icons import icon
from .radar import radar_svg

HERE = Path(__file__).parent
KIND_LABEL = {"paper": "Paper", "blog": "Blog", "repo": "Repo", "model": "Model"}
EXCERPT_LABEL = {"paper": "abstract", "blog": "feed excerpt", "repo": "README excerpt", "model": "model card excerpt"}

NAV = [  # (label, icon, page or None when the feature does not exist yet)
    ("Dashboard", "layout-grid", "index.html"),
    ("Research Feed", "newspaper", "feed.html"),
    ("Trends", "trending-up", None),
    ("Research Graph", "network", None),
    ("Compare", "git-compare", None),
    ("Digest", "file-text", "digest.html"),
    ("Research Agent", "bot", None),
    ("Settings", "settings", "settings.html"),
]

# Auto-analysis sections, in reading order. `primary` ones stay visible when collapsed.
SECTIONS = [
    ("tldr", "Key idea", "lightbulb", True),
    ("problem", "Problem", "circle-help", False),
    ("method", "Methodology", "flask-conical", True),
    ("setup", "Setup", "database", False),
    ("results", "Results", "gauge", True),
    ("limitations", "Limitations", "triangle-alert", False),
    ("takeaways", "Takeaways", "rocket", False),
]

_md = MarkdownIt("commonmark", {"html": False})


def markdown(text: str) -> Markup:
    return Markup(_md.render(text or ""))


def slug(item_id: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", item_id.lower()).strip("-")[:60]
    return f"{base}-{hashlib.sha1(item_id.encode()).hexdigest()[:6]}"


def fmt_date(value: str | None) -> str:
    return datetime.fromisoformat(value).strftime("%b %-d, %Y") if value else ""


def safe_url(value: str | None) -> str:
    """Links come from third-party feeds: only http(s) may reach an href."""
    return value if value and re.match(r"https?://", value, re.I) else "#"


def _sections(summary: dict) -> list[dict]:
    out = []
    for key, title, icon_name, primary in SECTIONS:
        value = summary.get(key)
        if not value:
            continue
        body = "\n".join(f"- {r}" for r in value) if isinstance(value, list) else value
        out.append({"key": key, "title": title, "icon": icon_name, "primary": primary, "body": body})
    return out


def collect_items(runs: list[dict]) -> list[dict]:
    """Latest occurrence of every item across runs (runs come newest first)."""
    seen: dict[str, dict] = {}
    for run in runs:
        for row in run["items"]:
            if row["id"] in seen:
                continue
            item = dict(row)
            item["week"] = run["week"]
            item["analyzed_at"] = run["generated_at"]
            item["slug"] = slug(row["id"])
            item["sections"] = _sections(row["summary"]) if row.get("summary") else []
            seen[row["id"]] = item
    return list(seen.values())


class Site:
    def __init__(self, cfg: Config, root: Path, out: Path):
        self.cfg, self.root, self.out = cfg, root, out
        self.runs = load_runs(root / "data")
        self.items = collect_items(self.runs)
        self.env = Environment(
            loader=FileSystemLoader(HERE / "templates"),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters.update(markdown=markdown, date=fmt_date, url=safe_url)
        self.env.globals.update(
            icon=icon, radar=radar_svg, cfg=cfg, site=cfg.site, nav=NAV, criteria=CRITERIA,
            kind_label=KIND_LABEL, excerpt_label=EXCERPT_LABEL,
            latest_week=self.runs[0]["week"] if self.runs else None,
        )

    def page(self, template: str, dest: str, active: str | None, **ctx) -> None:
        depth = dest.count("/")
        html = self.env.get_template(template).render(base="../" * depth, active=active, **ctx)
        path = self.out / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def build(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / "assets").mkdir(parents=True)
        for asset in (HERE / "static").iterdir():
            shutil.copy(asset, self.out / "assets" / asset.name)
        (self.out / ".nojekyll").write_text("")

        by_id = {i["id"]: i for i in self.items}
        latest = self.runs[0] if self.runs else None
        latest_top = [by_id[r["id"]] for r in latest["items"] if r["rank"]] if latest else []

        self.page("dashboard.html", "index.html", "Dashboard", run=latest, top=latest_top,
                  total_items=len(self.items), total_weeks=len(self.runs))
        feed = sorted(self.items, key=lambda i: (i["week"], i["total"]), reverse=True)
        self.page("feed.html", "feed.html", "Research Feed", items=feed,
                  topics=list(self.cfg.topics), kinds=sorted({i["kind"] for i in feed}))
        for item in self.items:
            self.page("paper.html", f"items/{item['slug']}.html", "Research Feed", item=item)
        self.page("digest_index.html", "digest.html", "Digest", runs=self.runs)
        for run in self.runs:
            # Published items are never re-crawled (state/seen.json), so their latest occurrence is this run.
            top = [by_id[r["id"]] for r in run["items"] if r["rank"]]
            self.page("digest_week.html", f"digest/{run['week']}.html", "Digest", run=run, top=top)
        self.page("settings.html", "settings.html", "Settings")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="weekly-site", description="Build the static web UI")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, help="output dir (default: <root>/docs)")
    args = parser.parse_args(argv)
    cfg = load_config(args.root / "config.yaml")
    site = Site(cfg, args.root, args.out or args.root / "docs")
    site.build()
    print(f"built {len(site.items)} item pages from {len(site.runs)} runs -> {site.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
