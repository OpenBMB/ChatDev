# Authentication Pattern

## Backend

- Accept meeting context inputs.
- Generate short-lived Meeting SDK JWT.
- Return token to authenticated Electron client session.

## Electron app

1. Initialize SDK.
2. Send SDK JWT to auth module.
3. Wait for auth callback success.
4. Continue to meeting join/start.

## Guardrails

- Refresh token on expiry windows.
- Fail fast on auth callback errors and show actionable logs.
- Do not persist SDK secret or signing logic in Electron bundle.
