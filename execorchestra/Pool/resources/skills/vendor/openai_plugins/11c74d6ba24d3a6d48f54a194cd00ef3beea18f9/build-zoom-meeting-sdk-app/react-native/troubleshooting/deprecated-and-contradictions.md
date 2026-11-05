# Deprecated and Contradictions Notes

Observed from analyzed package/source artifacts:

1. Reference URL naming inconsistency
- Package README references `react-native/annotated.html` for full API list, while current typed reference entrypoint is `modules.html`.
- Treat this as documentation routing inconsistency across versions.

2. Meeting SDK vs Video SDK wording inconsistency in docs
- Crawled React Native docs include wording that the Meeting SDK wrapper is based on the native Video SDK version.
- Treat this as a likely docs wording issue; align implementation to Meeting SDK package/version compatibility docs.

3. Example UX vs API shape mismatch
- Example UI prompts "Password Optional" but code blocks join if password is empty.
- Wrapper type allows optional `password`; runtime behavior depends on meeting config.

4. Android bridge fragility
- `updateMeetingSetting` uses `config.getString("language")` without robust null checks before split.
- Passing missing/invalid language can crash or throw.

5. Event model limitations
- Android bridge includes emitter plumbing but empty supported event set.
- Do not assume parity with native event coverage without custom extension.

6. Version/toolchain caveat in demo docs
- Demo notes include version-conditional setup (for example pre-`6.4.5` artifact handling) and non-Expo limitation.
- Keep integration guides version-scoped to avoid false assumptions during upgrades.
