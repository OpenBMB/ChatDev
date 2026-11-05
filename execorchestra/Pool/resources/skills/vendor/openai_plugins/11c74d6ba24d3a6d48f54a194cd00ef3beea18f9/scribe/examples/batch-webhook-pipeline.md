# Batch Job + Webhook Pipeline

Use batch mode when you need to process stored archives asynchronously.

## Flow

```text
submit batch job
  -> receive job_id
  -> poll /jobs or wait for webhook
  -> inspect /jobs/{jobId}/files
  -> ingest transcript outputs
```

## Submit Example

```bash
curl -X POST https://api.zoom.us/v2/aiservices/scribe/jobs   -H "Authorization: Bearer $TOKEN"   -H "Content-Type: application/json"   -d '{
    "input": {
      "mode": "PREFIX",
      "source": "S3",
      "uri": "s3://example-bucket/audio/",
      "auth": {
        "aws": {
          "access_key_id": "...",
          "secret_access_key": "...",
          "session_token": "..."
        }
      }
    },
    "output": {
      "destination": "S3",
      "uri": "s3://example-bucket/transcripts/",
      "layout": "PREFIX",
      "auth": {
        "aws": {
          "access_key_id": "...",
          "secret_access_key": "...",
          "session_token": "..."
        }
      }
    },
    "config": {
      "language": "en-US",
      "word_time_offsets": true,
      "channel_separation": true
    },
    "notifications": {
      "webhook_url": "https://example.com/webhooks/scribe",
      "secret": "replace-me"
    }
  }'
```

## Webhook Verification Pattern

```js
import crypto from 'crypto';

function verifyZoomWebhook(rawBody, timestamp, signature, secret) {
  const message = `v0:${timestamp}:${rawBody}`;
  const expected = `sha256=${crypto.createHmac('sha256', secret).update(message).digest('hex')}`;
  return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
}
```
