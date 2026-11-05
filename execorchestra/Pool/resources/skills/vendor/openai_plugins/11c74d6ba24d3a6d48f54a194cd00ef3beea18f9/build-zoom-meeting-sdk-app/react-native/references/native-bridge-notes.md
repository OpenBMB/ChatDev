# Native Bridge Notes

## Android bridge

- Uses `ZoomSDK.initialize(...)` with `wrapperType = 2`.
- `joinMeeting` and `startMeeting` resolve numeric result codes.
- Exposes lifecycle hooks but event emitter list is currently empty in bridge.

## iOS bridge

- Initializes `MobileRTC` + auth service (`sdkAuth` with JWT).
- `joinMeeting`/`startMeeting` call native meeting service methods and resolve/reject promises.

## Practical implication

The wrapper currently behaves as command-based API with limited cross-platform event exposure. Build app-level state handling around command results and native UI transitions.
