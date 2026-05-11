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
