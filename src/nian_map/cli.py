"""Command line entry point: `nian` starts the map server."""
from __future__ import annotations

import argparse
import logging
import os
import webbrowser

from . import __version__


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nian", description="Nian — live world map of social-media activity.")
    parser.add_argument("--host", default=os.environ.get("NIAN_HOST", "127.0.0.1"), help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("NIAN_PORT", "8100")), help="port (default 8100)")
    parser.add_argument("--youtube-key", help="YouTube Data API v3 key (or set NIAN_YOUTUBE_KEY / .env)")
    parser.add_argument("--demo", action="store_true", help="generate demo publications")
    parser.add_argument("--db", help="SQLite database path (default ~/.nian/nian.db)")
    parser.add_argument("--open", action="store_true", help="open the map in the browser")
    parser.add_argument("--dev", action="store_true", help="development mode: auto-reload, API docs at /docs")
    parser.add_argument("--version", action="version", version=f"nian-map {__version__}")
    args = parser.parse_args(argv)

    # Settings are read at import time, so the environment is set first.
    if args.youtube_key:
        os.environ["NIAN_YOUTUBE_KEY"] = args.youtube_key
    if args.demo:
        os.environ["NIAN_DEMO"] = "1"
    if args.db:
        os.environ["NIAN_DB_PATH"] = args.db
    if args.dev:
        os.environ["NIAN_ENV"] = "development"

    import uvicorn

    from .config import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    has_key = bool(os.environ.get("NIAN_YOUTUBE_KEY") or os.environ.get("YOUTUBE_API_KEY"))
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"Nian {__version__} → {url}")
    print(f"  YouTube: {'key detected' if has_key else 'no key (search and collection disabled)'}")
    if args.open:
        webbrowser.open(url)
    uvicorn.run("nian_map.main:app", host=args.host, port=args.port, reload=args.dev,
                proxy_headers=True, server_header=False, log_level="info")


if __name__ == "__main__":
    main()
