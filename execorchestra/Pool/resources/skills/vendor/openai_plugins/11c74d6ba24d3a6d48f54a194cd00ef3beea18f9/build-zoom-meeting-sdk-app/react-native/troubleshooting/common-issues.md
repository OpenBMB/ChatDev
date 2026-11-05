# Common Issues

## `joinMeeting` fails immediately

- Validate meeting number format and password.
- Confirm SDK initialization succeeded first.
- Check JWT validity window.

## `startMeeting` fails

- Verify `zoomAccessToken` (ZAK) is present and unexpired.
- Ensure host account and meeting ownership match ZAK context.

## Provider/hook misuse

- Ensure components calling `useZoom()` are wrapped in `ZoomSDKProvider`.

## iOS-specific init issues

- Confirm optional fields (`bundleResPath`, `appGroupId`, `replaykitBundleIdentifier`) only when needed and correctly configured.

## Android language crash risk

- Avoid passing partial/invalid language values to `updateMeetingSetting`.
