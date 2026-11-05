# Common Issues

Quick diagnostic guide for Zoom Video SDK Windows issues.

---

## Quick Diagnostic Checklist

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Callbacks don't fire | Missing message loop | [Windows Message Loop](windows-message-loop.md) |
| Build errors | Include order / missing headers | [Build Errors](build-errors.md) |
| Abstract class error | Missing delegate methods | [Delegate Methods](../references/delegate-methods.md) |
| Video subscribe fails | Subscribing too early | Subscribe in `onUserVideoStatusChanged` |
| Error code 2 | Video not ready | Wait for `status.isOn == true` |
| Error code 8 | Too frequent calls | Add `Sleep(200)` between calls |
| DLL not found | DLLs not copied | Copy SDK `bin\` to output |

---

## Error Codes (ZoomVideoSDKErrors)

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| 0 | Success | Operation succeeded | - |
| 1 | Wrong_Usage | API called incorrectly | Check API documentation |
| 2 | Internal_Error | SDK internal error | Often: video not ready yet |
| 3 | Uninitialize | SDK not initialized | Call `initialize()` first |
| 4 | Memory_Error | Memory allocation failed | Check system resources |
| 5 | Load_Module_Error | Failed to load DLL | Check DLLs are present |
| 6 | UnLoad_Module_Error | Failed to unload DLL | - |
| 7 | Invalid_Parameter | Bad parameter | Check NULL pointers, HWNDs |
| 8 | Call_Too_Frequently | API called too often | Add `Sleep(200)` |
| 9 | No_Impl | Feature not implemented | - |
| 10 | Dont_Support_Feature | Feature not supported | Check SDK version |
| 100 | Unknown | Unknown error | Check logs |

### Auth Errors (1000+)

| Code | Name | Solution |
|------|------|----------|
| 1001 | Auth_Error | Check JWT token |
| 1002 | Auth_Empty_Key_or_Secret | Provide credentials |
| 1003 | Auth_Wrong_Key_or_Secret | Verify credentials |
| 1004 | Auth_DoesNot_Support_SDK | Check SDK version |
| 1005 | Auth_Disable_SDK | Contact Zoom support |

### Session Errors (3000+)

| Code | Name | Solution |
|------|------|----------|
| 3001 | Session_Join_Failed | Check session name/token |
| 3002 | Session_No_Rights | Check permissions |
| 3003 | Session_Already_In_Progress | Leave first |
| 3005 | Session_Reconnecting | Wait for reconnect |
| 3008 | Session_Need_Password | Provide password |
| 3009 | Session_Password_Wrong | Check password |

---

## Subscribe Fail Reasons

When `onVideoCanvasSubscribeFail` fires:

| Code | Reason | Solution |
|------|--------|----------|
| 0 | None | - |
| 1 | HasSubscribe1080POr720P | Already have HD subscription |
| 2 | HasSubscribeTwo720P | Max 2x 720p |
| 3 | HasSubscribeExceededLimit | Too many subscriptions |
| 4 | HasSubscribeTwoShare | Max 2 share subscriptions |
| 5 | HasSubscribeVideo1080POr720PAndOneShare | Combined limit |
| 6 | TooFrequentCall | Add `Sleep(200)` |

---

## Common Issues by Category

### Session Issues

#### "joinSession returns success but onSessionJoin never fires"

**Cause**: Missing Windows message loop

**Fix**:
```cpp
while (!done) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    Sleep(10);
}
```

#### "Session join fails with error 3001"

**Cause**: Invalid JWT token or session name

**Fix**:
1. Verify JWT token is valid and not expired
2. Check session name matches token
3. Ensure token has correct role (host/attendee)

---

### Video Issues

#### "subscribeWithView returns error 2"

**Cause**: Video not ready when subscribing

**Fix**: Subscribe in `onUserVideoStatusChanged`, not `onUserJoin`:

```cpp
void onUserVideoStatusChanged(..., userList) override {
    for (auto user : userList) {
        if (user->GetVideoPipe()->getVideoStatus().isOn) {
            user->GetVideoCanvas()->subscribeWithView(hwnd, ...);
        }
    }
}
```

#### "Video shows black screen"

**Causes**:
1. Camera not started
2. Wrong HWND
3. Subscription failed silently

**Fixes**:
```cpp
// 1. Start your camera
sdk->getVideoHelper()->startVideo();

