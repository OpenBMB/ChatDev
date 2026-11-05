# iOS Lifecycle Workflow

## Core Sequence

1. App launch and permission strategy (camera/mic, optional share path prep).
2. SDK initialization and auth callbacks.
3. Join/start decision branch.
4. In-meeting event wiring (audio/video/chat/share/webinar where needed).
5. Background/foreground transitions and interruption recovery.
6. Leave/end and cleanup.

## Failure Domains

- Expired or mismatched signature data.
- Role/host-token mismatch in start flow.
- App lifecycle interruption (phone call/audio route/background).
- Incomplete delegate registration before meeting transitions.
