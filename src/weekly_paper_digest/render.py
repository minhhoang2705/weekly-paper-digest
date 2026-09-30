from __future__ import annotations

from datetime import datetime

from .config import Config
from .models import CRITERIA, Item

KIND_LABEL = {"paper": "📄 Paper", "blog": "📰 Blog/News", "repo": "💻 Repo", "model": "🤗 Model"}
CRITERION_LABEL = {
    "novelty": "Novelty", "credibility": "Credibility", "technical": "Technical",
    "impact": "Impact", "evidence": "Evidence",
}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _anchor(rank: int) -> str:
    return f"item-{rank}"


def _item_section(rank: int, item: Item) -> list[str]:
    out = [f'<a id="{_anchor(rank)}"></a>', f"## {rank}. {item.title}", ""]
    meta = [
        f"**Loại:** {KIND_LABEL[item.kind]} · **Topic:** {item.topic} · **Điểm tổng:** {item.total:.1f}/100",
        f"**Nguồn:** {', '.join(item.sources)} · **Ngày:** {item.published:%Y-%m-%d}" if item.published
        else f"**Nguồn:** {', '.join(item.sources)}",
    ]
    if item.authors:
        authors = ", ".join(item.authors[:8]) + (" et al." if len(item.authors) > 8 else "")
        meta.append(f"**Tác giả:** {authors}")
    links = [f"[Link]({item.url})"]
    if item.pdf_url:
        links.append(f"[PDF]({item.pdf_url})")
    if item.code_url and item.code_url != item.url:
        links.append(f"[Code]({item.code_url})")
    meta.append("**Links:** " + " · ".join(links))
    shown = {k: v for k, v in item.signals.items() if k not in ("arxiv_category", "topics", "publisher")}
    if shown:
        meta.append("**Tín hiệu:** " + ", ".join(f"`{k}`={v}" for k, v in shown.items()))
    out += [line + "  " for line in meta] + [""]

    out += ["| Tiêu chí | Điểm | Lý do |", "|---|:-:|---|"]
    out += [f"| {CRITERION_LABEL[c]} | {item.scores[c]}/5 | {_cell(item.reasons.get(c, ''))} |" for c in CRITERIA]
    out.append("")

    s = item.summary
    if s is None:
        out += ["> ⚠️ Không tạo được bản tóm tắt chi tiết cho mục này (lỗi LLM) — xem link gốc.", "", "---", ""]
        return out
    out += [f"> **TL;DR:** {s['tldr']}", ""]
    for title, key in (("Vấn đề", "problem"), ("Phương pháp", "method"), ("Thiết lập", "setup")):
        out += [f"### {title}", s[key], ""]
    out += ["### Kết quả chính"] + [f"- {r}" for r in s["results"]] + [""]
    out += ["### Hạn chế", s["limitations"], "", "### Ý nghĩa thực tế", s["takeaways"], ""]
    out += [f"<sub>Tóm tắt dựa trên: {item.fulltext_source}</sub>", "", "---", ""]
    return out


def render(
    cfg: Config,
    week: str,
    since: datetime,
    now: datetime,
    top: list[Item],
    stats: dict[str, int],
    warnings: list[str],
) -> str:
    out = [
        f"# Speech Weekly Digest — {week}",
        "",
        f"Khoảng thời gian: **{since:%Y-%m-%d} → {now:%Y-%m-%d}** · "
        f"Topic: {', '.join(cfg.topics)}",
        "",
        "| # | Tiêu đề | Loại | Topic | Tổng | N | C | T | I | E |",
        "|:-:|---|---|---|:-:|:-:|:-:|:-:|:-:|:-:|",
    ]
    for rank, item in enumerate(top, 1):
        s = item.scores
        out.append(
            f"| {rank} | [{_cell(item.title)}](#{_anchor(rank)}) | {KIND_LABEL[item.kind]} | {item.topic} | "
            f"**{item.total:.1f}** | {s['novelty']} | {s['credibility']} | {s['technical']} | "
            f"{s['impact']} | {s['evidence']} |"
        )
    weights = ", ".join(f"{CRITERION_LABEL[c]} {cfg.weights[c]:g}" for c in CRITERIA)
    out += ["", f"<sub>N/C/T/I/E = Novelty/Credibility/Technical/Impact/Evidence (1–5). Trọng số: {weights}.</sub>", "", "---", ""]
    if not top:
        out += ["_Tuần này không có mục nào đạt yêu cầu._", ""]
    for rank, item in enumerate(top, 1):
        out += _item_section(rank, item)

    out += ["## Thống kê lần chạy", ""]
    out += [f"- {k}: {v}" for k, v in stats.items()]
    out.append(f"- Models: {', '.join(f'{k}={v}' for k, v in cfg.models.items())}")
    if warnings:
        out += ["", "### ⚠️ Cảnh báo", ""] + [f"- {w}" for w in warnings]
    return "\n".join(out) + "\n"
