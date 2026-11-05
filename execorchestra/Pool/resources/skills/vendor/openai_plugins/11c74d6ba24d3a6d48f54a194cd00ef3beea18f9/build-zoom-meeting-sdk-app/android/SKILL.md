---
name: zoom-meeting-sdk-android
description: |
  Zoom Meeting SDK for Android native apps. Use when embedding Zoom meetings in Android with
  default/custom UI, PKCE + SDK auth, join/start flows, and Meeting SDK API integration.
---

# Zoom Meeting SDK (Android)

Use this skill when building Android apps with embedded Zoom meeting capabilities.

## Start Here

1. [android.md](android.md)
2. [concepts/lifecycle-workflow.md](concepts/lifecycle-workflow.md)
3. [concepts/architecture.md](concepts/architecture.md)
4. [examples/join-start-pattern.md](examples/join-start-pattern.md)
5. [scenarios/high-level-scenarios.md](scenarios/high-level-scenarios.md)
6. [references/android-reference-map.md](references/android-reference-map.md)
7. [references/environment-variables.md](references/environment-variables.md)
8. [references/versioning-and-compatibility.md](references/versioning-and-compatibility.md)
9. [troubleshooting/common-issues.md](troubleshooting/common-issues.md)

## Routing Notes

- Use **default UI** first for first successful join/start validation.
- Move to **custom UI** once auth, meeting state transitions, and permissions are stable.
- For signature/JWT mistakes, chain with [../../oauth/SKILL.md](../../oauth/SKILL.md) and [../references/signature-playbook.md](../references/signature-playbook.md).

## Key Sources

- Docs: https://developers.zoom.us/docs/meeting-sdk/android/
- API reference: https://marketplacefront.zoom.us/sdk/meeting/android/index.html
- Broader guide: [../SKILL.md](../SKILL.md)

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
