# iOS High-Level Scenarios

## Scenario 1: Telehealth client app

- Attendee join with strict permission prompts.
- Uses waiting-room and status callbacks for guided UX.
- Records app-level diagnostic events for support triage.

## Scenario 2: Internal host app

- Uses host start flow with `ZAK`.
- Enables moderator tools only after host privilege confirmation.
- Applies policy checks for recording and participant management.

## Scenario 3: Branded custom in-meeting experience

- Starts from default UI parity baseline.
- Adds custom UI modules for selected controls/views.
- Maintains fallback path when advanced features regress after SDK update.
