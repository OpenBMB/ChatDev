# Unreal Lifecycle Workflow

## Core Sequence

1. Plugin/wrapper initialization in Unreal project startup.
2. SDK init + auth sequence (JWT/signature path).
3. Join/start flow.
4. In-meeting event handling through wrapper event interfaces.
5. Cleanup and session/resource release.

## Wrapper-Specific Risk

- Method availability differs between C++ wrapper and Blueprint wrapper.
- Some wrapper methods are modified or newly introduced vs native SDK method behavior.
