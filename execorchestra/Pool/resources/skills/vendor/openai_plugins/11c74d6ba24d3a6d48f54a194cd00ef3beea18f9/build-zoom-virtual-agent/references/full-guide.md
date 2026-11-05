# /build-zoom-virtual-agent

Background reference for Zoom Virtual Agent across:
- Web campaign/chat embeds.
- Android WebView wrappers.
- iOS WKWebView wrappers.
- Knowledge-base sync and custom API ingestion.

Official docs:
- https://developers.zoom.us/docs/virtual-agent/
- https://developers.zoom.us/docs/virtual-agent/web/
- https://developers.zoom.us/docs/virtual-agent/android/
- https://developers.zoom.us/docs/virtual-agent/ios/

## Routing Guardrail

- If the user is implementing Contact Center app surfaces inside Zoom client, chain with [../contact-center/SKILL.md](../../contact-center/SKILL.md).
- If the user needs backend knowledge-base CRUD or automation scripts, chain with [../rest-api/SKILL.md](../../rest-api/SKILL.md) and [../oauth/SKILL.md](../../oauth/SKILL.md).
- If the user asks only for website bot embed and campaign controls, stay on [web/SKILL.md](../web/SKILL.md).
- If the user asks for mobile native wrappers around web chat, route to [android/SKILL.md](../android/SKILL.md) or [ios/SKILL.md](../ios/SKILL.md).

## Quick Links

1. [concepts/architecture-and-lifecycle.md](../concepts/architecture-and-lifecycle.md)
2. [scenarios/high-level-scenarios.md](../scenarios/high-level-scenarios.md)
3. [references/versioning-and-drift.md](../references/versioning-and-drift.md)
4. [references/samples-validation.md](../references/samples-validation.md)
5. [references/environment-variables.md](../references/environment-variables.md)
6. [troubleshooting/common-drift-and-breaks.md](../troubleshooting/common-drift-and-breaks.md)
7. [RUNBOOK.md](../RUNBOOK.md)

Platform skills:
- [web/SKILL.md](../web/SKILL.md)
- [android/SKILL.md](../android/SKILL.md)
- [ios/SKILL.md](../ios/SKILL.md)

## Common Lifecycle Pattern

1. Configure campaign or entry ID in Virtual Agent admin.
2. Initialize SDK in web or WebView container.
3. Wait for readiness (`zoomCampaignSdk:ready` or `waitForReady()`) before calling APIs.
4. Register bridge handlers (`exitHandler`, `commonHandler`, `support_handoff`) when native orchestration is needed.
5. Handle conversation lifecycle (`engagement_started`, `engagement_ended`) and UI state.
6. End chat (`endChat`) and clean up listeners.

## High-Level Scenarios

- Website campaign launcher with contextual customer attributes.
- Mobile app WebView chat with native close/handoff bridge.
- External URL handling via system browser vs in-app browser policy.
- Knowledge-base sync from external systems using custom API connector.
- Cross-team support flow that escalates from bot to live support with handoff payload.

## Chaining

- Contact Center app/web/mobile patterns: [../contact-center/SKILL.md](../../contact-center/SKILL.md)
- OAuth app setup and tokens: [../oauth/SKILL.md](../../oauth/SKILL.md)
- API workflows for KB automation: [../rest-api/SKILL.md](../../rest-api/SKILL.md)
- Event-driven backend follow-up: [../webhooks/SKILL.md](../../webhooks/SKILL.md)

## Operations

- [RUNBOOK.md](../RUNBOOK.md) - 5-minute preflight and debugging checklist.
