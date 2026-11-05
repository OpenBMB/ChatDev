# Meeting SDK - Troubleshooting

Common issues and solutions for Meeting SDK.

## Overview

Troubleshooting guide for Meeting SDK across all platforms.

## Common Issues

### Join Meeting Failed

| Error | Possible Cause | Solution |
|-------|----------------|----------|
| Invalid signature | JWT malformed or expired | Regenerate signature server-side |
| Meeting not found | Invalid meeting number | Verify meeting exists |
| Wrong password | Password mismatch | Check meeting password |
| Meeting locked | Host locked meeting | Contact host |

**Note:** Error code 0 often means success - check the SDK enum values (e.g., `SDKERR_SUCCESS = 0`).

### Authentication Issues

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Auth failed | Invalid credentials | Check SDK Key/Secret |
| Token expired | JWT too old | Generate fresh signature |
| Signature invalid | Wrong secret used | Verify SDK Secret |

### No Video

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Black screen | Permission denied | Request camera permission |
| Video not starting | Camera in use | Close other camera apps |
| Poor quality | Low bandwidth | Check network |

### No Audio

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Can't hear | Audio not connected | Join audio |
| Muted | User is muted | Check mute state |
| Echo | No echo cancellation | Use headphones |

### Web-Specific Issues

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| SharedArrayBuffer error | Missing headers | Add COOP/COEP headers |
| Component not rendering | Wrong container | Check `zoomAppRoot` element |
| Toolbar/controls missing | Global CSS resets | Don't use `* { margin: 0; }` - scope styles to your app |
| Toolbar cropped/off-screen | Zoom UI exceeds viewport | Use `transform: scale(0.95)` on `#zmmtg-root` |
| `ZoomMtgEmbedded is undefined` | Using CDN but Component View API | CDN provides `ZoomMtg`, use npm for `ZoomMtgEmbedded` |

### Web: "Black Screen" After Join (UI Hidden Behind App)

If the meeting "joins" but you only see your app shell or a blank/black area, the Zoom UI may be rendered but **covered by your SPA layout**, modals, or fixed headers.

**Applies mostly to Client View**, and occasionally to Component View if your container is mis-sized/overlaid.

Fix (Client View):

```css
/* Ensure the root container occupies the viewport and sits above your app shell. */
#zmmtg-root {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  z-index: 9999 !important;
}
```

Be critical: if you still see a "black screen", it can also be:

- camera permission denied / no video started
- your container is `display:none` or has `height: 0` (Component View)
- global CSS resets breaking Zoom's layout

### UI Customization Confusion (Web)

If the question is about hiding passcode/invite URL or removing built-in controls:

- Confirm **Client View vs Component View**
- Prefer supported customization knobs (e.g., `customize.meetingInfo` in Component View)
- Avoid brittle CSS hacks unless there's no supported alternative

See:
- `web/references/component-view-ui-customization.md`

### Client View CSS Fixes

**Toolbar falling off screen:**
```css
#zmmtg-root {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  width: 100vw !important;
  height: 100vh !important;
  transform: scale(0.95) !important;
  transform-origin: top center !important;
}
```

**Hide your app when meeting starts:**
```css
body.meeting-active .your-app { display: none !important; }
body.meeting-active { background: #000 !important; }
```

## Collecting Logs

See [SDK Logs & Troubleshooting](../../general/references/sdk-logs-troubleshooting.md) for log collection.

## Getting Support

1. Collect SDK logs
2. Note SDK version and platform
3. Document steps to reproduce
4. Contact [Developer Support](https://devsupport.zoom.us/)

## Resources

- **Developer forum**: https://devforum.zoom.us/
- **Support**: https://devsupport.zoom.us/
