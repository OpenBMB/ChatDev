# Samples Validation

Validated against:
- https://github.com/zoom/scribe-quickstart/
- official docs pages under `docs/ai-services/`
- AI Services OpenAPI inventory at `api-hub/ai-services/methods/endpoints.json`
- Zoom blog context:
  - `introducing-zoom-ai-services`
  - `voice-insights-modernize-customer-support-with-scribe`

## What the official quickstart confirms

- Node/Express proxy architecture is a valid implementation model.
- Fast mode can be proxied as multipart upload handling on your server even though the docs show JSON examples.
- Batch mode commonly injects AWS credentials into request payloads.
- Webhook verification uses `x-zm-signature` + `x-zm-request-timestamp` with HMAC-SHA256 and `sha256=` prefix.
- The quickstart uses `ZOOM_API_KEY` / `ZOOM_API_SECRET` naming.

## Useful implementation details from the sample

- `multer` memory storage is enough for a small fast-mode demo.
- Batch helper routes are naturally expressed as:
  - `POST /batch/jobs`
  - `GET /batch/jobs`
  - `GET /batch/jobs/:jobId`
  - `GET /batch/jobs/:jobId/files`
  - `DELETE /batch/jobs/:jobId`
- It is practical to keep one `generateJWT()` helper and inject the bearer token per request.

## Caveats from the sample

- It assumes Node `>=24`, which is stricter than many deployment environments actually need. Verify your runtime before copying that constraint unchanged.
- It uses environment-injected AWS credentials. Production pipelines may prefer pre-signed URLs or short-lived STS credentials only.
- The sample is an app demo, not a complete production reference for job retry policy, durable queues, or transcript storage.

## What the blog posts add

- They reinforce the highest-value downstream use cases:
  - post-call summaries
  - ticket enrichment
  - compliance/audit logging
  - searchable archives
  - customer-support QA workflows
- They are useful for scenario framing, but not as authoritative API surface documentation.
- Keep endpoint and request-shape decisions anchored to the AI Services docs and API Hub inventory, not the blog wording.
