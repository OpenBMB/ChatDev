# Lifecycle Workflow

Recommended runtime sequence for Electron Meeting SDK integrations:

1. Initialize SDK wrapper (`zoom_sdk` level init).
2. Authenticate with SDK JWT through auth service.
3. Configure meeting parameters and settings controllers.
4. Join or start meeting through meeting service.
5. Bind meeting controllers/events (audio, video, participants, chat, share).
6. Optional raw data and advanced modules.
7. Leave meeting and release SDK resources cleanly.

## Sequence Diagram

```text
Electron App
  -> initSDK
  -> authWithJwt
  -> create/get meeting service
  -> joinMeeting/startMeeting
  -> subscribe callbacks
  -> apply controller actions
  -> leaveMeeting
  -> cleanup
```

## Why this order matters

- Controller operations before successful auth or join usually fail or no-op.
- Settings should be applied before meeting join where possible.
- Cleanup prevents stale state and callback leaks on app relaunch.
