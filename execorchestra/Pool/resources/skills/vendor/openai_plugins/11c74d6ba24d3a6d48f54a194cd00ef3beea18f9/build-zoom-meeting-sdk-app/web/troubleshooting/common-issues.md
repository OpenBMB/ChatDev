# Common Issues - Zoom Meeting SDK Web

Quick diagnostics and solutions for the most common issues.

## Quick Diagnostic Workflow

```
1. Check browser console for errors
2. Verify signature is valid and not expired
3. Check COOP/COEP headers for HD features
4. Verify SDK version is supported
5. Test in Chrome/Edge first (most compatible)
```

## Initialization Issues

### "Meeting not initialized" (Error 2)

**Symptom**: SDK throws error when trying to join.

**Cause**: `join()` called before `init()` completed.

**Solution**:
```javascript
// WRONG
ZoomMtg.init({ leaveUrl: '...' });
ZoomMtg.join({ ... }); // Too early!

// CORRECT
ZoomMtg.init({
  leaveUrl: '...',
  success: () => {
    ZoomMtg.join({ ... }); // Wait for success callback
  }
});
```

### SDK Not Loading (CDN)

**Symptom**: `ZoomMtg is not defined`

**Cause**: Scripts not loaded in correct order.

**Solution**:
```html
<!-- Load in this exact order -->
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/react-dom.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/redux-thunk.min.js"></script>
<script src="https://source.zoom.us/{VERSION}/lib/vendor/lodash.min.js"></script>
<script src="https://source.zoom.us/zoom-meeting-{VERSION}.min.js"></script>
```

### Language Loading Timeout

**Symptom**: SDK hangs or UI shows wrong language.

**Cause**: `init()` called before language loaded.

**Solution**:
```javascript
ZoomMtg.i18n.load('en-US');
ZoomMtg.i18n.onLoad(() => {
  // ONLY init after language is loaded
  ZoomMtg.init({ ... });
});
```

## Authentication Issues

### "Signature is invalid" (Error 3712)

**Symptom**: Join fails with signature error.

**Causes & Solutions**:

1. **Wrong SDK Secret**
   ```bash
   # Verify in Zoom Marketplace > App > App Credentials
   ```

2. **Signature expired**
   ```javascript
   // Check signature expiration (default 2 hours)
   // Regenerate signature if needed
   ```

3. **Missing appKey prefix (v5.0.0+)**
   ```javascript
   // WRONG (pre-5.0 format)
   signature: "eyJhbGc..."

   // CORRECT (5.0+ format)
   signature: "appKey:sdkKey.eyJhbGc..."
   ```

4. **Wrong algorithm**
   ```javascript
   // MUST use HS256
   jwt.sign(payload, secret, { algorithm: 'HS256' });
   ```

### "API Key is invalid" (Error 3704)

**Symptom**: SDK Key rejected.

**Causes**:
1. Typo in SDK Key
2. SDK Key from different app type
3. SDK Key not activated

**Solution**: Verify SDK Key in Zoom Marketplace matches exactly.

### "SDK Key is disabled" (Error 3710)

**Symptom**: Previously working key now fails.

**Cause**: App deactivated in Marketplace.

**Solution**:
1. Go to Zoom Marketplace > Manage > Your Apps
2. Re-enable or create new app

## Join Issues

### "passWord" vs "password" Typo

**Symptom**: Join fails with password error even with correct password.

**Cause**: Different spelling between views!

**Solution**:
```javascript
// Client View - capital W
ZoomMtg.join({
  passWord: 'meeting123',  // Capital W!
});

// Component View - lowercase
client.join({
  password: 'meeting123',  // lowercase!
});
```

### "Meeting does not exist" (Error 3001/3610)

**Symptom**: Valid meeting number rejected.

**Causes & Solutions**:

1. **Wrong meeting number**
   - Check for typos
   - Use the 9-11 digit number, not Meeting ID from API

2. **Meeting deleted or expired**
   - Create new meeting

3. **Meeting not started yet**
   - Wait for host or enable "join before host"

### "Wrong meeting password" (Error 3004)

**Symptom**: Correct password rejected.

**Causes**:
1. Space/encoding issues in password
2. Password changed after you got it
3. Using URL-encoded password directly

**Solution**:
```javascript
// Extract password correctly from invite link
const url = new URL(inviteLink);
const password = url.searchParams.get('pwd');
```

### "Another meeting running" (Error 3005)

**Symptom**: Can't join new meeting.

**Cause**: User already in another SDK meeting instance.

**Solution**:
```javascript
// Leave current meeting first
ZoomMtg.leaveMeeting({});
// Then join new meeting
```

## HD Video Issues

### No HD Video / Low Quality

**Symptom**: Video stuck at low resolution.

**Cause**: SharedArrayBuffer not available.

**Diagnostic**:
```javascript
console.log('Cross-origin isolated:', window.crossOriginIsolated);
console.log('SharedArrayBuffer:', typeof SharedArrayBuffer === 'function');
```

