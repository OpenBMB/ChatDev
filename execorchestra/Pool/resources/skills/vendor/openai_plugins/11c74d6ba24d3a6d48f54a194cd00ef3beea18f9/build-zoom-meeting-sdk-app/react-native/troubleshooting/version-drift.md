# Version Drift Guidance

Because wrapper and native SDKs evolve:

- Reconfirm option names on each wrapper upgrade.
- Treat returned numeric meeting codes as versioned behavior.
- Re-test both join and host-start flows after SDK bump.
- Validate platform-specific flags (Android/iOS) separately.
- Reconfirm React Native framework compatibility window and Expo support status.

Upgrade checklist:

1. Compare `src/native/ZoomSDK.ts` API types between versions.
2. Compare Android `RNZoomSDKModule.java` option mapping.
3. Compare iOS `RNZoomSDK.m` auth/join/start implementations.
4. Re-run smoke tests: init -> isInitialized -> join/start -> cleanup.
5. Re-validate Android/iOS setup requirements from docs (permissions, min/target SDK, pod/gradle notes).
