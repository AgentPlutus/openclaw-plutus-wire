# Cloud Handoff

Cloud handoff is a future opt-in capability. It must not be part of the default
local cron path.

## Product Goal

Users should be able to connect Plutus Wire to an Agent Plutus server platform
with minimal setup. The platform can receive daily feed packages, run heavier
processing, and present a cross-device review surface.

## Required Gates

Before any upload:

1. The user enables cloud sync explicitly.
2. The destination endpoint is visible in config.
3. The redaction filter runs locally.
4. A manifest is written locally.
5. The upload request references the manifest id.

## Redaction Filter

The default redaction profile should remove or hash:

- local file paths
- browser/session identifiers
- cookies and tokens
- private message text if ever encountered
- raw profile descriptions unless configured
- exact local run paths

It may keep:

- source name
- post URL or post id
- public author handle
- public post text when the user allows it
- normalized topic/entity tags
- derived summary cards

## Sync Modes

- `off`: default.
- `manifest-only`: upload run metadata without post text.
- `redacted-daily`: upload redacted daily feed package.
- `full-visible-feed`: upload selected visible public post content; requires a
  separate explicit confirmation.

## Server Boundary

The local skill should not require the server to function. If the server is
unreachable, local ingest and review must continue.
