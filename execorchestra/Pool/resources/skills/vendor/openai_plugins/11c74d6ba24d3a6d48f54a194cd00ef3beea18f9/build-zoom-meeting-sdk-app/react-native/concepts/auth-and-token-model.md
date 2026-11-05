# Auth and Token Model

## Token types used by wrapper

- `jwtToken` in `initSDK`: Meeting SDK JWT (for SDK authorization)
- `zoomAccessToken` in `startMeeting`: ZAK token for host start

## Security model

- Generate tokens server-side only.
- Never ship SDK secret in the app.
- Keep JWT short-lived and rotate aggressively.

## Flow guidance

- Participant join: `initSDK(jwtToken)` + `joinMeeting(meetingNumber, password)`
- Host start: `initSDK(jwtToken)` + `startMeeting(zoomAccessToken=ZAK, meetingNumber)`
