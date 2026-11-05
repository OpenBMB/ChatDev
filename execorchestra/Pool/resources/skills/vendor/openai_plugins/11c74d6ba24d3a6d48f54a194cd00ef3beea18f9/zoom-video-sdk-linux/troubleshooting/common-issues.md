# Common Issues and Solutions

## Session Join Issues

### Issue: "Failed to join session" (no error details)

**Causes**:
1. Invalid JWT token
2. Session name doesn't match JWT `tpc` claim
3. Wrong SDK credentials
4. Expired token

**Solution**:
```python
# Regenerate JWT token
import jwt
import time

payload = {
    "app_key": SDK_KEY,
    "iat": int(time.time()) - 30,
    "exp": int(time.time()) + 7200,
    "tpc": "exact-session-name",  # MUST match sessionName
    "role_type": 1  # 0=participant, 1=host
}
token = jwt.encode(payload, SDK_SECRET, algorithm="HS256")
```

### Issue: "Authentication failed"

**Solution**: Verify SDK_KEY and SDK_SECRET in JWT generation.

### Issue: Session requires password

**Solution**:
```cpp
session_context.sessionPassword = "password";
```

## Audio Issues

### Issue: No audio callbacks

**Cause**: PulseAudio not configured.

**Solution**: See [PulseAudio Setup](pulseaudio-setup.md).

### Issue: Audio on headless Linux

**Solution**: Use virtual audio:
```cpp
session_context.virtualAudioSpeaker = new VirtualSpeaker();
session_context.virtualAudioMic = new VirtualMic();
```

## Video Issues

### Issue: "Linux has no Canvas API!"

**Solution**: Use Raw Data Pipe. See [Raw Data vs Canvas](../concepts/raw-data-vs-canvas.md).

### Issue: Video frames not received

**Cause**: Not subscribing to user's video pipe.

**Solution**:
```cpp
void onUserVideoStatusChanged(..., IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
    for (int i = 0; i < userList->GetCount(); i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
        pipe->subscribe(ZoomVideoSDKResolution_720P, videoDelegate);
    }
}
```

## Build Issues

### Issue: "libQt5Core.so.5: not found"

**Solution**: See [Qt Dependencies](qt-dependencies.md).

### Issue: Undefined reference to SDK symbols

**Solution**: See [Build Errors](build-errors.md).

## Memory Issues

### Issue: Crashes with large video frames

**Solution**: Use heap memory mode:
```cpp
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
```

## SDK Init Error 7 (Invalid_Parameter)

`sdk->initialize(initParams)` returns error code 7 when:

1. **Domain is wrong** - Must be `"https://zoom.us"` (with protocol). Plain `"zoom.us"` causes error 7.
2. **PulseAudio is not running** - Headless Linux requires PulseAudio. See [PulseAudio Setup](pulseaudio-setup.md).
3. **Missing `~/.config/zoomus.conf`** - Must exist with content:
   ```
   [General]
   system.audio.type=default
   ```

## GLib Main Loop Required

The SDK internally uses Qt/GLib for event dispatching. A `while (running) { sleep(500ms); }` loop does NOT work — `onSessionJoin` and all other delegate callbacks will never fire.

You MUST use a GLib main loop:

```cpp
#include <glib.h>

static GMainLoop* loop = nullptr;

gboolean timeout_callback(gpointer data) {
    return TRUE;
}

loop = g_main_loop_new(NULL, FALSE);
g_timeout_add(100, timeout_callback, loop);
g_main_loop_run(loop);

if (loop) g_main_loop_quit(loop);
```

See [Session Join Pattern](../examples/session-join-pattern.md) for the complete working example.

## All SDK Calls Must Be Made from the Main Thread

ALL Zoom Video SDK API calls must be called from the GLib main thread. Calling SDK methods from a `std::thread` or any background thread returns `ZoomVideoSDKErrors_Internal_Error` (error code 2).

Use `g_idle_add()` to schedule SDK calls from background threads:

```cpp
struct CallContext {
    IZoomVideoSDK* sdk;
    std::string data;
};

static gboolean executeOnMainThread(gpointer data) {
    auto* ctx = static_cast<CallContext*>(data);
    // Make SDK calls here — this runs on the GLib main thread
    delete ctx;
    return G_SOURCE_REMOVE;
}

// From a background thread:
auto* ctx = new CallContext{sdk_, someData};
g_idle_add(executeOnMainThread, ctx);
```

`g_idle_add()` is thread-safe — it queues work onto the GLib main loop. See [Command Channel](../examples/command-channel.md) for a real-world example.

## Quick Diagnostic Checklist

- [ ] PulseAudio installed and configured
- [ ] ~/.config/zoomus.conf exists
- [ ] Qt5 libraries copied from SDK
- [ ] Qt5 symlinks created
- [ ] LD_LIBRARY_PATH set correctly
- [ ] JWT token valid and not expired
- [ ] Session name matches JWT `tpc` claim
- [ ] All delegate methods implemented
- [ ] Using heap memory mode
- [ ] Subscribing in correct callbacks
- [ ] Domain set to "https://zoom.us" (with protocol)
- [ ] Using GLib main loop (not while/sleep loop)
- [ ] SDK calls made from main thread only (use g_idle_add from background threads)

## Error Codes

| Code | Name | Meaning |
|------|------|---------|
| 0 | Success | Operation succeeded |
| 1001 | Auth_Error | Authentication failed |
| 1003 | Auth_Wrong_Token | Invalid JWT |
| 1004 | Auth_Expired_Token | JWT expired |
| 3001 | Session_Join_Failed | Failed to join |
| 3008 | Session_Need_Password | Password required |
| 3009 | Session_Password_Wrong | Wrong password |
| 7 | Invalid_Parameter | Wrong domain, missing PulseAudio, or missing zoomus.conf |
| 2 | Internal_Error | SDK method called from wrong thread (use g_idle_add) |

## Getting Help

1. Check [Official Docs](https://developers.zoom.us/docs/video-sdk/linux/)
2. Search [Dev Forum](https://devforum.zoom.us/)
3. Review [GitHub Samples](https://github.com/zoom/videosdk-linux-raw-recording-sample)
