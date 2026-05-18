# Cloud Handoff

Cloud handoff is an opt-in capability. It must not be part of the default local
cron upload path.

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

`scripts/plutus_wire_cloud_handoff.py` and
`scripts/plutus_wire_tick.py --cloud-handoff` may build local manifest/package
files. They upload only with an explicit apply path.

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

## Local Artifacts

Cloud handoff writes:

- `cloud/latest-manifest.json`
- `cloud/latest-package.json`
- `cloud/<manifest_id>.manifest.json`
- `cloud/<manifest_id>.package.json`

The manifest includes `manifest_id`, package hash, package byte count, mode,
run id, and upload status. The package is mode-specific:

- `manifest-only`: run metadata and review summary only.
- `redacted-daily`: redacted review package with evidence text removed.
- `full-visible-feed`: review package with visible post text preserved after
  explicit confirmation.

## Server Boundary

The local skill should not require the server to function. If the server is
unreachable, local ingest and review must continue.
