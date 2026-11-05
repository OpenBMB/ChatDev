# Diagnostic Page Pattern

```javascript
import { Prober } from "@zoom/probesdk";

const prober = new Prober();

export async function runDeviceChecks(videoCanvas) {
  const permission = await prober.requestMediaDevicePermission({ audio: true, video: true });
  if (permission.error) return { ok: false, stage: "permission", error: permission.error };

  const devices = await prober.requestMediaDevices();
  if (devices.error) return { ok: false, stage: "devices", error: devices.error };

  const cameraId = devices.devices?.find((d) => d.kind === "videoinput")?.deviceId || "default";
  const micId = devices.devices?.find((d) => d.kind === "audioinput")?.deviceId || "default";
  const speakerId = devices.devices?.find((d) => d.kind === "audiooutput")?.deviceId;

  const audioResult = await prober.diagnoseAudio(
    { audio: { deviceId: micId }, video: false },
    { audio: { deviceId: speakerId }, video: false },
    5000
  );

  const videoResult = await prober.diagnoseVideo(
    { video: { deviceId: cameraId } },
    { rendererType: 2, target: videoCanvas }
  );

  return { ok: true, devices: devices.devices, audioResult, videoResult };
}

export function cleanupStream(stream) {
  prober.releaseMediaStream(stream);
  prober.cleanup();
}
```

## Notes

- `rendererType` target requirements must match chosen renderer.
- Always release media streams when diagnostics are complete.
