# macOS Common Issues

## 1. Join/start flow errors

- Validate signature freshness and role.
- Confirm meeting identifier and passcode mapping.
- Validate host token (`ZAK`) for start path.

## 2. Delegate callback gaps

- Ensure delegate/controller registration happens before feature usage.
- Keep coordinator/service objects strongly referenced through session lifecycle.

## 3. Custom UI regressions

- Verify default UI still works to isolate custom layer issues.
- Re-check rendering and feature-controller dependencies after SDK upgrades.

## 4. Version drift

- Re-run feature-level tests on breakout, share, annotation, and AI companion modules.
- Compare API reference map for renamed or newly required interfaces.
