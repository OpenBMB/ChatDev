---
name: zoom-virtual-agent-android
description: "Zoom Virtual Agent Android integration via WebView. Use for Java/Kotlin bridge callbacks, native URL handling, support_handoff relay, and lifecycle-safe embedding."
---

# Zoom Virtual Agent - Android

Official docs:
- https://developers.zoom.us/docs/virtual-agent/android/

## Quick Links

1. [concepts/webview-lifecycle.md](concepts/webview-lifecycle.md)
2. [examples/js-bridge-patterns.md](examples/js-bridge-patterns.md)
3. [references/android-reference-map.md](references/android-reference-map.md)
4. [troubleshooting/common-issues.md](troubleshooting/common-issues.md)

## Integration Model

- Host campaign URL in Android WebView.
- Inject runtime context (`window.zoomCampaignSdkConfig`).
- Register JavaScript bridge for `exitHandler`, `commonHandler`, `support_handoff`.
- Apply URL policy via `shouldOverrideUrlLoading` and optional multi-window callbacks.

## Hard Guardrails

- Initialize handlers before expecting JS callbacks.
- Treat legacy `openURL` command handling as compatibility path only.
- Prefer DOM links or `window.open` handling plus explicit native routing.

## Chaining

- Product-level patterns: [../SKILL.md](../SKILL.md)
- Contact Center mobile scope: [../../contact-center/android/SKILL.md](../../contact-center/android/SKILL.md)
