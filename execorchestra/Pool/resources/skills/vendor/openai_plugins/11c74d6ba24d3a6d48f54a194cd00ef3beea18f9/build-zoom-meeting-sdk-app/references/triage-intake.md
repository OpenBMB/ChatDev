---
title: "Meeting SDK Triage Intake (What to Ask First)"
---

# Meeting SDK Triage Intake (What to Ask First)

This is the fastest way to turn a vague “Meeting SDK isn’t working” question into an answer.

## 1) Which SDK + Which Platform?

- Platform: `web` | `android` | `ios` | `react-native` | `electron` | `windows` | `macos` | `linux`
- Exact SDK package/version (and Zoom client version if relevant)

## 2) Web: Client View vs Component View

Ask explicitly which one they’re using:

- **Client View (CDN)**: uses `ZoomMtg.*` (callbacks)
- **Component View (npm)**: uses `ZoomMtgEmbedded.createClient()` (promises)

These have different APIs and different customization limitations.

## 3) Join vs Start, and Role

- Are you **joining** as an attendee (`role=0`) or **starting** as host (`role=1`)?
- If starting as host, do you have a **ZAK** (Zoom Access Key) when required by the platform/SDK flow?

## 4) Inputs (Copy/Paste)

Request the exact values and formats (redact secrets):

- `meetingNumber` (digits only)
- `passcode` / `password` (and on Web Client View, confirm they used `passWord` key name)
- `userName`
- `sdkKey` (OK to share)
- signature generation code (server-side) and the payload fields used (`mn`, `role`, `iat`, `exp`, `tokenExp`)

## 5) The Symptom

Pick one bucket:

- signature/auth: “Invalid signature”, “signature expired”, “invalid parameter”
- web environment: “Joining meeting timeout”, “organization disabled access”, “SharedArrayBuffer”, “gallery view”
- UI/customization: “hide meeting info”, “hide passcode/invite URL”, “remove buttons”
- media: “no audio/video”, “screen share problems”, “performance/cpu”

## 6) Minimal Repro + Logs

- Minimal steps to reproduce
- SDK logs (see `general/references/sdk-logs-troubleshooting.md`)
- On Web: browser + OS, console errors, and whether corporate proxy/adblock is present
