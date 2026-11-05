# Probe SDK Sample Validation and Drift Notes

Validated sample:
- `zoom/probesdk-web`

## Lifecycle and Architecture Patterns Confirmed

- `Prober` initialization followed by staged diagnostics.
- Explicit separation between targeted checks (`diagnoseAudio`, `diagnoseVideo`) and comprehensive network probe (`startToDiagnose`).
- Cleanup and stream lifecycle methods are critical for stable page behavior.

## Contradictions and Drift Indicators

- Doc snippet drift:
- Some docs use video options key `type` while reference/sample prefer `rendererType`.
- Report shape drift:
- Docs show `basicInfo`/`supportedFeatures` whereas sample README also references `basicInfoEntries`/`featureEntries`.
- Timeout example variance:
- Docs and sample show different `connectTimeout` defaults in code snippets.

## Recommendations

- Use adapter layer for diagnostic report fields.
- Normalize renderer options through a shared utility in your app.
- Keep browser matrix in your own QA docs and update quarterly.
