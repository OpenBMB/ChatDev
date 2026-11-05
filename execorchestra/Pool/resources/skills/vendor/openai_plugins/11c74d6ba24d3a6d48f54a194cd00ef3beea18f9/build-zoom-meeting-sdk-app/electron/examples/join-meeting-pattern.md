# Join Meeting Pattern

## Flow

1. Collect meeting number, display name, passcode/credential strategy.
2. Ensure SDK auth completed.
3. Call join/start meeting API via meeting service.
4. Wait for in-meeting callbacks.
5. Initialize required controllers (audio/video/chat/share/participants).

## Operational checks

- Validate meeting number format before SDK call.
- Normalize role-specific fields for attendee vs host start flows.
- Apply settings defaults (audio/video/share) before join when supported.
