# Probe SDK 5-Minute Preflight Runbook

Use this before deep debugging.

## Skill Doc Standard Note

- Skill entrypoint is `SKILL.md`.
- This runbook is an operational convention (recommended), not a required skill file.
- API/option naming can drift by version; validate against current Probe SDK reference.

## 1) Confirm Integration Surface

- Confirm this is a web diagnostics use case, not meeting/session join runtime.
- Confirm whether you need only device checks, only network checks, or full diagnostics.
- Confirm renderer target strategy (`video-tag` or canvas-based renderer).

## 2) Confirm Required Inputs

- No Zoom Marketplace credentials are required for core Probe SDK diagnostics.
- Device IDs are required for explicit audio input/output and camera diagnostics.
- For comprehensive network diagnostics, verify optional JS/WASM URL override strategy.

## 3) Confirm Lifecycle Order

1. `requestMediaDevicePermission()`.
2. `requestMediaDevices()`.
3. `diagnoseAudio(...)` / `diagnoseVideo(...)`.
4. `startToDiagnose(jsUrl, wasmUrl, config, statsListener)`.
5. `stopToDiagnose*` and `cleanup()` on exit.

## 4) Confirm Event/State Handling

- Keep stream lifecycle explicit (`releaseMediaStream`).
- Keep stats callback lightweight and avoid blocking UI thread.
- Persist final report snapshot before cleanup.

## 5) Confirm Cleanup + Upgrade Posture

- Always stop active diagnostics before page unload/navigation.
- Re-check renderer option naming and report field names on upgrades.
- Re-check browser compatibility assumptions against current docs.

## 6) Quick Probes

- Permissions prompt appears and resolves expectedly.
- Devices list includes expected microphone/speaker/camera.
- Video diagnostic renders to selected target.
- Network diagnostic emits stats and final report.

## 7) Fast Decision Tree

- No media diagnostics -> permissions denied or insecure context.
- Video diagnostics fail -> renderer/target mismatch or unsupported renderer type.
- Network diagnostic incomplete -> timeout/domain/config mismatch.
- Report schema mismatch -> version drift between docs and installed package.

## 8) Source Checkpoints

### Official docs

- https://developers.zoom.us/docs/probe-sdk/
- https://marketplacefront.zoom.us/sdk/probe/index.html

### Raw docs in repo

- `tools/zoom-crawler/raw-docs/developers.zoom.us/docs/probe-sdk/`
- `tools/zoom-crawler/raw-docs/marketplacefront.zoom.us/sdk/probe/`
