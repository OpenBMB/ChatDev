# Zoom Meeting SDK Environment Variables

## Standard `.env` keys

| Variable | Required | Used for | Where to find |
| --- | --- | --- | --- |
| `ZOOM_SDK_KEY` | Yes | Meeting SDK signature issuer identity | Zoom Marketplace -> Meeting SDK app -> App Credentials |
| `ZOOM_SDK_SECRET` | Yes | Signature generation secret | Zoom Marketplace -> Meeting SDK app -> App Credentials |
| `ZOOM_MEETING_NUMBER` | Per flow | Meeting to join/start | Zoom meeting invite, Zoom web portal, or Meetings API |
| `ZOOM_MEETING_PASSWORD` | Conditional | Meeting passcode | Meeting invite details / Meetings API |
| `ZOOM_ROLE` | Conditional | Signature role (`0` attendee, `1` host) | Set by your app logic |
| `ZOOM_ZAK` | Host flows only | Host authorization token for start flows | Generate via Zoom REST API user token endpoint |

## Runtime-only values

- `MEETING_SDK_JWT` (generated signature)

Generate server-side and keep short-lived.

## Notes

- Never expose `ZOOM_SDK_SECRET` in frontend/mobile clients.

## Platform-Specific References

- Android: [../android/references/environment-variables.md](../android/references/environment-variables.md)
- iOS: [../ios/references/environment-variables.md](../ios/references/environment-variables.md)
- macOS: [../macos/references/environment-variables.md](../macos/references/environment-variables.md)
- Unreal: [../unreal/references/environment-variables.md](../unreal/references/environment-variables.md)
