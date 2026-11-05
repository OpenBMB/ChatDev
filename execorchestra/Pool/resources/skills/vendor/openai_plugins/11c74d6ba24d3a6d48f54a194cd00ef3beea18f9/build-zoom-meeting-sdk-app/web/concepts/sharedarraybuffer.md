# SharedArrayBuffer for Zoom Meeting SDK Web

SharedArrayBuffer (SAB) is a web API that enables shared memory in JavaScript, significantly improving performance for WebAssembly-based features. Zoom uses SharedArrayBuffer to power advanced features.

## Why SharedArrayBuffer Matters

**Features that REQUIRE SharedArrayBuffer:**
- 720p video sending (HD)
- 1080p video for webinar attendees
- Gallery view (up to 25 videos)
- Virtual backgrounds
- Background noise suppression
- Share tab audio (Chrome/Edge)

**Without SharedArrayBuffer:**
- Video limited to standard definition
- Gallery view may show fewer participants
- Virtual backgrounds unavailable
- Some performance features degraded

> **Note**: SharedArrayBuffer is NOT required for basic meeting functionality or WebRTC. The SDK will work without it, but with limited features.

## How to Enable SharedArrayBuffer

SharedArrayBuffer requires **Cross-Origin Isolation**. You must configure your server to send specific HTTP headers.

### Quick Comparison of Methods

| Method | Type | Custom Headers Required | Best For |
|--------|------|------------------------|----------|
| **Cross-Origin Isolation** | Permanent | Yes | Production |
| **Credentialless Headers** | Permanent | Yes | Production with 3rd-party content |
| **Document-Isolation-Policy** | Permanent | Yes | Chrome/Edge 137+ with iframes |
| **Service Workers** | Permanent | No | GitHub Pages, static hosts |
| **Chrome Origin Trials** | Temporary | No | Testing only (renew every 3 months) |

## Implementation Methods

### Method 1: Cross-Origin Isolation (Recommended)

Add these headers to ALL responses from your server:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

**Pros**: Industry standard, works across all browsers
**Cons**: May break third-party iframes/content without CORS headers

