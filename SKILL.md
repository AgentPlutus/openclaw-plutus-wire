---
name: plutus-wire
description: >-
  Run and maintain Plutus Wire, an OpenClaw skill that uses OpenCLI to read the
  user's own logged-in X timeline sources locally, stores recoverable artifacts,
  and turns them into reviewable outside-intelligence briefs. Use when asked to
  install, configure, run, debug, or extend the Plutus Wire OpenClaw workflow.
---

# Plutus Wire

Plutus Wire is an OpenClaw-first skill. Treat Codex/Claude instructions as
developer affordances; the product runtime is OpenClaw plus OpenCLI.

## Operating Rules

- Keep the runtime local-first unless the user explicitly enables cloud sync.
- Use OpenCLI as a dependency, not as copied core code or a fork.
- Never ask users to paste cookies, access tokens, or secrets into the repo.
- Read only pages visible to the user's own logged-in browser session.
- Preserve raw artifacts and run manifests before processing.
- Treat network loss, logged-out state, captcha, and rate limits as recoverable
  runtime states.
- Do not make notifications a default source.
- Do not enable AI tab by default; detect it and offer it as optional.

## Default Workflow

1. Check OpenClaw and OpenCLI availability.
2. For a normal user install, run `./install.sh`; use `./install.sh --run-now`
   when the user wants one immediate ingest and processor smoke.
3. For manual installs, refresh OpenCLI adapters with
   `scripts/install_opencli_adapters.py --apply --force`.
4. Configure sources with `scripts/plutus_wire_setup.py --detect-home-tabs`.
5. Use explicit setup commands to enable optional sources:
   `--enable ai`, `--enable bookmarks`, or `--likes-handle <handle> --enable likes`.
6. Run `scripts/plutus_wire_tick.py --dry-run` before installing cron.
7. Use `scripts/plutus_wire_tick.py --execute-adapters` for a live local ingest
   smoke; add `--process` to build review cards, then inspect
   `scripts/plutus_wire_db_status.py`.
8. Use `scripts/install_openclaw_cron.py` to print the planned OpenClaw cron.
9. Only run `scripts/install_openclaw_cron.py --apply` when the user explicitly
   asks to install the cron job.
10. Review local output with `scripts/serve_review.py` before enabling any cloud
   handoff.
11. Use `scripts/plutus_wire_setup.py --cloud-enable --cloud-mode redacted-daily
    --cloud-endpoint <url>` only when the user explicitly wants server handoff.

## References

- Read `references/source-policy.md` before changing source adapters.
- Read `references/offline-cron-contract.md` before changing scheduler logic.
- Read `references/privacy-and-local-state.md` before changing storage.
- Read `references/cloud-handoff.md` before adding upload or server sync.
- Read `references/opencli-browser-bridge.md` before changing OpenCLI usage.

## Processing

`processor_v0` should remain explainable: normalize, deduplicate, merge related
signals, translate when configured, and produce reviewable cards. Do not import
Agent Plutus macro-writer rules as default behavior until the backfill has been
reviewed and the rules are extracted into a stable public contract.

Run `scripts/plutus_wire_process.py` or `scripts/plutus_wire_tick.py --process`
to write `review/latest-package.json` and `review/latest-cards.json`.

## Cron Stability

Live ticks run health preflight by default. Treat `network_unavailable`,
`auth_required`, `captcha_or_challenge`, `rate_limited`, `adapter_error`, and
`skipped_backoff` as recoverable runtime states. Keep OpenClaw cron short and
repeatable; do not add a long-lived ingest daemon.

## Cloud Handoff

Cloud handoff is opt-in. Build redacted packages with
`scripts/plutus_wire_cloud_handoff.py`; upload only with `--apply` after cloud
config has an endpoint and non-`off` mode. `full-visible-feed` requires
`--cloud-allow-full-visible-feed`.
