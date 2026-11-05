# macOS Lifecycle Workflow

## Core Sequence

1. App startup and SDK initialization.
2. SDK auth callback success.
3. Join/start flow selection.
4. Meeting controller registration and in-meeting feature activation.
5. Leave/end handling.
6. SDK cleanup and process teardown.

## Failure Domains

- Auth/signature mismatch.
- Join/start parameter mismatch.
- Delegate/controller ordering issues in custom UI mode.
- Feature-level permission or role mismatch (recording, breakout, webinar).
