# Meeting SDK - Authorization

Generate JWT signatures for Meeting SDK authentication.

## Overview

Meeting SDK uses JWT (JSON Web Token) signatures to authenticate users joining meetings. Signatures must be generated server-side to protect your SDK Secret.

## Prerequisites

- Meeting SDK Key and Secret from [Marketplace](https://marketplace.zoom.us/) (sign-in required)
- Server-side code to generate signatures

## JWT Structure

| Claim | Description |
|-------|-------------|
| `sdkKey` | Your SDK Key |
| `mn` | Meeting number |
| `role` | 0 = participant, 1 = host |
| `iat` | Issued at timestamp |
| `exp` | Expiration timestamp |
| `tokenExp` | Token expiration timestamp |

## Signature Generation Best Practices

### Short-Lived Tokens (Recommended)

For security, generate tokens with short expiry:

```javascript
const iat = Math.floor(Date.now() / 1000) - 7200; // 2 hours in the past
const exp = Math.floor(Date.now() / 1000) + 10;   // 10 seconds from now

const payload = {
  sdkKey: SDK_KEY,
  mn: meetingNumber,
  role: role,
  iat: iat,
  exp: exp,
  tokenExp: exp
};
```

**Why this works:**
- `exp` is only 10 seconds after generation (short-lived for security)
- `iat` is set 2 hours in the past to satisfy Zoom's requirement that `exp - iat >= 2 hours`
- Token is generated just before joining, so 10 second window is sufficient

### Server-Side Example (Node.js)

```javascript
const jwt = require('jsonwebtoken');

function generateSignature(sdkKey, sdkSecret, meetingNumber, role) {
  const iat = Math.floor(Date.now() / 1000) - 7200; // 2 hours ago
  const exp = Math.floor(Date.now() / 1000) + 10;   // 10 seconds from now

  const payload = {
    sdkKey: sdkKey,
    mn: meetingNumber,
    role: role,
    iat: iat,
    exp: exp,
    tokenExp: exp
  };

  return jwt.sign(payload, sdkSecret, { algorithm: 'HS256' });
}
```

## Role Values

| Role | Value | Description |
|------|-------|-------------|
| Participant | 0 | Join as attendee |
| Host | 1 | Join as host (requires host key or being meeting owner) |

## Security Guidelines

| Do | Don't |
|----|-------|
| Generate signatures server-side | Expose SDK Secret in client code |
| Use short expiry times | Use long-lived tokens |
| Validate user before generating | Generate for unauthenticated users |

## Resources

- **Auth docs**: https://developers.zoom.us/docs/meeting-sdk/auth/
