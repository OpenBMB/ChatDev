---
name: zoom-contact-center-ios
description: "Zoom Contact Center SDK for iOS. Use for native iOS chat/video/ZVA/scheduled callback integrations, app lifecycle bridging, rejoin flow, and callback handling."
---

# Zoom Contact Center SDK - iOS

Official docs:
- https://developers.zoom.us/docs/contact-center/ios/
- https://marketplacefront.zoom.us/sdk/contact/ios/index.html

## Quick Links

1. [concepts/sdk-lifecycle.md](concepts/sdk-lifecycle.md)
2. [examples/service-patterns.md](examples/service-patterns.md)
3. [references/ios-reference-map.md](references/ios-reference-map.md)
4. [troubleshooting/common-issues.md](troubleshooting/common-issues.md)

## SDK Surface Summary

- Manager: `ZoomCCInterface.sharedInstance()`
- Context: `ZoomCCContext`
- Items: `ZoomCCItem`
- Services:
- `chatService`
- `zvaService`
- `videoService`
- `scheduledCallbackService`

## Hard Guardrails

- Set `ZoomCCContext` before channel operations.
- Forward app lifecycle calls (`appDidBecomeActive`, `appDidEnterBackgroud`, `appWillResignActive`, `appWillTerminate`).
- Use item-based initialization for channels.
- Keep rejoin URL handling connected to the video service path.

## Common Chains

- Contact Center apps in Zoom client: [../../zoom-apps-sdk/SKILL.md](../../zoom-apps-sdk/SKILL.md)
- OAuth and identity: [../../oauth/SKILL.md](../../oauth/SKILL.md)

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
