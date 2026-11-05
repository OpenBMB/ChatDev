# Get Started with Zoom Cobrowse SDK

Complete setup guide from credentials to your first cobrowse session.

## Overview

In a cobrowse session, there are **two roles**:

- **Customer** (role_type=1) – Integrates the SDK into their website
- **Agent** (role_type=2) – Uses an embedded iframe to interact with the customer

This guide shows you how to set up a **customer-initiated session** (the most common pattern).

## Step 1: Get SDK Credentials

### Requirements

1. **Zoom Workplace Account** with SDK Universal Credit
   - See [Build platform - create or update account](https://developers.zoom.us/docs/build/account/) for details

2. **Video SDK App** in Zoom Marketplace
   - Cobrowse SDK is a **feature of Video SDK** (not a separate product)

### Get Your Credentials

1. Access your SDK account web portal:
   - In your Zoom Workplace account, go to **Advanced** > **Zoom CPaaS** > **Manage**

2. Click **Build App**

3. Locate your **SDK credentials** in the Cobrowse tab

You'll receive **4 credentials**:

| Credential | Type | Purpose |
|------------|------|---------|
| **SDK Key** | Public | Used in CDN URL and JWT `app_key` claim |
| **SDK Secret** | Private | Used to sign JWTs (server-side only) |
| **API Key** | Private | REST API authentication (optional) |
| **API Secret** | Private | REST API authentication (optional) |

**Save these credentials securely** - you'll need them in the next step.

## Step 2: Generate JWT Tokens

Both customers and agents require JSON Web Tokens (JWTs) for authentication.

### JWT Structure

All JWTs have the same header:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

The payload differs by role:

**Customer JWT payload** (role_type=1):
```json
{
  "user_id": "user1_customer",
  "app_key": "YOUR_SDK_KEY",
  "role_type": 1,
  "user_name": "customer",
  "exp": 1723103759,
  "iat": 1723102859
}
```

**Agent JWT payload** (role_type=2):
```json
{
  "user_id": "user2_agent",
  "app_key": "YOUR_SDK_KEY",
  "role_type": 2,
  "user_name": "agent",
  "exp": 1723103759,
  "iat": 1723102859
}
```

### JWT Payload Fields

| Field | Required | Description |
|-------|----------|-------------|
| `app_key` | Yes | Your Zoom SDK Key (not API Key) |
| `role_type` | Yes | User role: `1` = customer, `2` = agent |
| `iat` | Yes | Token issue timestamp (epoch) |
| `exp` | Yes | Token expiration timestamp (epoch). Min: 30 minutes, Max: 48 hours |
| `user_id` | Yes | Uniquely identifiable user ID |
| `user_name` | Yes | User name (max 80 characters) |
| `enable_byop` | Optional | Enable Bring Your Own PIN: `1` = yes, `0` or omit = no |

### Sign the JWT

Sign the JWT with your SDK Secret (not API Secret):

```javascript
HMACSHA256(
  base64UrlEncode(header) + '.' + base64UrlEncode(payload),
  ZOOM_SDK_SECRET
);
```

### Set Up a Token Server

**CRITICAL**: JWT signing must happen **server-side** to protect your SDK Secret.

Use the official auth endpoint sample:

```bash
# Clone the sample
git clone https://github.com/zoom/cobrowsesdk-auth-endpoint-sample.git
cd cobrowsesdk-auth-endpoint-sample

# Install dependencies
npm install

# Create .env file
cat > .env << EOF
ZOOM_SDK_KEY=your_sdk_key_here
ZOOM_SDK_SECRET=your_sdk_secret_here
PORT=4000
EOF

# Start the server
npm start
```

The server will run on the base URL you configure for your token service.

**Token Request:**
```javascript
// POST https://YOUR_TOKEN_SERVICE_BASE_URL
{
  "role": 1,           // 1 = customer, 2 = agent
  "userId": "user123",
  "userName": "John Doe"
}

// Response
{
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**See also**: [JWT Authentication Concept](concepts/jwt-authentication.md)

## Step 3: Integrate the Customer SDK

The customer integrates the Cobrowse SDK into their website using the **CDN**.

> **Critical PIN Rule**
>
> The PIN agents should use comes from customer SDK event `pincode_updated`.
> Do not show or rely on provisional PIN values from backend/session placeholders.
> In UI, display one explicit value (for example, **Support PIN**) and pass only that to agent flow.

### Load the SDK

Include the SDK snippet in the `<head>` tag of your HTML page:

```html
<script type="module">
  const ZOOM_SDK_KEY = 'YOUR_SDK_KEY';

  (function (r, a, b, f, c, d) {
    r[f] = r[f] || {
      init: function () {
        r.ZoomCobrowseSDKInitArgs = arguments;
      },
    };
    var fragment = a.createDocumentFragment();
    function loadJs(url) {
      c = a.createElement(b);
      d = a.getElementsByTagName(b)[0];
      c.async = false;
      c.src = url;
      fragment.appendChild(c);
    }
    loadJs(
      `https://us01-zcb.zoom.us/static/resource/sdk/${ZOOM_SDK_KEY}/js/2.13.2`
    );
    d.parentNode.insertBefore(fragment, d);
  })(window, document, 'script', 'ZoomCobrowseSDK');
</script>
```

### SDK Version

Set the SDK VERSION using semantic versioning:

- **Fixed version**: `js/2.13.2` - Use exact version 2.13.2
- **Latest patch**: `js/2.13.x` - Use latest `>=2.13.0 and <2.14.0`

**Current version**: 2.13.2 (as of February 2026)

### Initialize the SDK

```javascript
const settings = {
  allowCustomerAnnotation: true,
  piiMask: { maskType: 'all_input' },
};

ZoomCobrowseSDK.init(settings, function ({ success, session, error }) {
  if (success) {
    console.log("SDK initialized successfully");
    // session object is now available
  } else {
    console.error("SDK init failed:", error);
  }
});
```

### Start a Session

```javascript
// Fetch JWT from your server
const response = await fetch('https://YOUR_TOKEN_SERVICE_BASE_URL', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    role: 1,
    userId: 'customer_' + Date.now(),
    userName: 'Customer'
  })
});
const { token } = await response.json();

