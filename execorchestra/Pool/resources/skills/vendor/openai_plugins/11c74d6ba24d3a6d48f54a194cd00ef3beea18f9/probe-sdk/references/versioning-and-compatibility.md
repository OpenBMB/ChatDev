# Probe SDK Versioning and Compatibility

## Upgrade Strategy

Use the standard upgrade workflow:
- [../../general/references/sdk-upgrade-workflow.md](../../general/references/sdk-upgrade-workflow.md)

## Compatibility Risks

- Renderer option naming drift (`type` vs `rendererType`) across docs/examples.
- Report object field naming drift (`basicInfo` vs `basicInfoEntries`, `supportedFeatures` vs `featureEntries`).
- Browser support table age vs current browser versions.
- Runtime JS/WASM URL override mismatches.

## Safe Upgrade Checklist

- Pin and record current/target `@zoom/probesdk` version.
- Compare get-started docs, API reference, and sample repo behavior.
- Validate all renderer targets in your browser matrix.
- Validate both full diagnostic completion and early stop path.
- Validate report schema adapter and downstream consumers.
- Pin JS/WASM assets to the same Probe SDK release and prevent mixed-version loading.
- Add cache-busting strategy for JS/WASM updates (asset fingerprinting or versioned URLs).
- Confirm CDN/browser cache invalidation behavior before production rollout.