**Solution**: Add COOP/COEP headers:
```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

See [concepts/sharedarraybuffer.md](../concepts/sharedarraybuffer.md) for details.

### Virtual Background Not Working

**Symptom**: Virtual background option missing or grayed out.

**Causes**:
1. SharedArrayBuffer not available
2. Browser not supported (Safari, iOS, Android)
3. Hardware limitations

**Solution**:
```javascript
// Check support first
ZoomMtg.isSupportVirtualBackground({
  success: (data) => {
    if (data.result.isSupport) {
      // VB supported
    } else {
      console.log('VB not supported:', data.result.reason);
    }
  }
});
```

## Event Listener Issues

### Callbacks Not Firing

**Symptom**: `inMeetingServiceListener` events never trigger.

**Causes & Solutions**:

1. **Registered too late**
   ```javascript
   // Register BEFORE or AFTER init, but make sure SDK is ready
   ZoomMtg.inMeetingServiceListener('onUserJoin', callback);
   ```

2. **Wrong event name**
   ```javascript
   // Event names are case-sensitive
   'onUserJoin'  // Correct
   'OnUserJoin'  // Wrong
   'on-user-join' // Wrong
   ```

3. **Meeting not fully joined**
   ```javascript
   // Wait for join success before expecting events
   ZoomMtg.join({
     success: () => {
       // Now events will fire
     }
   });
   ```

### Component View Events Not Firing

**Symptom**: `client.on()` callbacks never trigger.

**Solution**:
```javascript
// Component View uses different event names
client.on('connection-change', callback);  // Not 'onMeetingStatus'
client.on('user-added', callback);          // Not 'onUserJoin'
client.on('user-removed', callback);        // Not 'onUserLeave'
```

## Browser-Specific Issues

### Safari Screen Share Not Working

**Symptom**: Screen share option missing on Safari.

**Cause**: Requires Safari 17+ with macOS Sonoma for Client View.

**Solution**:
- Use Component View (works with earlier Safari)
- Or instruct users to use Chrome/Edge

### Firefox WebRTC Issues

**Symptom**: Video issues on Firefox.

**Cause**: Firefox uses different WebRTC implementation.

**Solution**: Test in Chrome first, then adapt for Firefox.

### Mobile Browser Limitations

**Symptom**: Features missing on mobile.

**Reality**: These features are NOT supported on mobile browsers:
- Screen share (send)
- Virtual backgrounds
- Whiteboard editing
- Remote control

**Solution**: Detect mobile and adjust UI accordingly:
```javascript
const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
if (isMobile) {
  // Hide unsupported feature buttons
}
```

## CORS Issues

### "Blocked by CORS policy"

**Symptom**: SDK resources blocked.

**Solution 1**: Use helper.html
```javascript
ZoomMtg.init({
  helper: './helper.html',
  // ...
});
```

**Solution 2**: Configure CSP headers
```
Content-Security-Policy:
  script-src 'self' 'unsafe-inline' 'unsafe-eval' https://zoom.us *.zoom.us blob:;
  connect-src 'self' https://zoom.us https://*.zoom.us wss://*.zoom.us;
```

### WebAssembly CORS Error

**Symptom**: "Failed to load WebAssembly module"

**Cause**: WASM files blocked by CSP.

**Solution**: Add `wasm-unsafe-eval` or `unsafe-eval` to script-src:
```
script-src 'self' 'wasm-unsafe-eval' ...
```

## React Integration Issues

### Client Recreated on Every Render

**Symptom**: Multiple SDK instances, memory leaks.

**Cause**: `createClient()` in component body.

**Solution**:
```javascript
// WRONG
function App() {
  const client = ZoomMtgEmbedded.createClient(); // Created every render!
}

// CORRECT
function App() {
  const clientRef = useRef<typeof client | null>(null);

  useEffect(() => {
    if (!clientRef.current) {
      clientRef.current = ZoomMtgEmbedded.createClient();
    }
  }, []);
}
```

### "Cannot read property of null" on Container

**Symptom**: Error when initializing Component View.

**Cause**: Container element not ready.

**Solution**:
```javascript
// WRONG
await client.init({
  zoomAppRoot: document.getElementById('meeting'), // Might be null
});

// CORRECT (React)
const containerRef = useRef<HTMLDivElement>(null);

useEffect(() => {
  if (containerRef.current) {
    client.init({ zoomAppRoot: containerRef.current });
  }
}, []);

return <div ref={containerRef} />;
```

## Performance Issues

### Slow Join Time

**Causes & Solutions**:

1. **Not preloading WASM**
   ```javascript
   // Call early, before user clicks join
   ZoomMtg.preLoadWasm();
   ZoomMtg.prepareWebSDK();
   ```

2. **Network latency**
   - Use China CDN for China users
   - Self-host assets with `assetPath`

3. **Large bundle**
   - Use code splitting
   - Lazy load SDK

### Memory Leaks

**Symptom**: Browser memory grows over time.

**Causes**:
1. Multiple SDK instances
2. Not cleaning up on unmount
3. Event listeners not removed

**Solution**:
```javascript
ZoomMtg.init({
  leaveOnPageUnload: true,  // Auto cleanup
});
```

## Debug Mode

### Enable Debug Logging

**Client View**:
```javascript
ZoomMtg.init({
  debug: true,  // Logs to console
});
```

**Component View**:
```javascript
client.init({
  debug: true,
});
```

### Mobile Debugging

```javascript
// Use vConsole for mobile debugging
if (/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
  const vConsole = new VConsole();
}
```

## Getting Help

1. **Check error codes**: [troubleshooting/error-codes.md](error-codes.md)
2. **Official docs**: https://developers.zoom.us/docs/meeting-sdk/web/
3. **Developer forum**: https://devforum.zoom.us/
4. **GitHub issues**: https://github.com/zoom/meetingsdk-web-sample/issues
