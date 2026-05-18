# Privacy And Local State

Plutus Wire is local-first.

## Local State

Default state directory:

```text
~/.openclaw/state/plutus-wire/
```

Expected subdirectories:

```text
runs/
raw/
db/
review/
cloud/
```

SQLite database:

```text
~/.openclaw/state/plutus-wire/db/plutus_wire.sqlite
```

Source setup writes the main config at:

```text
~/.openclaw/state/plutus-wire/config.json
```

The review UI reads a mirrored copy from:

```text
~/.openclaw/state/plutus-wire/review/config.json
```

## Never Store

- Browser cookies.
- API tokens.
- OpenClaw gateway tokens.
- X bearer tokens.
- Passwords.
- Private keys.

## Raw Artifacts

Raw artifacts may contain timeline text and public profile metadata visible to
the logged-in user. They must stay local by default and must not be committed.
The SQLite store is also local state and must not be committed.

Runtime failure records such as `source_runtime.last_error` must not contain
cookies, tokens, browser profile paths, or gateway credentials. Keep errors
short and operational.

Review artifacts under `review/` are local by default. They may include derived
summaries plus evidence text from visible posts. Cloud handoff must pass them
through the redaction layer before writing a package intended for upload.

## Derived Artifacts

Derived artifacts should keep source provenance while reducing raw exposure:

- post id
- URL
- source name
- timestamp
- author handle
- normalized text
- derived card text
- processing status

Cloud packages must replace local paths with `[local-path]`, replace secret
fields with `[redacted]`, and remove evidence `text` unless
`full-visible-feed` has been explicitly confirmed.