// Start cobrowse session
session.start({ sdkToken: token });
```

### Complete Customer Example

```html
<!DOCTYPE html>
<html>
<head>
  <title>Customer - Cobrowse Support</title>
  <script type="module">
    const ZOOM_SDK_KEY = 'YOUR_SDK_KEY';

    // Load SDK from CDN
    (function(r, a, b, f, c, d) {
      r[f] = r[f] || { init: function() { r.ZoomCobrowseSDKInitArgs = arguments }};
      var fragment = a.createDocumentFragment();
      function loadJs(url) {
        c = a.createElement(b);
        d = a.getElementsByTagName(b)[0];
        c["async"] = false;
        c.src = url;
        fragment.appendChild(c);
      }
      loadJs(`https://us01-zcb.zoom.us/static/resource/sdk/${ZOOM_SDK_KEY}/js/2.13.2`);
      d.parentNode.insertBefore(fragment, d);
    })(window, document, "script", "ZoomCobrowseSDK");
  </script>
</head>
<body>
  <h1>Need Help?</h1>
  <button id="cobrowse-btn" disabled>Loading...</button>
  <div id="pin-display"></div>

  <script type="module">
    let sessionRef = null;

    const settings = {
      allowAgentAnnotation: true,
      allowCustomerAnnotation: true,
      piiMask: {
        maskType: "custom_input",
        maskCssSelectors: ".sensitive-field"
      }
    };

    ZoomCobrowseSDK.init(settings, function({ success, session, error }) {
      if (success) {
        sessionRef = session;

        // Listen for PIN code
        session.on("pincode_updated", (payload) => {
          console.log("PIN Code:", payload.pincode);
          // This is the authoritative PIN for agent join
          document.getElementById("pin-display").innerHTML =
            `<p><strong>Your PIN:</strong> ${payload.pincode}</p>
             <p>Share this with your support agent</p>`;
        });

        // Enable button
        document.getElementById("cobrowse-btn").disabled = false;
        document.getElementById("cobrowse-btn").innerText = "Start Support Session";
      } else {
        console.error("SDK init failed:", error);
      }
    });

    // Handle button click
    document.getElementById("cobrowse-btn").addEventListener("click", async () => {
      try {
        // Fetch JWT from your server
        const response = await fetch("https://YOUR_TOKEN_SERVICE_BASE_URL", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: 1,
            userId: "customer_" + Date.now(),
            userName: "Customer"
          })
        });
        const { token } = await response.json();

        // Start session
        sessionRef.start({ sdkToken: token });
      } catch (error) {
        console.error("Failed to start session:", error);
      }
    });
  </script>
</body>
</html>
```

## Step 4: Use Zoom-Hosted Agent Portal

Agents connect to cobrowse sessions by embedding an iframe.

### Agent Portal Iframe

```html
<!DOCTYPE html>
<html>
<head>
  <title>Agent Portal</title>
</head>
<body>
  <h1>Agent Support Portal</h1>
  <iframe
    id="agent-iframe"
    width="1024"
    height="768"
    src=""
    allow="autoplay *; camera *; microphone *; display-capture *; geolocation *;"
  ></iframe>

  <script>
    async function connectAgent() {
      try {
        // Fetch JWT from your server
        const response = await fetch("https://YOUR_TOKEN_SERVICE_BASE_URL", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: 2,
            userId: "agent_" + Date.now(),
            userName: "Support Agent"
          })
        });
        const { token } = await response.json();

        // Load Zoom agent portal with token
        const iframe = document.getElementById("agent-iframe");
        iframe.src = `https://us01-zcb.zoom.us/sdkapi/zcb/frame-templates/desk?access_token=${token}`;
      } catch (error) {
        console.error("Failed to connect agent:", error);
      }
    }

    // Auto-connect on page load
    connectAgent();
  </script>
