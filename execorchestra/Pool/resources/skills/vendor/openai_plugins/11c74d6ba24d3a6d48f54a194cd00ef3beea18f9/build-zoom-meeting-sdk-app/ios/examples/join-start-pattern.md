# iOS Join/Start Pattern

## Join (attendee)

1. Request short-lived signature from backend.
2. Initialize/auth SDK and verify callback success.
3. Call join with meeting number/passcode/display name.
4. Observe meeting status and user/video delegate events.

## Start (host)

1. Backend provides host `ZAK` + role-aware signature.
2. Call start path with host token.
3. Validate host-only feature permissions before showing controls.

## Guardrails

- Do not put SDK secret in iOS app bundle.
- Register delegates before initiating meeting transitions.
- Persist minimal state needed for background recovery.
