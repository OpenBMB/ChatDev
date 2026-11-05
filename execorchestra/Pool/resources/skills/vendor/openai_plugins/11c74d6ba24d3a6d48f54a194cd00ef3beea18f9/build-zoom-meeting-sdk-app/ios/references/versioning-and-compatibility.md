# iOS Versioning and Compatibility

## Observed Versions

- Local SDK package: `v6.7.5.33005`
- Docs baseline: current iOS Meeting SDK docs tree captured on this crawl.

## Compatibility Practices

- Pin exact SDK package release.
- Re-verify category/protocol method availability on upgrades.
- Re-test background/audio interruption flows every upgrade.

## Contradiction/Drift Notes

- Package `README.md` points to generic Meeting SDK docs root, while platform docs live at `/meeting-sdk/ios/`.
- Package changelog file only links externally; keep your own integration delta notes per release.
