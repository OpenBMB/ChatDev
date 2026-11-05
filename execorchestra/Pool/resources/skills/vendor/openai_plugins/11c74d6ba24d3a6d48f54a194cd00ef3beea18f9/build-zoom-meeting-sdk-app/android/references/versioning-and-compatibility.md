# Android Versioning and Compatibility

## Observed Versions

- Local SDK package: `v6.7.5.37500`
- Docs baseline: current Meeting SDK Android docs tree captured on this crawl.

## Compatibility Practices

- Pin exact SDK artifact version in Gradle.
- Track enum/interface additions between releases.
- Validate custom UI flows after each SDK update (higher break risk vs default UI).

## Contradiction/Drift Notes

- Docs contain legacy and current path variants (`add-features` vs `custom-ui/default-ui` sections).
- Some page titles include suffix artifacts (for example `| MSDK | And`), indicating doc-generation inconsistencies, not functional API differences.
