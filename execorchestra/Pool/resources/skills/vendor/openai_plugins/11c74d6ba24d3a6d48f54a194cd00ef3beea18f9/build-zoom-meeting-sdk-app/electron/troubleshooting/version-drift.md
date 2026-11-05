# Version Drift

Electron SDK integrations are sensitive to dependency drift.

## Drift vectors

- Electron runtime upgrades
- Node ABI changes
- Native addon compiler toolchain changes
- Meeting SDK wrapper package updates

## Control strategy

1. Pin tested Electron + SDK versions.
2. Keep a compatibility matrix in your project docs.
3. Rebuild and smoke test on every runtime change.
4. Run callback/error-code regression tests for join/start/audio/video/share.
