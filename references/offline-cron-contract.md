# Offline Cron Contract

Plutus Wire should feel like a stable local launchd job while running through
OpenClaw cron.

## Runtime Shape

- Short recurring runs.
- No long-lived ingest process.
- Single-process lock.
- Per-source checkpoint.
- Per-run manifest.
- Raw artifact first, database ingest second, processing third.
- Processor failure must not block the next ingest run.

## Local Store

Each successful adapter artifact should be ingested into:

```text
~/.openclaw/state/plutus-wire/db/plutus_wire.sqlite
```

The store should maintain:

- `runs`
- `raw_artifacts`
- `posts`
- `sightings`
- `retweet_events`
- `checkpoints`

Checkpoint updates are source-local. A successful Following run should update
only the Following checkpoint, even if another optional source fails.

## Recoverable States

These states should be recorded without treating the whole job as broken:

- `network_unavailable`
- `auth_required`
- `captcha_or_challenge`
- `rate_limited`
- `source_temporarily_empty`
- `adapter_error`
- `processor_error`
- `skipped_backoff`

## Backoff

Backoff should be source-local. A rate-limited optional source must not block
Following or For You.

Runtime backoff state is stored in SQLite `source_runtime`. Successful source
runs clear the failure count and backoff. Repeated failures increase backoff up
to a small cap so short OpenClaw cron intervals remain safe.

Before live adapter execution, `plutus_wire_tick.py --execute-adapters` runs a
health preflight unless `--skip-health` is passed. A failed preflight marks all
planned sources as recoverably skipped and exits 0 so the next cron tick can
retry.

## Resume Behavior

When the network returns, Plutus Wire should continue from the last successful
checkpoint and write a new manifest. It should not require a manual restart
unless the user is logged out or the browser bridge itself is unavailable.