### Method 2: Credentialless Headers

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: credentialless
```

**Pros**: More compatible with third-party content
**Cons**: Same browser support as Method 1

### Method 3: Document-Isolation-Policy (Chrome/Edge 137+)

```
Document-Isolation-Policy: isolate-and-require-corp
# OR
Document-Isolation-Policy: isolate-and-credentialless
```

**Pros**: Allows embedding third-party iframes, videos, payment gateways
**Cons**: Chrome/Edge 137+ only (desktop)

### Method 4: Service Worker (No Server Headers)

For platforms that don't allow custom headers (GitHub Pages):

1. Add [coi-serviceworker](https://github.com/gzuidhof/coi-serviceworker) to your project:

```html
<!-- Add before any other scripts -->
<script src="coi-serviceworker.js"></script>
```

2. Place `coi-serviceworker.js` in your root directory

**Pros**: Works on static hosting without header control
**Cons**: Adds slight overhead, requires service worker support

### Method 5: Chrome Origin Trials (Temporary)

1. Register at [Chrome Origin Trials](https://developer.chrome.com/origintrials/#/trials/active)
2. Add meta tag to your page:

```html
<meta http-equiv="origin-trial" content="YOUR_TOKEN_HERE" />
```

**Pros**: Quick testing without server changes
**Cons**: Must renew every 3 months, will be deprecated

## Platform-Specific Configuration

### Vercel

**Next.js (next.config.js):**
```javascript
module.exports = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'require-corp',
          },
        ],
      },
    ];
  },
};
```

**Non-Next.js (vercel.json):**
```json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "Cross-Origin-Opener-Policy", "value": "same-origin" },
        { "key": "Cross-Origin-Embedder-Policy", "value": "require-corp" }
      ]
    }
  ]
}
```

### Netlify (_headers file)

Create `_headers` in your publish directory:

```
/*
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Embedder-Policy: require-corp
```

### AWS CloudFront

Use CloudFront Response Headers Policy:

1. Go to CloudFront > Policies > Response headers
2. Create custom policy with:
   - `Cross-Origin-Opener-Policy: same-origin`
   - `Cross-Origin-Embedder-Policy: require-corp`
3. Attach to your distribution

### Google App Engine (app.yaml)

```yaml
handlers:
  - url: /.*
    static_files: index.html
    upload: index.html
    http_headers:
      Cross-Origin-Opener-Policy: same-origin
      Cross-Origin-Embedder-Policy: require-corp
```

### nginx

```nginx
server {
    location / {
        add_header Cross-Origin-Opener-Policy "same-origin" always;
        add_header Cross-Origin-Embedder-Policy "require-corp" always;
        # ... other config
    }
}
```

### Apache (.htaccess)

```apache
<IfModule mod_headers.c>
    Header set Cross-Origin-Opener-Policy "same-origin"
    Header set Cross-Origin-Embedder-Policy "require-corp"
</IfModule>
```

### Express.js

```javascript
app.use((req, res, next) => {
  res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
  res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
  next();
});
```

### GitHub Pages

GitHub Pages doesn't support custom headers. Use the **Service Worker method**:

1. Download [coi-serviceworker.js](https://github.com/gzuidhof/coi-serviceworker)
2. Place in repository root
3. Add to your HTML before other scripts:

```html
<script src="coi-serviceworker.js"></script>
```

## Verify SharedArrayBuffer is Enabled

### In Browser Console

```javascript
// Check if SharedArrayBuffer is available
console.log('SharedArrayBuffer:', typeof SharedArrayBuffer === 'function');

// Check cross-origin isolation
console.log('Cross-Origin Isolated:', window.crossOriginIsolated);
```

### In Your Application

```javascript
// Before initializing Zoom SDK
if (typeof SharedArrayBuffer !== 'function') {
  console.warn('SharedArrayBuffer not available. HD features will be limited.');
  console.warn('Enable COOP/COEP headers on your server.');
}

// Check isolation status
if (!window.crossOriginIsolated) {
  console.warn('Page is not cross-origin isolated.');
}
```

### Using Zoom SDK

```javascript
// Client View - use disableCORP for development without headers
ZoomMtg.init({
  disableCORP: !window.crossOriginIsolated,
  // ... other options
});
```

## Troubleshooting

### "SharedArrayBuffer is not defined"

**Cause**: Headers not configured or browser doesn't support cross-origin isolation.

**Fix**:
1. Verify headers are being sent (check Network tab in DevTools)
2. Ensure headers are on ALL responses (not just HTML)
3. Check for conflicting headers from CDN/proxy

### Third-Party Content Blocked

**Cause**: `require-corp` blocks resources without CORS headers.

**Fix**:
1. Use `credentialless` instead of `require-corp`
2. Or add `crossorigin="anonymous"` to external resources:
   ```html
   <img src="https://example.com/image.jpg" crossorigin="anonymous">
   ```

### Service Worker Not Working

**Cause**: Service worker not registered or not at root.

**Fix**:
1. Ensure `coi-serviceworker.js` is in the root directory
2. Check service worker is registered in DevTools > Application > Service Workers
3. Try hard refresh (Ctrl+Shift+R)

### Headers Present but SAB Still Unavailable

**Cause**: Possibly Chrome < 92 or other browser limitations.

**Fix**:
1. Update browser to latest version
2. Check if browsing in incognito (some extensions can interfere)
3. Verify both COOP and COEP headers are present

## Browser Support for SharedArrayBuffer

| Browser | Version | Notes |
|---------|---------|-------|
| Chrome | 92+ | Full support with COOP/COEP |
| Edge | 92+ | Full support with COOP/COEP |
| Firefox | 79+ | Full support with COOP/COEP |
| Safari | 15.2+ | Full support with COOP/COEP |
| iOS Safari | 15.2+ | Full support with COOP/COEP |
| Android Chrome | 92+ | Full support with COOP/COEP |

## Additional Resources

- [Why you need "cross-origin isolated" for powerful features](https://web.dev/articles/why-coop-coep)
- [Making your website "cross-origin isolated"](https://web.dev/articles/coop-coep)
- [coi-serviceworker GitHub](https://github.com/gzuidhof/coi-serviceworker)
- [Document-Isolation-Policy explainer](https://github.com/nickreese/nickreese.github.io/tree/main/document-isolation-policy)