// 2. Verify HWND is valid and visible
HWND hwnd = CreateWindow(...);
ShowWindow(hwnd, SW_SHOW);

// 3. Check subscribe return value
ZoomVideoSDKErrors err = canvas->subscribeWithView(hwnd, ...);
if (err != ZoomVideoSDKErrors_Success) {
    std::cout << "Subscribe failed: " << err << std::endl;
}
```

#### "onVideoCanvasSubscribeFail fires with reason 6"

**Cause**: Calling subscribe too frequently

**Fix**: Add delay between subscribe calls:
```cpp
canvas->subscribeWithView(hwnd1, ...);
Sleep(200);  // Add delay
canvas->subscribeWithView(hwnd2, ...);
```

---

### Audio Issues

#### "No audio after joining"

**Cause**: Audio not connected

**Fix**: Connect audio in `onSessionJoin`:
```cpp
void onSessionJoin() override {
    sdk->getAudioHelper()->startAudio();
}
```

Also ensure `audioOption.connect = false` during join:
```cpp
context.audioOption.connect = false;  // Connect in callback
```

#### "Cannot mute/unmute"

**Cause**: Trying to control audio before connected

**Fix**: Wait for audio to be connected:
```cpp
void onUserAudioStatusChanged(...) override {
    if (user->getAudioStatus().isAudioConnected) {
        // Now safe to mute/unmute
    }
}
```

---

### Build Issues

#### "Cannot instantiate abstract class"

**Cause**: Not all delegate methods implemented

**Fix**: Implement ALL 80+ methods:
```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
    void onSessionJoin() override { }
    void onSessionLeave() override { }
    void onError(ZoomVideoSDKErrors, int) override { }
    // ... all 80+ methods
};
```

See [Delegate Methods](../references/delegate-methods.md).

#### "Unresolved external symbol"

**Cause**: sdk.lib not linked

**Fix**: Add to linker settings:
- Additional Library Directories: `$(SolutionDir)SDK\lib`
- Additional Dependencies: `sdk.lib`

---

### Runtime Issues

#### "DLL not found"

**Cause**: SDK DLLs not in executable directory

**Fix**: Copy all DLLs from `SDK\bin\` to output directory.

Post-Build Event:
```cmd
xcopy /Y /D "$(SolutionDir)SDK\bin\*.*" "$(OutDir)"
```

#### "Application crashes on exit"

**Cause**: Cleanup order incorrect

**Fix**: Proper cleanup sequence:
```cpp
void Cleanup() {
    // 1. Leave session first
    if (sdk->isInSession()) {
        sdk->leaveSession(false);
    }

    // 2. Wait for onSessionLeave callback
    // (process messages while waiting)

    // 3. Cleanup SDK
    sdk->cleanup();

    // 4. Destroy SDK object
    DestroyZoomVideoSDKObj();
}
```

---

## Logging

Enable SDK logging for debugging:

```cpp
ZoomVideoSDKInitParams params;
params.enableLog = true;
params.logFilePrefix = L"zoom_video_sdk";
```

Logs are written to: `%APPDATA%\ZoomVideoSDK\logs\`

---

## Related Documentation

- [Windows Message Loop](windows-message-loop.md) - Callback issues
- [Build Errors](build-errors.md) - Compile/link errors
- [Delegate Methods](../references/delegate-methods.md) - Required callbacks
- [Video Rendering](../examples/video-rendering.md) - Video subscription
- [API Reference](../references/windows-reference.md) - Error codes

---

**Quick fixes:**
1. Callbacks don't fire → Add message loop
2. Error 2 → Subscribe in `onUserVideoStatusChanged`
3. Error 8 → Add `Sleep(200)` between calls
4. Abstract class → Implement all 80+ delegate methods
