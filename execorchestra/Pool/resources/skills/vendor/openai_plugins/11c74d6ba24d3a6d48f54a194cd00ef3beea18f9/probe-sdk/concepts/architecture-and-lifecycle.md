# Probe SDK Architecture and Lifecycle

## Purpose

Probe SDK answers one question before real-time media starts:
- `Can this user/device/network support an acceptable experience?`

## Architecture Model

```text
User Browser
  -> Probe SDK (Prober, Reporter)
     -> Media APIs (permissions/devices)
     -> Renderer path (video tag / WebGL / WebGL2 / WebGPU)
     -> Network probing runtime (JS/WASM + domain endpoint)
  -> Diagnostic stats stream + final report
  -> UI gating decision (allow join / warn / block)
```

## Lifecycle Workflow

1. Initialize
- `const prober = new Prober()`
- `const reporter = new Reporter()` (optional for standalone feature/basic reports)

2. Permissions and devices
- `requestMediaDevicePermission({ audio: true, video: true })`
- `requestMediaDevices()`

3. Targeted diagnostics
- `diagnoseAudio(inputConstraints, outputConstraints, duration)`
- `diagnoseVideo(constraints, { rendererType, target })`

4. Comprehensive diagnostics
- `startToDiagnose(jsUrl, wasmUrl, config, statsListener)`
- stream live stats and wait for final report payload

5. Tear-down and cleanup
- `stopToDiagnose()` / `stopToDiagnoseVideo(stream?)`
- `releaseMediaStream(stream)`
- `cleanup()`

## Readiness Policy Calibration

- Keep readiness policy product-specific and versioned (for example, `policy_version=2026-02`).
- Define explicit thresholds per output signal (`allow`, `warn`, `block`) for network/audio/video outcomes.
- Recalibrate policy thresholds whenever upgrading Probe SDK or changing browser support baseline.
- Log policy version with each final report so support can reproduce decisions.

## Data Model Notes

Typical final report includes:
- network diagnostic result
- basic info entries
- supported feature entries

Field naming may vary by version (`basicInfo` vs `basicInfoEntries`, `supportedFeatures` vs `featureEntries`), so version-aware adapters are recommended.
