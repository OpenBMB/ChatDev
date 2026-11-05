# Versioning and Drift

## Naming Drift in Docs

The current Zoom docs are inconsistent about credential naming:
- AI Services auth page uses `API key` / `API secret`.
- Build-platform credentials page uses `SDK key` / `SDK secret`.
- Quickstart code uses `ZOOM_API_KEY` / `ZOOM_API_SECRET`.

Treat these as a portal/documentation naming drift issue and verify the current credential labels in the Zoom developer UI before changing production code.

## Product Positioning Drift

Scribe sits under `AI Services`, but related Zoom products may point users toward:
- RTMS for live meeting streams
- Meeting SDK Linux bots for visible in-meeting capture
- AI Companion / REST APIs for Zoom-generated summaries and transcripts
- blog or marketing material that frames Scribe inside broader speech/insights workflows

Keep the guardrail clear:
- `scribe` = file/storage transcription service
- `rtms` = live media stream ingestion
- Meeting SDK Linux = participant bot capture / raw recording

## Workflow-Claim Drift

Some AI Services and Scribe blog material frames Scribe inside broader voice-insights workflows such as:
- post-call summaries
- ticket enrichment
- compliance logging
- searchable archives
- customer-support QA pipelines
- sentiment or keyword-driven downstream analytics

These are valid architectural use cases, but they do not expand the current documented Scribe endpoint surface.

Implementation rule:
- use `scribe` for transcript generation
- use your own downstream pipeline for sentiment, classification, QA scoring, or summarization
- do not infer undocumented real-time or analytics endpoints from blog phrasing alone

## API Surface Drift Watchpoints

Watch for changes in:
- storage providers beyond `S3`
- request field names in `config`
- webhook signature header conventions
- response summary/file schemas
- language / output-format support

## Review Trigger

Re-review this skill when:
- `api-hub/ai-services/methods/endpoints.json` changes
- AI Services docs rename Build/API credentials again
- quickstart sample changes webhook or upload patterns
