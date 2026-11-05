# Bot Authentication - JWT, ZAK, and OBF Tokens

Understanding the different token types for Meeting SDK authentication, especially for bots joining meetings.

## Overview

Meeting SDK authentication involves multiple token types that serve different purposes. This guide clarifies the confusion between JWT signatures, ZAK tokens, and OBF tokens.

## Token Types Summary

| Token | Purpose | Always Required? | Deprecated? |
|-------|---------|------------------|-------------|
| **JWT Signature** | Initialize/authenticate Meeting SDK | **Yes** | **No** |
| **ZAK Token** | Authenticate as a Zoom user | No (situational) | **No** |
| **OBF Token** | Join external meetings with user attribution | No (required Feb 2026) | **No** |

## Common Confusion

### JWT App Type vs JWT Signature

**This is the #1 source of confusion.**

| Term | What It Is | Status |
|------|------------|--------|
| **JWT App Type** | A Zoom app type for REST API authentication | **Deprecated** (migrated to Server-to-Server OAuth) |
| **JWT Signature** | A token generated using SDK credentials to authenticate Meeting SDK | **Still required and NOT deprecated** |

**Key Point:** The deprecation of JWT App Type does NOT affect Meeting SDK. You still need JWT signatures for SDK authentication.

---

## 1. JWT Signature (Always Required)

### What Is It?

A JWT (JSON Web Token) signature authenticates your application to use the Meeting SDK. Generated server-side using your SDK Client ID and Client Secret.

### When to Use

**Always.** Every Meeting SDK join requires a JWT signature.

### How to Generate

```javascript
// Server-side (Node.js)
const KJUR = require('jsrsasign');

function generateSignature(sdkKey, sdkSecret, meetingNumber, role) {
  const iat = Math.round(Date.now() / 1000) - 30;  // 30 seconds ago
  const exp = iat + 60 * 60 * 2;                    // 2 hours from iat

  const payload = {
    sdkKey: sdkKey,        // Your SDK Client ID
    mn: meetingNumber,     // Meeting number to join
    role: role,            // 0 = participant, 1 = host
    iat: iat,
    exp: exp,
    tokenExp: exp
  };

  const header = { alg: 'HS256', typ: 'JWT' };

  return KJUR.jws.JWS.sign('HS256',
    JSON.stringify(header),
    JSON.stringify(payload),
    sdkSecret              // Your SDK Client Secret
  );
}
```

### Best Practice: Short-Lived Tokens

```javascript
// Generate token just before joining
const iat = Math.floor(Date.now() / 1000) - 7200;  // 2 hours in past
const exp = Math.floor(Date.now() / 1000) + 10;    // 10 seconds from now

// Why this works:
// - exp is short-lived (security)
// - exp - iat >= 2 hours (Zoom requirement)
// - Token generated right before use
```

### Role Values

| Role | Value | Description |
|------|-------|-------------|
| Participant | 0 | Join as attendee |
| Host | 1 | Join as host (requires being meeting owner or having host key) |

---

## 2. ZAK Token (Zoom Access Key)

### What Is It?

A short-lived credential that proves your bot/app is authenticated as a specific Zoom user. Generated via the Zoom REST API.

### When to Use

