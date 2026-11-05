# Browser Support for Zoom Meeting SDK Web

The Zoom Meeting SDK for Web supports browsers within **two versions** of their current release. This document details feature support by browser.

## Feature Support Matrix

| Feature | Chrome | Firefox | Safari | Edge | iOS/iPadOS | Android |
|---------|--------|---------|--------|------|------------|---------|
| **Video** |
| 720p Video (receive) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 720p Video (send) | ✅¹ | ✅¹ | ✅¹ | ✅¹ | ✅¹ | ✅¹ |
| 1080p (webinar attendees) | ✅¹ | ✅¹ | ✅¹ | ✅¹ | ✅¹ | ✅¹ |
| Gallery View (25 videos) | ✅ | ✅ | ✅² | ✅ | ✅ | ✅ |
| Virtual Background | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| WebRTC Video | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Audio** |
| Audio (receive) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Audio (send) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Background Noise Suppression | ✅¹ | ✅¹ | ✅¹ | ✅¹ | ✅¹ | ✅¹ |
| Share Tab Audio | ✅¹ | ❌ | ❌ | ✅¹ | ❌ | ❌ |
| Call In (PSTN) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Call Out (PSTN) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Screen Sharing** |
| Screen Share (receive) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Screen Share (send) | ✅ | ✅ | ✅³ | ✅ | ❌ | ❌ |
| Remote Control (give) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Be Remote Controlled | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Meeting Features** |
| Breakout Rooms | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Waiting Room | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| In-Meeting Chat | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chat - Send File | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cloud Recording | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Closed Captioning | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Live Transcription | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Live Translation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| RTMP Live Streaming | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Webinar Q&A | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Whiteboard** |
| Whiteboard (view) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Whiteboard (edit) | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Other** |
| Stay Awake (Component View) | ✅⁴ | ❌ | ✅⁴ | ✅⁴ | ❌ | ❌ |
| Encryption (TLS 1.2 + AES-GCM) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| End-to-End Encryption (E2EE) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Footnotes

1. **Requires SharedArrayBuffer** - Must enable COOP/COEP headers. See [sharedarraybuffer.md](sharedarraybuffer.md).
2. **Safari Gallery View** - Requires Safari 17.0+, macOS Sonoma, and SDK v2.18.0+.
3. **Safari Screen Share** - Component View supported. Client View requires Safari 17+ with macOS 14 Sonoma+.
4. **Stay Awake** - Chrome 116+, Edge 90+, Safari 16.4+. Uses [WakeLock API](https://developer.mozilla.org/en-US/docs/Web/API/WakeLock).

## Version Support Policy

Zoom supports the current browser version plus two previous versions:

| If Current Version Is | Supported Versions |
|-----------------------|-------------------|
| Chrome 140 | 138, 139, 140 |
| Firefox 130 | 128, 129, 130 |
| Safari 18 | 16, 17, 18 |
| Edge 130 | 128, 129, 130 |

## Mobile and Tablet Browser Support

### iOS and iPadOS

All browsers on iOS/iPadOS use the same WebKit engine (including Chrome and Firefox on iOS). Features are determined by **iOS version**, not browser version.

| iOS Version | Key Capabilities |
|-------------|------------------|
| iOS 15.2+ | SharedArrayBuffer support |
| iOS 16.4+ | 720p in landscape mode, WakeLock |
| iOS 17+ | Improved WebRTC performance |

### Android

Most Android browsers are Chromium-based. Features depend on **Android OS version** and **Chrome version**.

| Android Version | Notes |
|-----------------|-------|
| Android 10+ | Full support |
| Chrome 112+ | 720p in landscape mode |

**Important**: Android Firefox is NOT supported (uses GeckoView engine).

### Samsung Internet

Samsung Internet follows its [own versioning scheme](https://en.wikipedia.org/wiki/Samsung_Internet#History) but is Chromium-based:

| Samsung Internet | Chromium Base |
|------------------|---------------|
| 20.0 | Chromium 106 |
| 21.0 | Chromium 111 |
| 22.0 | Chromium 118 |

### Tablets

| Device Type | Browser Support |
|-------------|-----------------|
| iPad | Same as iOS Safari |
| Android Tablets | Same as Android browsers |
| Microsoft Surface | Same as Windows desktop browsers |
| Chromebooks | Same as Chrome desktop |

## WebRTC Support Details

WebRTC video is supported on:

- **Chrome**: Windows, macOS, Android, iOS, ChromeOS
- **Edge**: Windows
- **Safari**: macOS, iOS (WebKit-based browsers)

Some Android device models have specific limitations due to hardware variations.

## Content Security Policy (CSP)

If you use Content Security Policy headers, configure them to allow Zoom SDK:

```
Content-Security-Policy:
  default-src 'self';
  base-uri 'self';
  worker-src blob:;
  style-src 'self' 'unsafe-inline';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' https://zoom.us *.zoom.us dmogdx0jrul3u.cloudfront.net blob:;
  connect-src 'self' https://zoom.us https://*.zoom.us wss://*.zoom.us;
  img-src 'self' https:;
  media-src 'self' https:;
  font-src 'self' https:;
```

### CSP Error: WebAssembly.instantiate()

If you see this error:

```
CompileError: WebAssembly.instantiate(): Refused to compile...
```

Add `'unsafe-eval'` or `'wasm-unsafe-eval'` (if browser supports it) to your `script-src` directive.

## Known Limitations

### All Browsers
- **E2EE not supported** on any web browser
- **Cannot be remote-controlled** (browsers don't support this)

### Safari
- No virtual background support
- Screen share (send) limited to Safari 17+ on macOS Sonoma
- No tab audio sharing

### Firefox
- No WebRTC video (uses different implementation)
- No tab audio sharing
- No Stay Awake feature

### Mobile (iOS/Android)
- No screen share sending
- No virtual backgrounds
- No whiteboard editing
- No Stay Awake feature
- No remote control

## Checking Browser Compatibility

### In Your Application

```javascript
// Client View
const requirements = ZoomMtg.checkSystemRequirements();
console.log('Browser compatible:', requirements.browserInfo);

// Component View
const requirements = client.checkSystemRequirements();
console.log('Video supported:', requirements.video);
console.log('Audio supported:', requirements.audio);
console.log('Screen share supported:', requirements.screen);
```

### Feature Detection

```javascript
// Check SharedArrayBuffer for HD features
const hasHD = typeof SharedArrayBuffer === 'function';

// Check screen capture support
const hasScreenShare = navigator.mediaDevices &&
                       typeof navigator.mediaDevices.getDisplayMedia === 'function';

// Check WebRTC support
const hasWebRTC = !!(window.RTCPeerConnection ||
                     window.webkitRTCPeerConnection ||
                     window.mozRTCPeerConnection);

// Check WakeLock support (Stay Awake)
const hasWakeLock = 'wakeLock' in navigator;
```

## Recommendations

### For Maximum Compatibility
1. Use Chrome or Edge on desktop
2. Enable SharedArrayBuffer headers for HD features
3. Test on iOS Safari for mobile users
4. Provide fallback messaging for unsupported features

### For Virtual Backgrounds
- Require Chrome, Edge, or Firefox (desktop only)
- Ensure SharedArrayBuffer is enabled
- Safari users won't have this feature

### For Screen Sharing
- Desktop browsers only
- Safari users need macOS Sonoma + Safari 17+ for Client View
- Component View works on Safari with earlier versions

## Official Resources

- [Zoom Web Client Features](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0064261)
- [Zoom Platform Comparison](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065520)
