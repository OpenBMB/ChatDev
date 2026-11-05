# Android Common Issues

## 1. Init succeeds, join fails immediately

- Verify signature freshness and role correctness.
- Confirm meeting number/passcode are exact values.
- Confirm auth path aligns with join/start path (attendee vs host).

## 2. Works in sample, fails in app

- Compare manifest permissions and ProGuard/R8 rules.
- Compare Gradle dependency graph for collisions.
- Confirm lifecycle ownership (Activity recreation handling).

## 3. Custom UI instability

- Validate default UI parity first.
- Re-check event registration ordering before rendering operations.
- Guard against null/late user stream references.

## 4. Version drift breakage

- Rebuild against pinned SDK version.
- Revisit renamed interfaces in API reference map.
- Re-test breakout, raw data, and advanced feature modules after upgrade.
