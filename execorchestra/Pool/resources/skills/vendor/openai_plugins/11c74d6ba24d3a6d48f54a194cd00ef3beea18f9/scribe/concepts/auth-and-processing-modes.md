# Auth and Processing Modes

## Authentication Model

Scribe uses a Build-platform JWT bearer token.

JWT shape:
- algorithm: `HS256`
- issuer claim: Build-platform credential identifier used by the Scribe API
- expiration: keep to one hour or less

Node example:

```js
import { KJUR } from 'jsrsasign';

export function generateJWT(apiKey, apiSecret) {
  const iat = Math.round(Date.now() / 1000) - 30;
  const exp = iat + 60 * 60;
  return KJUR.jws.JWS.sign(
    'HS256',
    JSON.stringify({ alg: 'HS256', typ: 'JWT' }),
    JSON.stringify({ iss: apiKey, iat, exp }),
    apiSecret,
  );
}
```

## Credential Naming Drift

Zoom docs currently use inconsistent labels across AI Services pages:
- `API key` / `API secret`
- `SDK key` / `SDK secret`
- `Build platform credentials`

For implementation, treat them as the Build-platform JWT issuer/secret pair used to sign Scribe requests. Verify the exact labels in the current portal UI before shipping.

## Fast Mode vs Batch Mode

| Mode | Best for | Transport | Result timing |
|------|----------|-----------|---------------|
| Fast mode | One short file, interactive UX | `POST /transcribe` | Immediate synchronous JSON |
| Batch mode | Archives, long media, many files | `POST /jobs` then status/webhook | Asynchronous |

## Fast Mode Request Shape

- required: `file`, `config`
- common config: `language`, `word_time_offsets`, `channel_separation`, `timestamps`, `output_format`, `profanity_filter`, `diarization`

## Batch Mode Request Shape

- required: `input`, `output`, `config`
- input modes: `SINGLE`, `PREFIX`, `MANIFEST`
- storage provider currently surfaced in the OpenAPI as `S3`
- optional webhook callback: `notifications.webhook_url` + `notifications.secret`

## Operational Choice

Choose fast mode when:
- user uploads one file
- latency matters more than throughput
- file size and duration are manageable
- you are building pseudo-streaming over short microphone chunks from a browser UI

Choose batch mode when:
- many files must be processed
- transcripts can arrive later
- storage-centric workflows fit better than direct upload

## Browser Microphone Pseudo-Streaming

Scribe is file-oriented, so a browser microphone UX should be modeled as repeated short uploads, not a long-lived stream.

Recommended pattern:
1. capture browser microphone audio with `MediaRecorder`
2. flush short chunks to your backend
3. submit each chunk through the async fast-mode wrapper
4. poll by request ID
5. append transcript chunks in order

Recommended starting values:
- chunk size: `5 seconds`
- acceptable range: `5-10 seconds`
- concurrent in-flight chunks: `2-3`

Why this works:
- lowers the chance of frontend `504` on longer synchronous requests
- gives incremental transcript updates without waiting for one long request

Guardrail:
- this is pseudo-streaming over file uploads
- this is not the preferred production design for live audio capture
- use it only when a lightweight browser demo or rough incremental transcript is acceptable
- avoid it when you need stable low-latency live transcription, lower overhead, or stronger continuity across utterances
- for true live media streams, low-latency server ingest, or continuous in-meeting audio, use `rtms`
