# Common Issues

Quick diagnostics for Zoom CoBrowse SDK issues.

- Ensure SDK script/package is loaded.
- Verify role-specific JWT generation on server.
- Validate token expiry and clock skew.
- Confirm session PIN flow between customer and agent.

## Docs Links / 404s

**Symptom**: Official doc links you found are stale or return 404.

**Fix**:
- Prefer the curated references under `references/` (these are meant to stay stable even if external URLs drift).
- If you need working code, start from official sample repos referenced by the skill, then adapt to your stack.

## Confusing "Who Creates the Session?"

**Symptom**: You built an "agent creates session" endpoint, but the customer flow seems to actually start the share / generate the PIN.

**Fix**:
- Treat **customer start/share** as the action that creates the shareable context (PIN/session), then the **agent joins** using that PIN/session info.
- Keep your server responsibilities narrow: token minting, optional auditing, and routing; avoid inventing "session creation" semantics that the SDK already owns.

## Two PIN Values (Most Common Integration Mistake)

**Symptom**: UI shows one PIN from backend/session record and another PIN from SDK event, agent gets `Pin not found` or `Cobrowse code not found`.

**Fix**:
- Treat `session.on("pincode_updated")` as the **authoritative support PIN** for agent entry.
- Display exactly one primary PIN in UI (label it clearly as "Support PIN").
- Do not surface provisional/debug PINs to users.
- When opening agent page with `?pin=...`, prefer freshly generated links and avoid stale bookmarks.

## Agent Desk Error `30308` (Pincode is not found)

**Symptom**: Zoom-hosted agent desk shows:
- `Cobrowse code not found`
- error code `30308`

**Fix**:
- Ensure customer session is active and not expired before agent joins.
- Use the latest PIN emitted by `pincode_updated`.
- If your app restarts or uses in-memory state, persist session/PIN mapping or avoid strict local PIN gating for desk launch.
- Have agent re-enter a fresh PIN from a newly started customer session.

## Plain HTML / Express Integration Friction

**Symptom**: Quickstarts assume Vite/modern build pipeline; your plain HTML/Express adaptation breaks.

**Fix**:
- Load the SDK exactly as the official snippet expects (script order matters).
- Avoid bundler-only patterns in plain HTML (ESM imports, `import.meta`, etc.) unless you add a bundler.

See:
- [Get Started](../get-started.md)
- [Get Started (official)](../references/get-started-official.md)
