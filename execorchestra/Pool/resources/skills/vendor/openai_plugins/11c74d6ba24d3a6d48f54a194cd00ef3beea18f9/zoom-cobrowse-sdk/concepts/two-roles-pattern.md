# Two Roles Pattern

Zoom Cobrowse uses two roles:

- `role_type=1`: customer session
- `role_type=2`: agent session

Use separate JWTs for each role and keep token generation on the server.

## What Is Usually Created

In most real implementations, you create these objects in order:

1. **Customer session record** (server-side)
   - `session_id`
   - generated PIN
   - status (`active`/`revoked`)
   - expiry timestamp
2. **Customer token** (`role_type=1`)
   - used by customer browser SDK to start/share session
3. **Agent token** (`role_type=2`)
   - created after PIN validation
   - used to load agent desk iframe or custom agent UI

## PIN Source of Truth

In practice, the PIN you should hand to agents is the value emitted by customer SDK event:

- `session.on("pincode_updated", ...)`

Do not rely on placeholder/provisional PIN values from pre-start backend records for user-facing flows.
Always show one clearly labeled PIN in UI (for example, "Support PIN") and reuse that same value in agent links.

## Recommended Endpoint Split

- `POST /api/customer/start` -> create session + customer token + PIN
- `POST /api/agent/connect` -> validate PIN + issue agent token
- `POST /api/session/revoke` -> end session
- `GET /api/session/list` -> operational visibility

See:
- [Get Started](../get-started.md)
- [Authorization (official)](../references/authorization-official.md)
