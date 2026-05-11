# Source Policy

Plutus Wire reads user-selected X sources through OpenCLI and the user's own
browser login state.

## Allowed Sources

Default enabled:

- `following`
- `for-you`

Optional:

- `ai` or other detected home tabs.
- `likes`.
- `bookmarks`.
- Lists or communities only when detected and supported by an adapter.

Out of v0.1:

- Notifications.
- Third-party account monitoring that is not visible to the user's session.
- Bulk collection outside configured user sources.

## Adapter Rules

- Use OpenCLI browser bridge APIs and browser-visible requests.
- Do not ask users for cookies or tokens.
- Do not store secrets in run artifacts.
- Keep source names explicit in every artifact.
- Write adapter version and OpenCLI version into run manifests.
- If a source returns auth, captcha, rate-limit, or network errors, mark only
  that source as degraded and keep the rest of the run recoverable.

## M1 Adapter Commands

```bash
opencli plutus-wire health --format json
opencli plutus-wire home-tabs --format json
opencli plutus-wire timeline --type following --limit 80 --format json
opencli plutus-wire timeline --type for-you --limit 80 --format json
opencli plutus-wire timeline --type ai --limit 80 --format json
opencli plutus-wire bookmarks --limit 80 --format json
opencli plutus-wire likes --handle <handle> --limit 80 --format json
```

`home-tabs` is detection-only. It should not be treated as an ingest source.

## Local Config

Source setup writes:

```text
~/.openclaw/state/plutus-wire/config.json
```

Default enabled sources are `following` and `for-you`. AI, likes, and bookmarks
remain disabled until the user enables them. Likes must include a handle before
it can be enabled.

## Public Positioning

Say:

- browser bridge
- your own logged-in browser session
- local-first timeline intelligence
- source selection

Do not say:

- bypass access controls
- evade rate limits
- steal, spy, or secretly monitor
- collect other users' private data
