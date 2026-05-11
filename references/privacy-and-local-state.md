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
