from __future__ import annotations

import os

import httpx

USER_AGENT = "weekly-paper-digest/0.1 (+https://github.com/minhhoang2705/weekly-paper-digest)"


def make_client() -> httpx.Client:
    transport = httpx.HTTPTransport(retries=3)
    return httpx.Client(
        transport=transport,
        follow_redirects=True,
        timeout=httpx.Timeout(60.0, connect=15.0),
        headers={"User-Agent": USER_AGENT},
    )


def github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
