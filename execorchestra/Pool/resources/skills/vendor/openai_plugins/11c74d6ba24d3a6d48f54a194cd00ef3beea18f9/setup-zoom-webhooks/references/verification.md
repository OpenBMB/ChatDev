# Webhooks - Verification

Verify webhook authenticity and handle URL validation.

## Overview

Zoom provides two verification mechanisms:
1. **URL Validation** - Verify your endpoint during setup
2. **Request Signature** - Verify each webhook request

## URL Validation

When you configure a webhook endpoint, Zoom sends a validation request:

```json
{
  "event": "endpoint.url_validation",
  "payload": {
    "plainToken": "random_token_string"
  }
}
```

### Response Required

Hash the token with your webhook secret and respond:

```javascript
const crypto = require('crypto');

app.post('/webhook', (req, res) => {
  const { event, payload } = req.body;

  if (event === 'endpoint.url_validation') {
    const hashForValidation = crypto
      .createHmac('sha256', WEBHOOK_SECRET_TOKEN)
      .update(payload.plainToken)
      .digest('hex');

    return res.json({
      plainToken: payload.plainToken,
      encryptedToken: hashForValidation
    });
  }

  // Handle other events...
  res.status(200).send();
});
```

## Request Signature Verification

Verify each webhook request is from Zoom:

### Headers

| Header | Description |
|--------|-------------|
| `x-zm-signature` | Request signature |
| `x-zm-request-timestamp` | Request timestamp |

### Verification Code

```javascript
const crypto = require('crypto');

function verifyWebhook(req) {
  const signature = req.headers['x-zm-signature'];
  const timestamp = req.headers['x-zm-request-timestamp'];
  // Prefer raw body bytes captured by your framework to avoid JSON re-serialization mismatches.
  const body = req.rawBody ? req.rawBody.toString('utf8') : JSON.stringify(req.body);

  const message = `v0:${timestamp}:${body}`;
  const hash = crypto
    .createHmac('sha256', WEBHOOK_SECRET_TOKEN)
    .update(message)
    .digest('hex');

  const expectedSignature = `v0=${hash}`;

  return signature === expectedSignature;
}
```

## Security Best Practices

1. Always verify signatures
2. Check timestamp to prevent replay attacks
3. Use HTTPS endpoints only
4. Keep webhook secret secure

## Resources

- **Webhook verification**: https://developers.zoom.us/docs/api/rest/webhook-reference/#verify-webhook-events
