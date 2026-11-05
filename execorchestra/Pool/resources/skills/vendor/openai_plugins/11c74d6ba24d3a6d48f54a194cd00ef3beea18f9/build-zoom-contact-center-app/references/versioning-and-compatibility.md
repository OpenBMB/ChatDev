# Versioning and Compatibility Notes

## Minimum Version Enforcement

- Zoom enforces SDK minimum versions quarterly.
- Enforcement windows are announced with advance notice.
- Older SDKs can stop functioning in production even if code has not changed.

## Practical Policy

1. Track SDK version in runtime telemetry.
2. Maintain a scheduled upgrade cadence.
3. Validate critical flows every release:
- launch/init
- engagement events
- channel open/close
- rejoin (mobile)

## Known Drift Patterns

- API shape drift between docs and generated references.
- Legacy snippets showing old method signatures.
- Event naming/style differences between product surfaces.
- Deprecated callbacks preserved for backward compatibility but replaced in newer signatures.

## iOS Notable Deprecation

- `onService:error:detail:` is deprecated.
- Prefer `onService:error:detail:description:`.

## Smart Embed Version Note

- Smart Embed v3 is the forward path in docs.
- Maintain version-gated integration code if your account still has older embed behavior.

## Defensive Design

- Feature-detect methods/events before calling them.
- Keep adapters between your domain model and SDK payloads.
- Avoid hard-coding assumptions about optional fields.
