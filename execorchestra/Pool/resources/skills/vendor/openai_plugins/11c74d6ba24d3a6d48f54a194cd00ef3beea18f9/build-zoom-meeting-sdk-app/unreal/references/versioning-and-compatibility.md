# Unreal Versioning and Compatibility

## Observed Versions

- Local package version: `v6.1.5.43366` (`UE v5.4.3`)
- Local package naming: `zoom-meeting-sdk-unreal-engine-6.1.5-full`
- Docs baseline: current Unreal Meeting SDK docs tree captured on this crawl.

## Compatibility Practices

- Validate Unreal engine version compatibility before SDK integration.
- Confirm wrapper API availability in both C++ and Blueprint paths.
- Keep a version matrix (Unreal Engine version x wrapper version x Meeting SDK behavior).

## Contradiction/Drift Notes

- Unreal package `CHANGELOG.md` currently points to a Windows changelog URL (packaging inconsistency).
- Wrapper docs reference base behavior from Windows SDK for unchanged methods; verify assumptions per wrapper release.
- Unreal wrapper package version is behind current mobile/desktop package streams in this workspace snapshot.
