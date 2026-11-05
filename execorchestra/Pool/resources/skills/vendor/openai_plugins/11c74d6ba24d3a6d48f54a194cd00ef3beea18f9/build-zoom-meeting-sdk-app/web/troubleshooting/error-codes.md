# Zoom Meeting SDK Web - Error Codes

Comprehensive reference for all error codes returned by the Zoom Meeting SDK for Web.

## Quick Lookup

| Code Range | Category |
|------------|----------|
| 0-2 | General/Success |
| 3000-3999 | Meeting Validation |
| 4000-4999 | Connection Status |
| 6000+ | System/Service |
| 10000+ | SDK Version |
| 13000+ | Simulive |

## General Errors (0-2)

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `0` | SUCCESS | Function invoked successfully | N/A |
| `1` | FAIL | General function error | Check parameters and SDK state |
| `2` | MEETING_NOT_INIT | Meeting not initialized | Call `init()` before `join()` |

## Meeting Validation Errors (3000-3999)

### Authentication Errors

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `3704` | API_KEY_INVALID | SDK Key/Client ID is invalid | Verify SDK credentials in Marketplace |
| `3705` | SIGNATURE_EXPIRED | JWT signature has expired | Generate new signature with valid `exp` |
| `3708` | ROLE_ERROR | Incorrect role in signature | Use role 0 (participant) or 1 (host) |
| `3710` | API_KEY_DISABLED | SDK Key is deactivated | Re-enable in Marketplace or create new app |
| `3712` | SIGNATURE_INVALID | Signature verification failed | Check SDK secret, verify signature generation |
| `3265` | TOKEN_ERROR | Token validation failed | Check ZAK/OBF token format and expiry |
| `3623` | TOKEN_ERROR_ALT | Token error (alternate) | Same as 3265 |
| `3713` | NO_PERMISSION | Insufficient permissions | Verify account permissions and scopes |

### Meeting Errors

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `3001` | ERROR_NOT_EXIST | Meeting does not exist | Verify meeting number |
| `3003` | ERROR_NOT_HOST | Not meeting host | Use host's ZAK token to start |
| `3004` | WRONG_MEETING_PASSWORD | Incorrect password | Verify `passWord` (Client View) or `password` (Component View) |
| `3005` | ANOTHER_MEETING_RUNNING | Already in another meeting | Leave current meeting first |
| `3008` | MEETING_NOT_START | Meeting hasn't started | Wait for host or use "join before host" |
| `3009` | BE_REMOVED | User was removed from meeting | Cannot rejoin; contact host |
| `3610` | MEETING_NOT_EXIST_ALT | Meeting does not exist (alt) | Same as 3001 |

### Registration & Login

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `3000` | EMAIL_REQUIRED | Email required for webinar | Provide `userEmail` in join params |
| `3099` | REGISTRATION_REQUIRED | Meeting requires registration | Get `tk` token from registration API |
| `3100` | LOGIN_REQUIRED | Zoom login required | Provide ZAK token for authenticated join |
| `3624` | HOST_EMAIL_REQUIRED | Host/alt host needed for webinar | Use host credentials to start |

### Host Errors

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `3625` | HOST_INACTIVE | Meeting host is inactive | Contact host to activate account |
| `3702` | HOST_NOT_FOUND | Host does not exist | Verify host account |
| `3709` | HOST_NOT_FOUND | Host not found (alt) | Same as 3702 |
| `3711` | CANT_HOST_CONCURRENT | Can't host multiple meetings | End other meeting first |

### Platform Restrictions

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `3603` | NOT_SUPPORT_WEBCLIENT | Web join not allowed | Admin must enable web client |
| `3608` | TSP_NOT_SUPPORT | TSP audio not supported on web | Use computer audio or phone |
| `3611` | USE_DESKTOP_OR_MOBILE | Browser join disabled | Use Zoom desktop/mobile app |
| `3620` | EMAIL_BLOCKED | Email blocked by admin | Contact account administrator |
| `3621` | NO_RESPONSE_FROM_WEB | Server timeout | Retry request |

## Connection Errors (4000-4999)

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `4000` | RE_CONNECTING | Reconnecting to meeting | Wait for reconnection |
| `4001` | DISCONNECT | Disconnected from meeting | Check network, try rejoining |
| `4003` | INVALID_PARAMETER | Invalid join parameter | Check all required fields |
| `4004` | MEETING_ENDED | Meeting has ended | Cannot join ended meeting |
| `4005` | MEETING_CAPACITY_REACHED | Meeting is full | Host needs to increase capacity |
| `4006` | MEETING_LOCKED | Meeting is locked | Host must unlock to allow joins |
| `4007` | REJECT_BARRIERS | Information barriers rejection | Contact admin about policies |
| `4008` | PARTICIPANT_EXIST | Already a participant | Already in meeting or leave first |
| `4009` | SERVER_ERROR | Internal server error | Retry request |
| `4011` | NOT_ALLOW_CROSS_JOIN | Cross-account join blocked | Publish app on Marketplace (see 6.1 ToS) |

