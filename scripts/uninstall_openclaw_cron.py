#!/usr/bin/env python3
"""Print guidance for removing Plutus Wire cron jobs."""

from __future__ import annotations


def main() -> int:
    print("List jobs:")
    print("  openclaw cron list")
    print("Remove the Plutus Wire job by id:")
    print("  openclaw cron rm <job-id>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
