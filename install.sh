#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec python3 scripts/plutus_wire_install.py "$@"
