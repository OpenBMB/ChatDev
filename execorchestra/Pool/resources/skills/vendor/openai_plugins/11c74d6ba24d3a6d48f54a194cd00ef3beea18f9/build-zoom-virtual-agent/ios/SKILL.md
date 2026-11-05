---
name: zoom-virtual-agent-ios
description: "Zoom Virtual Agent iOS integration via WKWebView. Use for Swift/Objective-C script injection, message handlers, support_handoff relay, and URL routing policies."
---

# Zoom Virtual Agent - iOS

Official docs:
- https://developers.zoom.us/docs/virtual-agent/ios/

## Quick Links

1. [concepts/webview-lifecycle.md](concepts/webview-lifecycle.md)
2. [examples/js-bridge-patterns.md](examples/js-bridge-patterns.md)
3. [references/ios-reference-map.md](references/ios-reference-map.md)
4. [troubleshooting/common-issues.md](troubleshooting/common-issues.md)

## Integration Model

- Load campaign URL in `WKWebView`.
- Inject `window.zoomCampaignSdkConfig` using `WKUserScript`.
- Register message handlers for exit/common/handoff flows.
- Handle URL behavior in navigation delegates (`in-app`, `SFSafariViewController`, or system browser).

## Hard Guardrails

- Register scripts and handlers before web interaction.
- Handle iOS 14.5+ download behavior where needed.
- Keep deprecated `openURL` command support as fallback only.

## Chaining

- Product-level patterns: [../SKILL.md](../SKILL.md)
- Contact Center mobile scope: [../../contact-center/ios/SKILL.md](../../contact-center/ios/SKILL.md)
