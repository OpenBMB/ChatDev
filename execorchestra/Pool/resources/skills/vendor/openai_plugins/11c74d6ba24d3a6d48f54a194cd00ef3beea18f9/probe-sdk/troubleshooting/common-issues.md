# Probe SDK Common Issues

## Permissions denied or missing streams

Symptoms:
- Permission request returns error.
- No stream returned for diagnostics.

Checks:
- HTTPS/secure context is used.
- Not in insecure context (`http://`, mixed content, blocked iframe permissions policy).
- Browser-level camera/mic permissions are granted.
- Device is not locked by another app.

## No media devices detected

Symptoms:
- `requestMediaDevices` returns empty sets for mic/camera/speaker.

Checks:
- OS-level privacy settings allow browser device access.
- External USB/Bluetooth devices are connected before page load.
- Virtual device drivers are installed and recognized by the browser.
- Browser enterprise policies are not blocking media device enumeration.

## Video diagnostic fails to render

Symptoms:
- `diagnoseVideo` error or blank target.

Checks:
- Renderer option key and target match selected renderer.
- `video-tag` renderer uses HTMLVideoElement target.
- WebGL/WebGL2/WebGPU renderers use canvas/offscreen canvas target.

## Network diagnostic never completes

Symptoms:
- `startToDiagnose` does not return final report in expected duration.

Checks:
- `probeDuration` and `connectTimeout` values are reasonable.
- Domain and optional JS/WASM URLs are reachable.
- Browser/network policies do not block probing paths.

## Report field mismatch in app code

Symptoms:
- Undefined fields when parsing final report.

Checks:
- Add compatibility adapter for `basicInfo` vs `basicInfoEntries`.
- Add compatibility adapter for `supportedFeatures` vs `featureEntries`.
- Pin SDK version and align parser tests to that version.

## Residual resource usage after diagnostics

Symptoms:
- Camera indicator remains active.
- Memory/network usage persists after leaving page.

Checks:
- Call `stopToDiagnoseVideo` and/or `releaseMediaStream`.
- Call `stopToDiagnose` on early exit.
- Call `cleanup()` on route/page teardown.
