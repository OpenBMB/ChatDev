---
name: zoom-contact-center-web
description: "Zoom Contact Center SDK for Web. Use for web chat/video/campaign embeds, engagement event handling, app-context integrations, and Smart Embed postMessage workflows."
---

# Zoom Contact Center SDK - Web

Official docs:
- https://developers.zoom.us/docs/contact-center/web/
- https://developers.zoom.us/docs/contact-center/web/sdk-reference/

## Quick Links

1. [concepts/lifecycle-and-events.md](concepts/lifecycle-and-events.md)
2. [examples/app-context-and-state.md](examples/app-context-and-state.md)
3. [references/web-reference-map.md](references/web-reference-map.md)
4. [troubleshooting/common-issues.md](troubleshooting/common-issues.md)

## Integration Modes

1. Contact Center App in Zoom client:
- Zoom Apps SDK engagement APIs/events.

2. External website embed:
- Campaign SDK/web scripts (`zoomCampaignSdk` pattern).
- Video client initialization pattern.

3. Smart Embed:
- iframe + `postMessage` event contract.

## Hard Guardrails

- For campaign SDK, gate calls behind `zoomCampaignSdk:ready`.
- Persist state by `engagementId`.
- Expect context switching and background app behavior.
- Validate CSP and allow-list settings before debugging logic.

## Chaining

- For in-client app APIs and auth flows: [../../zoom-apps-sdk/SKILL.md](../../zoom-apps-sdk/SKILL.md)
- For identity and OAuth: [../../oauth/SKILL.md](../../oauth/SKILL.md)
- For cobrowse workflow: [../../cobrowse-sdk/SKILL.md](../../cobrowse-sdk/SKILL.md)

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
