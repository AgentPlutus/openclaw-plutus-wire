#!/usr/bin/env python3
"""Serve the local Plutus Wire review page."""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
from pathlib import Path

from lib.local_store import connect_db, store_summary
from lib.store import DEFAULT_STATE_DIR


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "assets" / "site"


def make_handler(state_dir: Path):
    class PlutusWireHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(SITE_ROOT), **kwargs)

        def do_GET(self):
            if self.path == "/data/config.json":
                self._serve_json(state_dir / "review" / "config.json")
                return
            if self.path == "/data/latest-manifest.json":
                latest = latest_manifest_path(state_dir)
                if latest is None:
                    self._serve_payload({})
                else:
                    self._serve_json(latest)
                return
            if self.path == "/data/db-status.json":
                conn = connect_db(state_dir)
                try:
                    self._serve_payload(store_summary(conn))
                finally:
                    conn.close()
                return
            if self.path == "/data/latest-cards.json":
                self._serve_json(state_dir / "review" / "latest-cards.json")
                return
            if self.path == "/data/latest-package.json":
                self._serve_json(state_dir / "review" / "latest-package.json")
                return
            if self.path == "/data/latest-cloud-manifest.json":
                self._serve_json(state_dir / "cloud" / "latest-manifest.json")
                return
            super().do_GET()

        def _serve_json(self, path: Path) -> None:
            if not path.exists():
                self._serve_payload({})
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(path.read_bytes())

        def _serve_payload(self, payload: dict) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    return PlutusWireHandler


def latest_manifest_path(state_dir: Path) -> Path | None:
    runs_dir = state_dir / "runs"
    if not runs_dir.exists():
        return None
    manifests = sorted(runs_dir.glob("*.manifest.json"))
    return manifests[-1] if manifests else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Plutus Wire review UI.")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args()

    state_dir = args.state_dir.expanduser()
    handler = make_handler(state_dir)
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as server:
        print(f"serving http://127.0.0.1:{args.port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
