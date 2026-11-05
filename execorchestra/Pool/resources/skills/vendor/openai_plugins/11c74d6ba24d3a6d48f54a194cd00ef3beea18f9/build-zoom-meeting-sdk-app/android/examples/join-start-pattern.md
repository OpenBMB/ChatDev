# Android Join/Start Pattern

## Join (attendee)

1. Backend creates short-lived SDK signature/JWT.
2. App initializes SDK and verifies init callback success.
3. App executes join with normalized meeting number + passcode.
4. App subscribes to meeting status callbacks before join call returns.

## Start (host)

1. Backend resolves host token (`ZAK`) + role-aware signature.
2. App executes start flow and validates host privilege errors explicitly.
3. App applies host-only features conditionally (recording, management controls).

## Guardrails

- Do not hardcode secret in app.
- Normalize meeting identifiers as strings of digits.
- Treat SDK callback thread behavior as asynchronous; avoid UI blocking.