</body>
</html>
```

### Iframe Permissions

The `allow` attribute must include these permissions:

- `autoplay *` - Auto-play media
- `camera *` - Camera access
- `microphone *` - Microphone access
- `display-capture *` - Screen capture
- `geolocation *` - Location services

## Step 5: Test the Cobrowse SDK

### Testing Steps

1. **Open two browsers** (or use incognito + normal mode):
   - Browser A: Customer page
   - Browser B: Agent page

2. **Customer browser**:
   - Open customer page
   - Click "Start Support Session" button
   - Note the 6-digit PIN displayed

3. **Agent browser**:
   - Open agent page
   - Enter the PIN code in the iframe

4. **Verify connection**:
   - Agent should now see the customer's browser
   - Both sides should show "Connected" status

5. **Test features**:
   - **Annotations**: Agent can draw on the screen
   - **Data masking**: Masked fields show asterisks for agent
   - **Remote assist**: Agent can scroll the page (if enabled)

6. **End session**:
   - Either side can click "End Session" to terminate

### Troubleshooting Test Issues

| Issue | Solution |
|-------|----------|
| SDK doesn't load | Verify SDK Key is correct in CDN URL |
| PIN not showing | Check browser console for errors |
| Agent can't connect | Verify PIN is correct and session is still active |
| Connection fails | Check HTTPS is being used (or a loopback host for development) |

## Step 6: Add Features

Now that you have a working cobrowse session, add features:

### Annotation Tools

Enable drawing tools for customer and/or agent:

```javascript
const settings = {
  allowAgentAnnotation: true,      // Agent can draw
  allowCustomerAnnotation: true    // Customer can draw
};
```

**See**: [Annotation Tools Example](examples/annotations.md)

### Data Masking

Hide sensitive fields from agents:

```javascript
const settings = {
  piiMask: {
    maskType: 'custom_input',
    maskCssSelectors: '.sensitive-field, #ssn, #credit-card',
    maskHTMLAttributes: 'data-sensitive=true'
  }
};
```

**See**: [Privacy Masking Example](examples/privacy-masking.md)

### Remote Assist

Allow agent to scroll the customer's page:

```javascript
const settings = {
  remoteAssist: {
    enable: true,
    enableCustomerConsent: true,        // Customer must approve
    remoteAssistTypes: ['scroll_page']
  }
};
```

**See**: [Remote Assist Example](examples/remote-assist.md)

### Bring Your Own PIN (BYOP)

Use custom PIN codes instead of auto-generated ones:

1. Enable BYOP in JWT payload:
   ```json
   {
     "enable_byop": 1,
     ...
   }
   ```

2. Provide custom PIN when starting session:
   ```javascript
   session.start({
     customPinCode: 'MYPIN123',
     sdkToken: token
   });
   ```

**See**: [BYOP Custom PIN Example](examples/byop-custom-pin.md)

## Next Steps

- **Learn core concepts**: [Session Lifecycle](concepts/session-lifecycle.md)
- **Explore features**: [Complete documentation index](SKILL.md)
- **Handle errors**: [Error Codes Reference](troubleshooting/error-codes.md)
- **Production checklist**: [CORS and CSP Configuration](troubleshooting/cors-csp.md)

## PIN Code Access - Bring Your Own PIN (BYOP)

The Cobrowse SDK supports connecting agents and customers using a PIN code. In the simple example above, Zoom automatically generates a 6-digit PIN code displayed to the customer.

**Auto-generated PIN flow:**
1. Customer clicks "Start Support Session"
2. Zoom generates 6-digit PIN
3. Customer shares PIN with agent
4. Agent enters PIN to connect

**Custom PIN flow (BYOP):**
1. Your app generates custom PIN code (1-10 characters, letters/numbers)
2. Pass PIN when starting session: `session.start({ customPinCode: 'MYPIN', sdkToken })`
3. Agent enters your custom PIN to connect

**BYOP enables**:
- Integration with existing support ticket systems
- Use of case/ticket IDs as PINs
- npm integration for custom agent UI

**See**: [Bring Your Own PIN (BYOP)](examples/byop-custom-pin.md) for complete guide.

## Resources

- **Official Docs**: https://developers.zoom.us/docs/cobrowse-sdk/
- **API Reference**: https://marketplacefront.zoom.us/sdk/cobrowse/
- **Quickstart Repo**: https://github.com/zoom/CobrowseSDK-Quickstart
- **Auth Endpoint Sample**: https://github.com/zoom/cobrowsesdk-auth-endpoint-sample
- **Dev Forum**: https://devforum.zoom.us/

## Common Questions

**Q: Can I use HTTP instead of HTTPS?**
A: Only for loopback/local development. Production must use HTTPS.

**Q: What's the difference between SDK Key and API Key?**
A: SDK Key is used in the CDN URL and JWT `app_key` claim. API Key is for optional REST API calls.

**Q: Can multiple agents join the same session?**
A: Yes, up to 5 agents can join a single customer session.

**Q: Does the customer need to install anything?**
A: No, it's pure JavaScript delivered via CDN. No plugins or extensions needed.

**Q: What happens if the customer refreshes the page?**
A: The session will attempt to automatically reconnect within a 2-minute window.

**Q: Can I customize the agent portal UI?**
A: Not with the iframe approach. For custom UI, use npm integration with BYOP mode.