| Scenario | ZAK Required? |
|----------|---------------|
| Meeting has "Only Authenticated Users Can Join" enabled | **Yes** |
| Starting a meeting as the host (when host not present) | **Yes** (host's ZAK) |
| Changing bot's profile picture to match a user | **Yes** |
| Regular meeting join | No |

### How to Get ZAK Token

**Step 1: Get OAuth Access Token**

```bash
curl -X POST "https://zoom.us/oauth/token" \
  -H "Authorization: Basic {BASE64(client_id:client_secret)}" \
  -d "grant_type=authorization_code&code={auth_code}&redirect_uri={redirect_uri}"
```

**Step 2: Generate ZAK Token**

```bash
curl -X GET "https://api.zoom.us/v2/users/me/token?type=zak&ttl=7200" \
  -H "Authorization: Bearer {access_token}"
```

**Response:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Required OAuth Scope

```
user:read:zak
```

### Using ZAK in SDK Join

```javascript
// Web SDK
ZoomMtg.join({
  signature: signature,      // JWT signature (always required)
  sdkKey: clientId,
  meetingNumber: meetingNumber,
  passWord: password,
  userName: "Meeting Bot",
  zak: zakToken,             // ZAK token for authenticated join
  success: (success) => console.log('Joined'),
  error: (error) => console.error(error)
});
```

### Key Properties

- **Short-lived**: Configurable TTL (typically 1-2 hours)
- **Any ZAK works**: Doesn't need to be from a meeting participant
- **No concurrency limit**: One service account can generate unlimited tokens
- **Expiry checked at join**: If already in meeting, bot stays connected even if ZAK expires

### Common Mistake

**Wrong:** Thinking ZAK must be from a meeting participant.

**Right:** Any Zoom account's ZAK satisfies "Only Authenticated Users" requirement. Create one service account (e.g., `meeting-bot@company.com`) for all your bots.

---

## 3. OBF Token (On-Behalf-Of Token)

### What Is It?

A new credential that ties your bot to a specific user who is present in the meeting. Required for external meetings starting **February 23, 2026**.

### Why Introduced?

Zoom introduced OBF tokens for accountability and transparency. It makes clear that an SDK app belongs to a specific person in the meeting.

### When to Use

| Date | External Meeting Requirement |
|------|------------------------------|
| Before Feb 23, 2026 | ZAK or OBF (optional) |
| **After Feb 23, 2026** | **ZAK or OBF required** |

### Critical Difference: OBF vs ZAK

| Aspect | ZAK Token | OBF Token |
|--------|-----------|-----------|
| User presence required | No | **Yes** - user MUST be in meeting |
| Bot disconnection | Stays if token owner leaves | **Immediately disconnected** if user leaves |
| Meeting scope | Any meeting | Specific meeting ID only |
| Attribution | Generic authentication | Tied to specific attending user |

### How to Get OBF Token

**Step 1: Get OAuth Access Token** (same as ZAK)

**Step 2: Generate OBF Token**

```bash
curl -X GET "https://api.zoom.us/v2/users/me/token?type=onbehalf&meeting_id={meeting_id}" \
  -H "Authorization: Bearer {access_token}"
```

**Response:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Required OAuth Scope

```
user:read:token
```

### Using OBF in SDK Join

```javascript
// Web SDK
ZoomMtg.join({
  signature: signature,      // JWT signature (always required)
  sdkKey: clientId,
  meetingNumber: meetingNumber,
  passWord: password,
  userName: "Meeting Bot",
  obfToken: obfToken,        // OBF token (NOT zak)
  success: (success) => console.log('Joined'),
  error: (error) => console.error(error)
});
```

**Important:** `zak` and `obfToken` are **mutually exclusive**. Use only one.

### Handling Join Failures

If bot joins before authorizing user is in meeting:

```javascript
// SDK v6.6.10+ returns specific error code
// MEETING_FAIL_AUTHORIZED_USER_NOT_INMEETING

async function joinWithRetry(joinOptions, maxRetries = 5) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await ZoomMtg.join(joinOptions);
      return; // Success
    } catch (error) {
      if (error.code === 'MEETING_FAIL_AUTHORIZED_USER_NOT_INMEETING') {
        console.log(`User not in meeting yet. Retry ${i + 1}/${maxRetries}`);
        await sleep(3000); // Wait 3 seconds
      } else {
        throw error; // Different error, don't retry
      }
    }
  }
  throw new Error('Max retries exceeded - user never joined meeting');
}
```

### OBF Token Mapping

You must map users to their meetings:

1. **Zoom Meetings API**: `GET /users/{userId}/meetings`
2. **Calendar integration**: Parse meeting invites from Google Calendar/Outlook

---

## Complete Bot Join Flow

### Current (Pre-Feb 2026)

```javascript
// 1. Generate JWT signature (always required)
const signature = await generateSignature(sdkKey, sdkSecret, meetingNumber, 0);

// 2. Optionally get ZAK for authenticated-only meetings
let zakToken = null;
if (meetingRequiresAuth) {
  zakToken = await getZAKToken(accessToken);
}

// 3. Join meeting
await ZoomMtg.join({
  signature: signature,
  sdkKey: sdkKey,
  meetingNumber: meetingNumber,
  passWord: password,
  userName: "Meeting Bot",
  zak: zakToken,  // Optional
});
```

### Post-Feb 2026 (External Meetings)

```javascript
// 1. Generate JWT signature (always required)
const signature = await generateSignature(sdkKey, sdkSecret, meetingNumber, 0);

// 2. For external meetings, get OBF token
const obfToken = await getOBFToken(accessToken, meetingNumber);

// 3. Wait for authorizing user to join (if using OBF)
// ... implement retry logic ...

// 4. Join meeting
await ZoomMtg.join({
  signature: signature,
  sdkKey: sdkKey,
  meetingNumber: meetingNumber,
  passWord: password,
  userName: "Meeting Bot",
  obfToken: obfToken,  // For external meetings
});
```

---

## Linux Bot Implementation

For headless Linux bots, use the official sample:

```bash
# Clone sample repository
git clone git@github.com:zoom/meetingsdk-headless-linux-sample.git

# Configure (sample.config.toml)
[credentials]
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"

[meeting]
join_url = "https://zoom.us/j/123456789?pwd=xxx"
# OR
meeting_id = 123456789
password = "abc123"

# Optional tokens
zak_token = "..."   # For authenticated joins
obf_token = "..."   # For external meetings

# Run with Docker
docker compose up
```

---

## Common Mistakes

| Mistake | Reality | Fix |
|---------|---------|-----|
| JWT signatures are deprecated | Only JWT App Type is deprecated | Continue using JWT signatures for SDK |
| ZAK must be from meeting participant | Any Zoom account's ZAK works | Use single service account |
| Using both ZAK and OBF together | They're mutually exclusive | Use only one |
| Generating OBF before user in meeting | OBF requires user presence | Implement retry logic |
| Development credentials for external meetings | Dev credentials only work for your account | Get production credentials (4-6 week review) |

---

## Timeline

| Date | Change |
|------|--------|
| **Now** | JWT signatures required; ZAK optional |
| **Nov 2025** | SDK v6.6.10 with OBF-specific error codes |
| **Feb 23, 2026** | **OBF or ZAK required for external meetings** |

---

## OAuth Scopes Summary

| Token | Required Scope |
|-------|----------------|
| ZAK Token | `user:read:zak` |
| OBF Token | `user:read:token` |

## Resources

- **Meeting SDK Auth**: https://developers.zoom.us/docs/meeting-sdk/auth/
- **OBF Token Announcement**: https://developers.zoom.us/blog/transition-to-obf-token-meetingsdk-apps/
- **Linux SDK Sample**: https://github.com/zoom/meetingsdk-headless-linux-sample
- **Developer Forum**: https://devforum.zoom.us/
