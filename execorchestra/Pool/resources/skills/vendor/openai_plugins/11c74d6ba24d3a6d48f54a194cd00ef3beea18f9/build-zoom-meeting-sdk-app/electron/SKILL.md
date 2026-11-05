---
name: zoom-meeting-sdk-electron
description: |
  Zoom Meeting SDK for Electron desktop applications. Use when embedding Zoom meetings in an Electron app
  with the Node addon wrapper, JWT auth, join/start flows, settings controllers, and raw data integration.
---

# Zoom Meeting SDK (Electron)

Use this skill when building Electron desktop apps that embed Zoom Meeting SDK capabilities through the Electron wrapper.

## Start Here

1. **[Lifecycle Workflow](concepts/lifecycle-workflow.md)** - init -> auth -> join/start -> in-meeting -> cleanup
2. **[SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)** - service/controller/event model in Electron
3. **[Setup Guide](examples/setup-guide.md)** - dependency and build expectations
4. **[Authentication Pattern](examples/authentication-pattern.md)** - SDK JWT generation and auth callbacks
5. **[Join Meeting Pattern](examples/join-meeting-pattern.md)** - start/join meeting execution flow
6. **[SKILL.md](SKILL.md)** - full navigation

## Core Notes

- Electron wrapper is built on top of native Meeting SDK with Node addon bridges.
- Keep SDK key/secret server-side; generate SDK JWT on backend.
- Feature support differs by platform/version; check module docs before implementation.
- Raw data and IPC patterns require explicit security hardening in production.

## References

- [Electron API Reference Index](references/electron-reference.md)
- [Module Map](references/module-map.md)
- [Deprecated and Contradictions](troubleshooting/deprecated-and-contradictions.md)

## Related Skills

- [zoom-meeting-sdk](../SKILL.md)
- [zoom-oauth](../../oauth/SKILL.md)
- [zoom-general](../../general/SKILL.md)


## Merged from meeting-sdk/electron/SKILL.md

# Zoom Meeting SDK Electron - Documentation Index

## Start Here

1. [SKILL.md](SKILL.md)
2. [Lifecycle Workflow](concepts/lifecycle-workflow.md)
3. [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)
4. [Setup Guide](examples/setup-guide.md)

## Concepts

- [Lifecycle Workflow](concepts/lifecycle-workflow.md)
- [SDK Architecture Pattern](concepts/sdk-architecture-pattern.md)
- [High-Level Scenarios](concepts/high-level-scenarios.md)

## Examples

- [Setup Guide](examples/setup-guide.md)
- [Authentication Pattern](examples/authentication-pattern.md)
- [Join Meeting Pattern](examples/join-meeting-pattern.md)
- [Raw Data Pattern](examples/raw-data-pattern.md)

## References

- [Electron API Reference](references/electron-reference.md)
- [Module Map](references/module-map.md)

## Troubleshooting

- [Common Issues](troubleshooting/common-issues.md)
- [Version Drift](troubleshooting/version-drift.md)
- [Deprecated and Contradictions](troubleshooting/deprecated-and-contradictions.md)

## Operations

- [RUNBOOK.md](RUNBOOK.md) - 5-minute preflight and debugging checklist.
