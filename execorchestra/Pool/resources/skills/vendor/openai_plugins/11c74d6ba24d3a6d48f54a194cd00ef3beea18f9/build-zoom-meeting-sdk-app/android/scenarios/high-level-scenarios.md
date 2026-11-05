# Android High-Level Scenarios

## Scenario 1: Field-service meeting embed

- Technician app embeds meeting in default UI.
- Uses attendee join tokens from backend.
- Adds device telemetry + service-quality diagnostics.

## Scenario 2: Branded healthcare consult

- Start from default UI for reliability.
- Phase in custom UI for constrained controls and guided workflows.
- Enforce strict permission and foreground-service handling.

## Scenario 3: Training/coaching session app

- Uses breakout room and in-meeting chat flows.
- Tracks lifecycle events for attendance and session analytics.
- Uses migration-safe handling for renamed SDK enums across upgrades.
