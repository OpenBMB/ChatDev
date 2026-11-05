# Cobrowse SDK - Get Started

Set up collaborative browsing on your website.

## Overview

This guide walks through integrating the Cobrowse SDK for customer-initiated sessions.

## Prerequisites

1. SDK Universal Credit on your Zoom account
2. SDK Key and Secret
3. Token server for JWT generation

## Step 1: Get SDK Credentials

1. In Zoom Workplace, go to **Advanced** → **Zoom CPaaS** → **Manage**
2. Click **Build App**
3. Locate **SDK Key** and **SDK Secret**

## Step 2: Set Up Token Server

Generate JWTs server-side to protect your SDK Secret.

```javascript
const jwt = require('jsonwebtoken');

function generateCobrowseToken(userId, userName, roleType) {
  const iat = Math.floor(Date.now() / 1000);
  const exp = iat + 3600; // 1 hour

  const payload = {
    user_id: userId,
    app_key: SDK_KEY,
    role_type: roleType,  // 1 = customer, 2 = agent
    user_name: userName,
    iat: iat,
    exp: exp
  };

  return jwt.sign(payload, SDK_SECRET, { algorithm: 'HS256' });
}
```

## Step 3: Integrate Customer SDK

Add to your website:

```html
<script src="https://cobrowse.zoom.us/sdk.js"></script>

<script>
async function startCobrowse() {
  // Get token from your server
  const token = await fetch('/api/cobrowse-token').then(r => r.json());

  const cobrowse = new ZoomCobrowse({
    sdkKey: 'YOUR_SDK_KEY',
    token: token.jwt
  });

  const session = await cobrowse.startSession();

  // Display PIN to customer
  alert(`Your session PIN: ${session.pin}`);
}
</script>

<button onclick="startCobrowse()">Start Support Session</button>
```

## Step 4: Set Up Agent View

Agents join via iframe:

```html
<iframe
  src="https://cobrowse.zoom.us/agent?pin={PIN}"
  allow="camera; microphone"
></iframe>
```

## Next Steps

- Configure [privacy masking](features.md#masking)
- Set up [annotations](features.md#annotations)
- Implement [Bring Your Own PIN](features.md#byop)

## Resources

- **Cobrowse docs**: https://developers.zoom.us/docs/cobrowse-sdk/get-started/