## OBF/Anonymous Join Errors (March 2026+)

> **IMPORTANT**: Starting **March 2, 2026**, anonymous joins to external meetings are blocked. You must provide a valid OBF or ZAK token.

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `4012` | NOT_ALLOW_ANONYMOUS_JOIN | Anonymous join not allowed | Provide valid OBF or ZAK token |
| `4013` | USER_LEVEL_TOKEN_NOT_HAVE_HOST_ZAK_OBF | OBF/ZAK token invalid or missing | Verify token is not expired or malformed |

### 4012 Error Response

```json
{
  "meetingStatus": 3,
  "errorCode": 4012,
  "errorMessage": "Anonymous joins are not allowed for this SDK app. Authenticate the Zoom user and provide a ZAK or OBF token."
}
```

**Solutions for 4012:**
1. Generate OBF token via Zoom API
2. Or get user's ZAK token via `/users/me/zak`
3. Pass token in `obfToken` or `zak` join parameter

### 4013 Error Response

```json
{
  "meetingStatus": 3,
  "errorCode": 4013,
  "errorMessage": "The OBF or ZAK token is not provided or invalid. Make sure it's not expired or malformed."
}
```

**Solutions for 4013:**
1. Check token expiration (OBF tokens expire)
2. Verify token format is correct
3. Regenerate token if expired

## System Errors (6000+)

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `6603` | BLOCKED_BY_HOST_ADMIN | SDK Key blocked by host's admin | Contact host's admin to whitelist |

## SDK Version Errors (10000+)

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `10000` | SDK_VERSION_UNSUPPORTED | SDK version no longer supported | Upgrade to latest SDK version |

## Simulive Errors (13000+)

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| `13208` | UNABLE_JOIN_ENDED_SIMULIVE | Simulive webinar has ended | Cannot join ended simulive |

## Error Handling Patterns

### Client View

```javascript
ZoomMtg.join({
  // ... options
  success: (res) => {
    console.log('Joined successfully');
  },
  error: (err) => {
    console.error('Join failed:', err);

    switch (err.errorCode) {
      case 3004:
        alert('Incorrect meeting password');
        break;
      case 3712:
        console.error('Signature invalid - check SDK secret');
        break;
      case 4012:
        console.error('OBF token required for external meetings');
        break;
      default:
        console.error(`Error ${err.errorCode}: ${err.errorMessage}`);
    }
  }
});
```

### Component View

```javascript
try {
  await client.join({
    // ... options
  });
} catch (error) {
  console.error('Join failed:', error);

  // error.reason contains error code
  // error.message contains description

  if (error.reason === 'WRONG_MEETING_PASSWORD') {
    alert('Incorrect password');
  }
}
```

### Listen for Connection Changes

```javascript
// Client View
ZoomMtg.inMeetingServiceListener('onMeetingStatus', (data) => {
  // status: 1=connecting, 2=connected, 3=disconnected, 4=reconnecting
  if (data.status === 3) {
    console.error('Disconnected:', data.errorCode);
  }
});

// Component View
client.on('connection-change', (payload) => {
  if (payload.state === 'Closed') {
    console.error('Connection closed:', payload.reason);
  }
});
```

## Common Error Scenarios

### "Signature is invalid" (3712)

**Causes:**
1. SDK Secret doesn't match SDK Key
2. Signature generated with wrong algorithm (must be HS256)
3. Clock skew between server and Zoom
4. Missing or incorrect `appKey` field in signature

**Debug Steps:**
1. Verify SDK Key and Secret in Marketplace
2. Check signature generation code
3. Ensure server time is accurate (NTP sync)
4. Test with official [auth-endpoint-sample](https://github.com/zoom/meetingsdk-auth-endpoint-sample)

### "Meeting does not exist" (3001/3610)

**Causes:**
1. Typo in meeting number
2. Meeting was deleted
3. Meeting ID vs Meeting Number confusion

**Note:** Meeting ID (from API) and Meeting Number (shown in client) are the same.

### "Anonymous join not allowed" (4012)

**Causes:**
1. Joining meeting outside your account without authorization
2. No OBF or ZAK token provided

**Solutions:**
1. For bots: Use App Privilege Token (OBF)
2. For users: Get their ZAK token
3. For same-account meetings: No token needed

### "Cross-account join blocked" (4011)

**Cause:** Your app isn't published on Marketplace and is trying to join meetings outside your account.

**Solutions:**
1. Publish your app on Zoom Marketplace
2. Or only join meetings within your account
3. Or use OBF token for authorization

## OBF Token Timeline

| Date | Enforcement |
|------|-------------|
| **February 7, 2026** | If OBF provided, must be valid (not expired/malformed) |
| **March 2, 2026** | Cannot join external meetings without valid OBF/ZAK |

## Additional Resources

- [OBF FAQ](https://developers.zoom.us/docs/meeting-sdk/obf-faq/)
- [Signature Generation](https://developers.zoom.us/docs/meeting-sdk/auth/)
- [ZAK Token API](https://developers.zoom.us/docs/api/users/#tag/users/get/users/me/zak)
