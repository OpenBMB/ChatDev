---
name: zoom-meeting-sdk-react-native
description: Zoom Meeting SDK for React Native. Use when embedding Zoom meetings in React Native iOS/Android apps with @zoom/meetingsdk-react-native, JWT auth, join/start flows, platform setup, and native bridge troubleshooting.
---

# Zoom Meeting SDK (React Native)

Use this skill when building React Native apps that need embedded Zoom meeting join/start flows.

## Quick Links

1. **[Lifecycle Workflow](concepts/lifecycle-workflow.md)** - init -> auth -> join/start -> in-meeting -> cleanup
2. **[Architecture](concepts/architecture.md)** - JS wrapper, native bridge, iOS/Android SDK layers
3. **[High-Level Scenarios](concepts/high-level-scenarios.md)** - practical product patterns
4. **[Setup Guide](examples/setup-guide.md)** - install package + platform requirements
5. **[Join Meeting Pattern](examples/join-meeting-pattern.md)** - JWT + meetingNumber + password
6. **[Start Meeting Pattern](examples/start-meeting-pattern.md)** - ZAK-based host start
7. **[SKILL.md](SKILL.md)** - full navigation

## Core APIs (Wrapper)

From `@zoom/meetingsdk-react-native` wrapper surface:

- `initSDK(config)`
- `isInitialized()`
- `updateMeetingSetting(config)`
- `joinMeeting(config)`
- `startMeeting(config)`
- `cleanup()`

See: **[Wrapper API](references/wrapper-api.md)**

## Critical Notes

- You still need native iOS/Android Meeting SDK dependencies configured.
- `joinMeeting` and `startMeeting` return numeric status/error codes from native layer.
- For host start flow, pass `zoomAccessToken` (ZAK).
- Keep JWT generation on backend, never embed SDK secret in app.
- Current docs note React Native support up to `0.75.4`; Expo is not supported.

## Platform Guides

- **[iOS Setup](references/ios-setup.md)** - Podfile, optional ReplayKit/app group fields
- **[Android Setup](references/android-setup.md)** - Gradle dependency + options mapping
- **[Native Bridge Notes](references/native-bridge-notes.md)** - behavior differences and gotchas

## Troubleshooting

- **[Common Issues](troubleshooting/common-issues.md)**
- **[Version Drift](troubleshooting/version-drift.md)**
- **[Deprecated/Contradictions](troubleshooting/deprecated-and-contradictions.md)**

## Related Skills

- **[zoom-meeting-sdk](../SKILL.md)** - parent Meeting SDK hub
- **[zoom-oauth](../../oauth/SKILL.md)** - auth flow and token management
- **[zoom-general](../../general/SKILL.md)** - cross-product architecture decisions

## Documentation Index

### Start Here

1. [SKILL.md](SKILL.md)
2. [Lifecycle Workflow](concepts/lifecycle-workflow.md)
3. [Architecture](concepts/architecture.md)
4. [Setup Guide](examples/setup-guide.md)

### Concepts

- [Lifecycle Workflow](concepts/lifecycle-workflow.md)
- [Architecture](concepts/architecture.md)
- [Auth and Token Model](concepts/auth-and-token-model.md)
- [High-Level Scenarios](concepts/high-level-scenarios.md)

### Examples

- [Setup Guide](examples/setup-guide.md)
- [Join Meeting Pattern](examples/join-meeting-pattern.md)
- [Start Meeting Pattern](examples/start-meeting-pattern.md)
- [Provider Hook Pattern](examples/provider-hook-pattern.md)

### References

- [Wrapper API](references/wrapper-api.md)
- [Android Setup](references/android-setup.md)
- [iOS Setup](references/ios-setup.md)
- [Native Bridge Notes](references/native-bridge-notes.md)
- [Official Sources](references/official-sources.md)

### Troubleshooting

- [Common Issues](troubleshooting/common-issues.md)
- [Version Drift](troubleshooting/version-drift.md)
- [Deprecated and Contradictions](troubleshooting/deprecated-and-contradictions.md)

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
