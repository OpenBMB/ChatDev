# Android Architecture

## Layer Model

- App UI layer (Activity/Fragment/Compose wrapper).
- Meeting orchestration layer (init/auth/join/start state machine).
- SDK facade layer (`mobilertc.aar` interfaces and controllers).
- Backend signing service (short-lived signature/JWT issuance).

## Reference Flow

```text
Android UI -> App Meeting Service -> Backend Signature API -> Zoom Meeting SDK
      ^                    |                    |                   |
      |                    v                    v                   v
  User actions       Session state store   Token/role policy   Meeting callbacks
```

## Why this split

- Keeps SDK secret server-side.
- Prevents UI from owning auth/security logic.
- Enables deterministic retry policy on join/start failures.
