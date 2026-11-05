# macOS Join/Start Pattern

## Join (attendee)

1. Get short-lived signature from backend.
2. Initialize/auth SDK and verify callback result.
3. Join with meeting number + passcode.
4. Register required meeting delegates before user interaction.

## Start (host)

1. Backend provides host `ZAK` + role-aware signature.
2. Start flow executes with host token.
3. Host-only controls enabled after privilege verification.

## Guardrails

- Keep SDK secret off client.
- Validate delegate callbacks under both default and custom UI.
- Explicitly handle leave/end transitions for cleanup.
