"""Run it standalone: ``python -m kiddo_growth_chart``."""

from __future__ import annotations

import argparse

from .config import Config
from .web import create_app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kiddo-growth-chart")
    ap.add_argument("--config", help="path to config JSON (else $KIDDO_CONFIG)")
    ap.add_argument("--dataset", help="path to dataset JSON (else $KIDDO_DATASET, else sample)")
    ap.add_argument("--provider", help="photo provider name (default: none)")
    ap.add_argument("--photos", help="root directory for the 'folder' provider")
    ap.add_argument("--host", default="127.0.0.1", help="default: loopback only")
    ap.add_argument("--port", type=int, default=8461)
    args = ap.parse_args(argv)

    config = Config.load(args.config)
    if args.dataset:
        config.dataset = args.dataset
    if args.photos:
        config.provider = args.provider or "folder"
        config.provider_options = {"root": args.photos}
    elif args.provider:
        config.provider = args.provider

    create_app(config).run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
