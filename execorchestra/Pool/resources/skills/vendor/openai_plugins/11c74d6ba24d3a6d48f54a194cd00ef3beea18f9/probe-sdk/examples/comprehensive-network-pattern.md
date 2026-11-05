# Comprehensive Network Diagnostic Pattern

```javascript
import { Prober } from "@zoom/probesdk";

const prober = new Prober();

export async function runComprehensiveDiagnostic() {
  const jsUrl = "";   // optional custom hosted prober.js
  const wasmUrl = ""; // optional custom hosted prober.wasm loader

  const config = {
    probeDuration: 120 * 1000,
    connectTimeout: 20 * 1000,
    domain: "zoom.us",
  };

  const statsHistory = [];

  const report = await prober.startToDiagnose(jsUrl, wasmUrl, config, (stats) => {
    statsHistory.push(stats);
  });

  return {
    report,
    statsHistory,
  };
}

export async function stopEarlyAndCollect() {
  const partial = await prober.stopToDiagnose();
  prober.cleanup();
  return partial;
}
```

## Notes

- Use stats callback for realtime charting; keep callback lightweight.
- Wrap final report fields behind adapter layer for version drift.
