# Unreal Join/Start Pattern

## Join/Start Sequence

1. Initialize wrapper SDK context.
2. Authenticate with backend-provided short-lived token/signature.
3. Trigger join/start through wrapper API.
4. Bind wrapper event callbacks before user-interactive meeting controls.

## Blueprint/C++ Guardrails

- Confirm node/function exists in selected wrapper mode.
- For modified wrapper methods, verify input/output differences from native docs.
- Keep a thin C++ adapter for shared validation logic when Blueprint nodes diverge.
