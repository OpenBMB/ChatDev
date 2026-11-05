# Raw Data Pattern

Raw data flows are advanced and require hardening.

## Typical use cases

- Local AI processing.
- Quality monitoring.
- Compliance capture.

## Pattern

1. Enable raw data module after meeting join.
2. Subscribe to relevant streams.
3. Transfer frames/samples through controlled IPC/data path.
4. Apply backpressure, buffering, and clean shutdown handling.

## Risks

- Performance overhead if frame handling is not bounded.
- Sensitive data exposure if raw buffers are not protected.
- Version mismatch risks in native addon dependencies.
