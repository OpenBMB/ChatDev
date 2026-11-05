# macOS Versioning and Compatibility

## Observed Versions

- Local SDK package: `v6.7.6.75900`
- Docs baseline: current macOS Meeting SDK docs tree captured on this crawl.

## Compatibility Practices

- Pin exact SDK package and re-test controller/delegate contracts on upgrade.
- Verify custom UI features (annotation/share/immersive) first during upgrade testing.
- Maintain a release checklist for host-only and webinar-specific flows.

## Contradiction/Drift Notes

- Docs contain both top-level and nested advanced-feature paths; treat them as parallel documentation organization, not separate APIs.
- Changelog in package is external-link based; maintain local upgrade notes for exact behavior changes.
