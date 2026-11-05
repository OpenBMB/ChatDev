# Meeting SDK iOS Guide

## Scope

iOS Meeting SDK integration for init/auth, default/custom UI, meeting join/start, and in-meeting features.

## Validation Snapshot

- Docs coverage includes: setup/get-started, default UI and custom UI feature tracks, PKCE/start/join/auth, FAQ/error-code pages.
- API reference snapshot includes class/protocol maps, file references, and member lists.
- Local package checked: `zoom-sdk-ios-6.7.5.33005` with `MobileRTCSample` and Objective-C sample presenters.

## Practical Guidance

1. Achieve stable default UI join path first.
2. Add host-start and advanced features after baseline is stable.
3. Move to custom UI only where UX requires it.
4. Add explicit permission and audio route diagnostics.
