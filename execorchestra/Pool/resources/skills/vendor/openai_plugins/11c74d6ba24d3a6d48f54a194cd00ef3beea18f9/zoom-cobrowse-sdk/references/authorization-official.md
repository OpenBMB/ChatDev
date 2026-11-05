# Cobrowse SDK - Authorization

JWT authentication for Cobrowse sessions.

## Overview

Both customers and agents require JWTs for authentication. Generate tokens server-side.

## JWT Structure

### Header

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

### Payload

| Claim | Type | Description |
|-------|------|-------------|
| `user_id` | string | Unique user identifier |
| `app_key` | string | Your SDK Key |
| `role_type` | number | 1 = customer, 2 = agent |
| `user_name` | string | Display name |
| `iat` | number | Issued at timestamp |
| `exp` | number | Expiration timestamp |

### Strict Claim Names (Important)

Cobrowse token validation is strict. Use these claim names exactly:

- `user_id` (not `user_identity`)
- `app_key`
- `role_type`
- `user_name`
- `iat`
- `exp`

Avoid adding unrecognized custom claims unless Zoom docs explicitly support them for your SDK version.
If you see `Invalid token` (code `124`), validate claim names first.

## Role Types

| Role | Value | Description |
|------|-------|-------------|
| Customer | 1 | User sharing their browser |
| Agent | 2 | Support staff viewing session |

## Customer Token Example

```javascript
const customerPayload = {
  user_id: "customer_123",
  app_key: "YOUR_SDK_KEY",
  role_type: 1,
  user_name: "John Customer",
  iat: Math.floor(Date.now() / 1000),
  exp: Math.floor(Date.now() / 1000) + 3600
};

const token = jwt.sign(customerPayload, SDK_SECRET, { algorithm: 'HS256' });
```

## Agent Token Example

```javascript
const agentPayload = {
  user_id: "agent_456",
  app_key: "YOUR_SDK_KEY",
  role_type: 2,
  user_name: "Support Agent",
  iat: Math.floor(Date.now() / 1000),
  exp: Math.floor(Date.now() / 1000) + 3600
};

const token = jwt.sign(agentPayload, SDK_SECRET, { algorithm: 'HS256' });
```

## Security

- Generate tokens server-side only
- Never expose SDK Secret in client code
- Use reasonable expiration times

## Resources

- **Auth docs**: https://developers.zoom.us/docs/cobrowse-sdk/authorize/
