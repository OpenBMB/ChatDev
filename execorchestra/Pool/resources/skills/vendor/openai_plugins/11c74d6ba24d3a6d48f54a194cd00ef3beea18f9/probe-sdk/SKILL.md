---
name: probe-sdk
description: Use when using Probe SDK.
---

# Zoom Probe SDK

Use this skill when the app needs readiness checks before a user joins a meeting or video session.

## Workflow

1. Define the preflight gate: browser support, camera, microphone, speaker, network, CPU, or diagnostic report.
2. Run diagnostics before the Meeting SDK or Video SDK join flow.
3. Decide whether failed checks should block join, warn the user, or capture support telemetry.
4. Keep probe results separate from meeting/session tokens and avoid sending unnecessary device details downstream.
5. Debug by isolating browser permissions, device enumeration, HTTPS requirements, firewall behavior, and unsupported environments.

## References

- Full preserved guide: [references/full-guide.md](references/full-guide.md)
- Probe overview: [probe-sdk.md](probe-sdk.md)
- Architecture and lifecycle: [concepts/architecture-and-lifecycle.md](concepts/architecture-and-lifecycle.md)
- Diagnostic page pattern: [examples/diagnostic-page-pattern.md](examples/diagnostic-page-pattern.md)
- Network pattern: [examples/comprehensive-network-pattern.md](examples/comprehensive-network-pattern.md)
- Common issues: [troubleshooting/common-issues.md](troubleshooting/common-issues.md)
