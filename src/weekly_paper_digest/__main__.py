from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import load_config
from .pipeline import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="weekly-digest", description="Weekly speech paper digest")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repo root (config.yaml, digests/, state/)")
    parser.add_argument("--lookback-days", type=int, help="override config.lookback_days")
    parser.add_argument("--dry-run", action="store_true", help="crawl + filter only; no LLM calls, nothing written")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_dotenv(args.root / ".env")
    cfg = load_config(args.root / "config.yaml")

    result = run(cfg, args.root, lookback_days=args.lookback_days, dry_run=args.dry_run)
    for k, v in result.stats.items():
        print(f"{k}: {v}")
    for w in result.warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    if args.dry_run:
        by_kind: dict[str, int] = {}
        for item in result.candidates:
            by_kind[item.kind] = by_kind.get(item.kind, 0) + 1
        print("candidates by kind:", by_kind)
        for item in result.candidates[:15]:
            print(f"  [{item.kind}] {item.title[:100]}  ({', '.join(item.sources)})")
    else:
        print(f"digest: {result.digest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
