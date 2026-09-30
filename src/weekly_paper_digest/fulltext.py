from __future__ import annotations

from dataclasses import dataclass

import httpx
import trafilatura

from .http import github_headers
from .models import Item

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 250_000


@dataclass
class FullText:
    label: str                # human-readable origin shown in the digest
    pdf: bytes | None = None
    text: str | None = None


def _html_text(client: httpx.Client, url: str) -> str | None:
    resp = client.get(url)
    if resp.status_code != 200:
        return None
    text = trafilatura.extract(resp.text, include_tables=True, include_comments=False, url=url)
    return text[:MAX_TEXT_CHARS] if text and len(text) > 500 else None


def _pdf(client: httpx.Client, url: str) -> bytes | None:
    resp = client.get(url)
    ok = resp.status_code == 200 and resp.content[:5] == b"%PDF-"
    return resp.content if ok and len(resp.content) <= MAX_PDF_BYTES else None


def fetch_fulltext(client: httpx.Client, item: Item) -> FullText | None:
    """Best available primary content for an item; None means abstract only."""
    if item.kind == "paper":
        if item.pdf_url and (pdf := _pdf(client, item.pdf_url)):
            return FullText("PDF", pdf=pdf)
        if item.arxiv_id and (text := _html_text(client, f"https://arxiv.org/html/{item.arxiv_id}")):
            return FullText("arXiv HTML", text=text)
        return None
    if item.kind == "blog":
        text = _html_text(client, item.url)
        return FullText("bài viết gốc", text=text) if text else None
    if item.kind == "repo":
        repo = item.id.removeprefix("gh:")
        resp = client.get(
            f"https://api.github.com/repos/{repo}/readme",
            headers={**github_headers(), "Accept": "application/vnd.github.raw"},
        )
        return FullText("README", text=resp.text[:MAX_TEXT_CHARS]) if resp.status_code == 200 else None
    if item.kind == "model":
        model_id = item.id.removeprefix("hf-model:")
        resp = client.get(f"https://huggingface.co/{model_id}/raw/main/README.md")
        return FullText("model card", text=resp.text[:MAX_TEXT_CHARS]) if resp.status_code == 200 else None
    return None
