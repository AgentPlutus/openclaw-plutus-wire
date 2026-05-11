#!/usr/bin/env python3
"""Serve the local Plutus Wire review page."""

from __future__ import annotations

import argparse
import http.server
import socketserver
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "assets" / "site"


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Plutus Wire review UI.")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(*a, directory=str(SITE_ROOT), **kw)
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as server:
        print(f"serving http://127.0.0.1:{args.port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
