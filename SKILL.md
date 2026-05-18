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
2. Install or refresh OpenCLI adapters with `scripts/install_opencli_adapters.py`
   only when the user asks to modify local OpenCLI state.
3. Configure sources with `scripts/plutus_wire_setup.py --detect-home-tabs`.
4. Use explicit setup commands to enable optional sources:
   `--enable ai`, `--enable bookmarks`, or `--likes-handle <handle> --enable likes`.
5. Run `scripts/plutus_wire_tick.py --dry-run` before installing cron.
6. Use `scripts/plutus_wire_tick.py --execute-adapters` for a live local ingest
   smoke; then inspect `scripts/plutus_wire_db_status.py`.
7. Use `scripts/install_openclaw_cron.py` to print the planned OpenClaw cron.
8. Only run `scripts/install_openclaw_cron.py --apply` when the user explicitly
   asks to install the cron job.
9. Review local output before enabling any cloud handoff.

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

## Cron Stability

Live ticks run health preflight by default. Treat `network_unavailable`,
`auth_required`, `captcha_or_challenge`, `rate_limited`, `adapter_error`, and
`skipped_backoff` as recoverable runtime states. Keep OpenClaw cron short and
repeatable; do not add a long-lived ingest daemon.
