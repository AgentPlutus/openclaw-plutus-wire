# Plutus Wire

Tap your own timeline. Break the algorithmic cage.

[中文介绍](README.zh-CN.md)

Plutus Wire is an OpenClaw skill for turning your own X timeline into a local
outside intelligence wire. It uses OpenCLI as a browser bridge, reads pages
visible to your logged-in browser session, stores artifacts locally, and builds
reviewable signal briefs from the sources you choose.

Plutus Wire is not a fork of OpenCLI and not a generic scraping framework.
OpenCLI supplies the browser bridge. Plutus Wire supplies the X adapters,
source registry, offline scheduler contract, local store, processing prompts,
review surface, and optional cloud handoff.

## Status

This repository is in early scaffold state. The first working target is v0.1:

- OpenClaw skill entrypoint.
- OpenCLI dependency and adapter layout.
- M1 OpenCLI adapters for health, home tab detection, timelines, likes, and
  bookmarks.
- M2 local source configuration written to
  `~/.openclaw/state/plutus-wire/config.json`.
- M3 SQLite local store with raw artifact ingest, post sightings, retweet
  events, and per-source checkpoints.
- M4 cron stability layer with health preflight, recoverable failure
  classification, source-local backoff, and DB status.
- M5 deterministic processor that turns SQLite posts into local review cards.
- M6 opt-in cloud handoff with local redaction, manifest/package files, and
  explicit upload gates.
- Local-first cron runner.
- Following and For You as default sources.
- Detected home tabs, likes, and bookmarks as optional sources.
- Local SQLite/state/log artifacts.
- Reviewable brief cards.
- Cloud sync design that is opt-in and redaction-first.

## Why It Exists

Algorithmic timelines optimize for engagement. Plutus Wire gives the user a
separate local intelligence desk: a way to compare Following, For You, optional
home tabs, likes, and bookmarks without treating the platform ranking as the
final view of reality.

The product goal is not to collect more posts. The goal is to build an outside
view that the user can inspect, reject, and refine.

## Local-First Contract

By default, Plutus Wire runs locally.

- It uses the user's own browser login state.
- It only reads content visible to that user.
- It stores raw artifacts and derived state on the user's machine.
- It does not upload feed data by default.
- It does not ask users to paste cookies, tokens, or secrets into the repo.
- It treats network loss as a recoverable runtime state, not a fatal error.

Future server integration will be explicit opt-in. Uploads must pass through a
redaction filter and write a user-visible manifest before leaving the machine.

## Dependencies

Install OpenCLI first. Install OpenClaw when you want scheduled cron runs.

```bash
npm install -g @jackwener/opencli
opencli --help
# Optional, for scheduled cron runs:
openclaw --help
```

OpenCLI is credited in `NOTICE`. Plutus Wire should send upstream issues or pull
requests to OpenCLI when it needs browser bridge changes instead of carrying a
private fork.

## Quickstart

Plutus Wire ships its OpenCLI adapters in this repository under
`opencli-clis/plutus-wire/`. The one-command installer copies those adapters
into `~/.opencli/clis/plutus-wire`, validates them, detects available X home
tabs, writes local config, and runs a dry-run manifest.

```bash
git clone https://github.com/AgentPlutus/openclaw-plutus-wire.git
cd openclaw-plutus-wire
./install.sh
```

To install and immediately run one local ingest plus processor smoke:

```bash
./install.sh --run-now
```

Then open the local review page:

```bash
python3 scripts/serve_review.py
```

Manual flow:

```bash
python3 scripts/install_opencli_adapters.py --apply --force
opencli validate plutus-wire
python3 scripts/plutus_wire_setup.py --detect-home-tabs
python3 scripts/plutus_wire_tick.py --execute-adapters --process
python3 scripts/plutus_wire_db_status.py
```

For scheduled OpenClaw runs, first verify `./install.sh --run-now`, then create
an OpenClaw cron job through `scripts/install_openclaw_cron.py --apply`.

To install adapters into OpenCLI during development:

```bash
python3 scripts/install_opencli_adapters.py --apply
opencli validate plutus-wire
opencli plutus-wire home-tabs --format json
opencli plutus-wire timeline --type following --limit 20 --format json
```

The installer defaults to a copied install, which is safest for OpenCLI package
resolution. Use `--mode symlink` only for local development when you have
validated that your OpenCLI runtime resolves symlinked adapters correctly.

To configure sources:

```bash
python3 scripts/plutus_wire_setup.py --detect-home-tabs
python3 scripts/plutus_wire_setup.py --enable ai
python3 scripts/plutus_wire_setup.py --enable bookmarks
python3 scripts/plutus_wire_setup.py --likes-handle your_handle --enable likes
python3 scripts/plutus_wire_setup.py --disable ai
```

The setup command writes:

```text
~/.openclaw/state/plutus-wire/config.json
~/.openclaw/state/plutus-wire/review/config.json
```

Serve the local review UI with:

```bash
python3 scripts/plutus_wire_process.py
python3 scripts/serve_review.py
```

The SQLite store lives at:

```text
~/.openclaw/state/plutus-wire/db/plutus_wire.sqlite
```

Install the OpenClaw cron only after local smoke passes:

```bash
python3 scripts/install_openclaw_cron.py --every 5m
python3 scripts/install_openclaw_cron.py --every 5m --disabled --apply
```

Live ticks exit successfully for recoverable states such as network loss,
logged-out browser state, captcha/challenge, rate limits, and source-local
adapter errors. These are written to the run manifest and SQLite
`source_runtime` table instead of crashing the whole schedule.

The default cron plan runs local ingest plus `processor_v0`. It does not upload
feed data.

To prepare an opt-in cloud handoff:

```bash
python3 scripts/plutus_wire_setup.py \
  --cloud-enable \
  --cloud-mode redacted-daily \
  --cloud-endpoint https://example.com/plutus-wire/ingest
python3 scripts/plutus_wire_tick.py --execute-adapters --process --cloud-handoff
python3 scripts/plutus_wire_cloud_handoff.py
```

The cloud command writes redacted local manifest/package files under:

```text
~/.openclaw/state/plutus-wire/cloud/
```

Uploads require both enabled cloud config and an explicit apply path:

```bash
python3 scripts/plutus_wire_cloud_handoff.py --apply
python3 scripts/install_openclaw_cron.py --include-cloud-handoff --cloud-apply
```

`full-visible-feed` additionally requires
`--cloud-allow-full-visible-feed`.

## Source Defaults

Default enabled sources:

- Following
- For You

Optional sources:

- Detected X home tabs such as AI, if the account exposes them.
- Likes.
- Bookmarks.
- Other detected tabs only when an adapter can read them.

Notifications are intentionally out of v0.1. Lists and communities are not
default sources.

## Repository Layout

```text
SKILL.md
README.md
README.zh-CN.md
install.sh
scripts/
  plutus_wire_install.py
  plutus_wire_tick.py
  plutus_wire_setup.py
  plutus_wire_process.py
  plutus_wire_cloud_handoff.py
  plutus_wire_db_status.py
  install_opencli_adapters.py
  install_openclaw_cron.py
  uninstall_openclaw_cron.py
  serve_review.py
  lib/
opencli-clis/plutus-wire/
  health.js
  home-tabs.js
  timeline.js
  likes.js
  bookmarks.js
prompts/
references/
assets/site/
tests/
codex/
```

## Safety Language

Use these words in public docs:

- local-first
- browser bridge
- user's own logged-in browser session
- intelligence wire
- reviewable brief
- redaction filter

Avoid positioning this project as surveillance, secret collection, bypassing
access controls, or evading platform limits.
