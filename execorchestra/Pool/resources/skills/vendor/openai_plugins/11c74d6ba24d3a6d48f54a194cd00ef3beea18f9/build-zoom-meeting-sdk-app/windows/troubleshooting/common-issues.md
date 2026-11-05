# Common Issues & Troubleshooting Checklist

## Quick Diagnostic Workflow

### Build Issues vs Runtime Issues

**Build issues** = Problems during compilation (Visual Studio errors)
**Runtime issues** = Problems when running the executable (authentication, joining meetings)

Use this flowchart:

```
Does your code compile?
├─ NO  → See "Build Issues Checklist" below
└─ YES → Does authentication succeed?
          ├─ NO  → See "Authentication Issues" below
          └─ YES → Does meeting join succeed?
                   ├─ NO  → See "Meeting Join Issues" below
                   └─ YES → Does video capture work?
                            ├─ NO  → See "Video Capture Issues" below
                            └─ YES → You're all set!
```

---

## Build Issues Checklist

### ✅ Compiler Errors with `uint32_t`, `AudioType`, or `YUVRawDataI420`

**Symptoms**:
- `Error C2061: syntax error: identifier 'uint32_t'`
- `Error C3646: 'GetAudioJoinType': unknown override specifier`
- `Error: use of undefined type 'YUVRawDataI420'`

**Checklist**:
- [ ] `#include <windows.h>` is the FIRST include in every file
- [ ] `#include <cstdint>` is right after `<windows.h>` in every file
- [ ] `meeting_audio_interface.h` is included BEFORE `meeting_participants_ctrl_interface.h`
- [ ] `zoom_sdk_raw_data_def.h` is included when using raw video data

**Fix**: See [Build Errors Guide](build-errors.md) for detailed solutions.

---

### ✅ "Cannot Instantiate Abstract Class" Error

**Symptoms**:
- `Error C2259: 'AuthServiceEventListener': cannot instantiate abstract class`
- `note: due to following members: 'void IAuthServiceEvent::onNotificationServiceStatus(...)': is abstract`

**Checklist**:
- [ ] Implemented ALL pure virtual methods from `IAuthServiceEvent` (6 methods)
- [ ] Implemented ALL pure virtual methods from `IMeetingServiceEvent` (9 methods)
- [ ] Included WIN32-conditional methods (even though they're in `#if defined(WIN32)`)
- [ ] Used `override` keyword to catch signature mismatches
- [ ] Verified method signatures match SDK headers exactly

**Fix**: See [Interface Methods Guide](../references/interface-methods.md) for complete method lists.

---

### ✅ Linker Errors

**Symptoms**:
- `LNK2019: unresolved external symbol`
- `Error: Cannot open file 'sdk.lib'`

**Checklist**:
- [ ] Added SDK library directory to Project Properties → Linker → General → Additional Library Directories
  - `$(SolutionDir)SDK\x64\lib`
- [ ] Added `sdk.lib` to Project Properties → Linker → Input → Additional Dependencies
- [ ] Verified SDK architecture matches project architecture (both x64)
- [ ] SDK DLL (`sdk.dll`) is in the same directory as the executable or in PATH

**Fix**:
1. Right-click project → Properties
2. Configuration: All Configurations, Platform: x64
3. Linker → General → Additional Library Directories: Add `$(SolutionDir)SDK\x64\lib`
4. Linker → Input → Additional Dependencies: Add `sdk.lib`
5. Copy `SDK\x64\bin\sdk.dll` to your output directory

---

## Runtime Issues

### ✅ Authentication Timeout (CRITICAL!)

**Symptoms**:
- "Still waiting..." messages keep printing
- "ERROR: Authentication timeout after 30 seconds"
- `onAuthenticationReturn()` callback NEVER fires

**Root Cause**: 99% of the time, this is a **missing Windows message loop**, NOT a JWT token issue!

**Checklist**:
- [ ] Added `PeekMessage()` loop during authentication wait
- [ ] Added `PeekMessage()` loop in main event loop
- [ ] Using `PM_REMOVE` flag with `PeekMessage()`
- [ ] Calling `TranslateMessage()` and `DispatchMessage()` for each message

**Fix**: See [Windows Message Loop Guide](windows-message-loop.md) for complete solution.

**Quick test**: Add this minimal message loop:
```cpp
while (!g_authenticated) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}
```

If `onAuthenticationReturn()` suddenly fires, you confirmed the issue was the message loop.

---

### ✅ Authentication Fails with Error Code

**Symptoms**:
- `onAuthenticationReturn()` fires but with non-success code
- "Authentication failed: [error code]"

**Authentication Error Codes**:

| Code | Enum Value | Meaning | Solution |
|------|------------|---------|----------|
| 0 | `AUTHRET_SUCCESS` | ✅ Success | N/A |
| 1 | `AUTHRET_KEYORSECRETEMPTY` | JWT token or app secret is empty | Verify JWT token string is not empty |
| 2 | `AUTHRET_JWTTOKENWRONG` | Invalid JWT token format or signature | Regenerate JWT token, verify app credentials |
| 3 | `AUTHRET_OVERTIME` | JWT token expired | Regenerate JWT with fresh timestamp |
| 4 | `AUTHRET_NETWORKISSUE` | Network connection problem | Check firewall, proxy settings, internet connection |
| 16 | `AUTHRET_CLIENT_INCOMPATIBLE` | SDK version incompatible with Zoom service | Update SDK to latest version |

**Checklist**:
- [ ] JWT token is correctly formatted (3 parts separated by dots)
- [ ] JWT token was generated within the last hour
- [ ] App credentials (SDK Key/Secret) match JWT token generation
- [ ] System clock is accurate (JWT validation is time-sensitive)
- [ ] Not behind a firewall blocking Zoom domains (*.zoom.us, *.zoomgov.com)

**How to regenerate JWT token**:
```javascript
// Node.js example
const jwt = require('jsonwebtoken');
const token = jwt.sign(
  {
    appKey: 'YOUR_SDK_KEY',
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 7200,  // 2 hours
    tokenExp: Math.floor(Date.now() / 1000) + 7200
  },
  'YOUR_SDK_SECRET'
);
```

---

### ✅ Meeting Join Fails

**Symptoms**:
- `onMeetingStatusChanged()` fires with `MEETING_STATUS_FAILED`
- "Join meeting failed: [error code]"

**Meeting Error Codes**:

| Code | Enum Value | Meaning | Solution |
|------|------------|---------|----------|
| 0 | `MEETING_SUCCESS` | ✅ Success | N/A |
| 1 | `MEETING_FAIL_NETWORK_ERR` | Network error | Check internet connection |
| 2 | `MEETING_FAIL_RECONNECT_ERR` | Reconnection failed | Retry joining |
| 3 | `MEETING_FAIL_MMR_ERR` | Multi-media router error | Contact Zoom support |
| 4 | `MEETING_FAIL_PASSWORD_ERR` | Wrong meeting password | Verify password |
| 5 | `MEETING_FAIL_SESSION_ERR` | Invalid meeting session | Verify meeting number |
| 6 | `MEETING_FAIL_MEETING_OVER` | Meeting has ended | Join a different meeting |
| 7 | `MEETING_FAIL_MEETING_NOT_START` | Meeting hasn't started | Wait for host to start |
| 8 | `MEETING_FAIL_MEETING_NOT_EXIST` | Invalid meeting number | Verify meeting number |
| 9 | `MEETING_FAIL_MEETING_USER_FULL` | Meeting at capacity | Wait for slot or use livestream |
| 10 | `MEETING_FAIL_CLIENT_INCOMPATIBLE` | SDK version incompatible | Update SDK |

**Checklist**:
- [ ] Meeting number is correct (10-11 digits)
- [ ] Meeting password is correct (if required)
- [ ] Authenticated successfully before joining
- [ ] Meeting is currently active (host has started it)
- [ ] Meeting hasn't reached capacity
- [ ] Using `SDK_UT_WITHOUT_LOGIN` user type for JWT auth

**Fix for common issues**:
```cpp
// Correct join pattern
JoinParam joinParam;
joinParam.userType = SDK_UT_WITHOUT_LOGIN;  // REQUIRED for JWT auth

JoinParam4WithoutLogin withoutLoginParam;
withoutLoginParam.meetingNumber = 1234567890;  // Your meeting number
withoutLoginParam.userName = L"Bot User";
withoutLoginParam.psw = L"meeting_password";  // Empty if no password
withoutLoginParam.vanityID = nullptr;
withoutLoginParam.customer_key = nullptr;
withoutLoginParam.webinarToken = nullptr;
withoutLoginParam.isVideoOff = false;
withoutLoginParam.isAudioOff = false;

joinParam.param.withoutloginuserJoin = withoutLoginParam;
meetingService->Join(joinParam);
```

---

### ✅ Callbacks Not Firing

**Symptoms**:
- `SetEvent()` called but callbacks never execute
- Authentication/meeting status changes but no output

**Checklist**:
- [ ] Windows message loop is running (see Authentication Timeout above)
- [ ] Event listener pointer is valid (not deleted prematurely)
- [ ] Event listener is set BEFORE calling SDK methods
- [ ] Using `new` to allocate listener (SDK manages lifecycle)

**Fix**:
```cpp
// CORRECT: Set listener before SDK actions
AuthServiceEventListener* authListener = new AuthServiceEventListener(&OnAuthComplete);
authService->SetEvent(authListener);
authService->SDKAuth(authContext);  // Now callbacks will work

// WRONG: Set listener after
authService->SDKAuth(authContext);
authService->SetEvent(authListener);  // Too late!
```

---

## Video Capture Issues

### ✅ Raw Video Data Not Received

**Symptoms**:
- `onRawDataFrameReceived()` never fires
- `onRawDataStatusChanged()` fires but no frames

**Checklist**:
- [ ] Called `StartRawRecording()` after joining meeting
- [ ] Subscribed to video streams using `Subscribe(userId, Raw_Video_On)`
- [ ] Implemented `IZoomSDKRendererDelegate` interface correctly
- [ ] Created raw data helper: `CreateRawdataRenderer()`
- [ ] Set renderer delegate: `setRawDataResolution(...)` and `subscribe(...)`

**Fix**: See [Raw Video Capture Guide](../examples/raw-video-capture.md) for complete workflow.

**Quick test**:
```cpp
// After successfully joining meeting
IMeetingRecordingController* recordingCtrl = meetingService->GetMeetingRecordingController();
recordingCtrl->StartRawRecording();

IZoomSDKVideoSource* videoSource = rawDataHelper->GetRawdataVideoSourceHelper();
videoSource->subscribe(userId, Raw_Video_On);
```

---

### ✅ Video Data Format Issues

**Symptoms**:
- Receiving frames but video looks corrupted
- Wrong frame size or color

**Checklist**:
- [ ] Using YUV420 (I420) format, not RGB
- [ ] Buffer size is `width * height * 1.5` bytes (not `width * height * 3`)
- [ ] Y plane: `width * height` bytes
- [ ] U plane: `(width/2) * (height/2)` bytes
- [ ] V plane: `(width/2) * (height/2)` bytes
- [ ] Rotation is handled correctly (0°, 90°, 180°, 270°)

**YUV420 Layout**:
```
Width: 1920, Height: 1080
Total bytes: 1920 * 1080 * 1.5 = 3,110,400 bytes

Y plane: [0 to 2,073,599]       (1920 * 1080 bytes)
U plane: [2,073,600 to 2,592,639]  (960 * 540 bytes)
V plane: [2,592,640 to 3,110,399]  (960 * 540 bytes)
```

---

## Network & Firewall Issues

### ✅ SDK Network Requirements

**Symptoms**:
- `AUTHRET_NETWORKISSUE` error code
- `MEETING_FAIL_NETWORK_ERR` error code
- Timeouts during initialization

**Required Firewall Rules**:
- [ ] Allow outbound HTTPS (port 443) to `*.zoom.us`
- [ ] Allow outbound HTTPS (port 443) to `*.zoomgov.com` (for government)
- [ ] Allow UDP ports 8801-8810 for media
- [ ] Not behind a proxy requiring authentication (or proxy configured)

**How to test connectivity**:
```bash
# Test DNS resolution
ping zoom.us
ping us01web.zoom.us

# Test HTTPS connectivity
curl https://zoom.us
curl https://us01web.zoom.us
```

**Proxy configuration** (if required):
```cpp
InitParam initParam;
initParam.strWebDomain = L"https://zoom.us";
// Add proxy settings if needed
// initParam.proxy = ...;
```

---

## General Debugging Tips

### Enable SDK Logging

```cpp
InitParam initParam;
initParam.enableLogByDefault = true;  // Enable logs
initParam.enableGenerateDump = true;   // Enable crash dumps
```

Logs location: `%APPDATA%\Zoom\logs\` or `C:\Users\[username]\AppData\Roaming\Zoom\logs\`

### Add Debug Output to Callbacks

```cpp
void AuthServiceEventListener::onAuthenticationReturn(AuthResult ret) {
    std::cout << "[DEBUG] onAuthenticationReturn called! Code: " << ret << std::endl;
    // Your logic here
}
```

### Use Windows Debugger

Set breakpoints in callback methods to verify they're being called:
- `onAuthenticationReturn()`
- `onMeetingStatusChanged()`

If breakpoints never hit → Message loop issue
If breakpoints hit but code is wrong → Logic issue

### Verify SDK Version

Check `SDK/x64/version.txt` or `sdk.dll` properties → Details tab

Different versions have different:
- Required callback methods
- Error codes
- API behavior

This guide is for **SDK v6.7.2.26830**.

---

## "If You See X, Do Y" Quick Reference

| You See | Do This |
|---------|---------|
| `uint32_t` error | Add `#include <cstdint>` after `<windows.h>` |
| `AudioType` error | Include `meeting_audio_interface.h` before `meeting_participants_ctrl_interface.h` |
| `YUVRawDataI420` error | Include `zoom_sdk_raw_data_def.h` |
| Abstract class error | Implement ALL virtual methods (see [Interface Methods Guide](../references/interface-methods.md)) |
| Authentication timeout | Add Windows message loop (see [Message Loop Guide](windows-message-loop.md)) |
| `AUTHRET_JWTTOKENWRONG` | Regenerate JWT token with correct app credentials |
| `AUTHRET_OVERTIME` | JWT token expired, generate a fresh one |
| `MEETING_FAIL_PASSWORD_ERR` | Wrong meeting password or no password provided |
| `MEETING_FAIL_MEETING_NOT_EXIST` | Invalid meeting number, verify 10-11 digits |
| Callbacks not firing | Add Windows message loop, verify `SetEvent()` called first |
| No video frames | Call `StartRawRecording()` and `Subscribe()` after joining |

---

## Complete SDK Error Code Reference

This section provides comprehensive error code tables from official Zoom documentation.

### Global SDK Error Codes (SDKERR_*)

| Code | Name | Description |
|------|------|-------------|
| 0 | `SDKERR_SUCCESS` | Success |
| 1 | `SDKERR_NO_IMPL` | This feature is currently not available |
| 2 | `SDKERR_WRONG_USEAGE` | Incorrect usage of the feature |
| 3 | `SDKERR_INVALID_PARAMETER` | Wrong parameter |
| 4 | `SDKERR_MODULE_LOAD_FAILED` | Loading module failed |
| 5 | `SDKERR_MEMORY_FAILED` | No memory allocated |
| 6 | `SDKERR_SERVICE_FAILED` | Internal service error |
| 7 | `SDKERR_UNINITIALIZE` | SDK is not initialized before use |
| 8 | `SDKERR_UNAUTHENTICATION` | SDK is not authorized before use |
| 9 | `SDKERR_NORECORDINGINPROCESS` | No recording is in progress |
| 10 | `SDKERR_TRANSCODER_NOFOUND` | Transcoder module is not found |
| 11 | `SDKERR_VIDEO_NOTREADY` | The video service is not ready |
| 12 | `SDKERR_NO_PERMISSION` | No permission |
| 13 | `SDKERR_UNKNOWN` | Unknown error |
| 14 | `SDKERR_OTHER_SDK_INSTANCE_RUNNING` | Another SDK instance is in progress |
| 15 | `SDKERR_INTERNAL_ERROR` | SDK internal error |
| 16 | `SDKERR_NO_AUDIODEVICE_ISFOUND` | No audio device is found |
| 17 | `SDKERR_NO_VIDEODEVICE_ISFOUND` | No video device is found |
| 18 | `SDKERR_TOO_FREQUENT_CALL` | API calls too frequent |
| 19 | `SDKERR_FAIL_ASSIGN_USER_PRIVILEGE` | User cannot be assigned with the new privilege |
| 20 | `SDKERR_MEETING_DONT_SUPPORT_FEATURE` | The current meeting does not support the request feature |
| 21 | `SDKERR_MEETING_NOT_SHARE_SENDER` | The current user is not the presenter |
| 22 | `SDKERR_MEETING_YOU_HAVE_NO_SHARE` | There is no sharing |
| 23 | `SDKERR_MEETING_VIEWTYPE_PARAMETER_IS_WRONG` | Incorrect `ViewType` parameters |
| 24 | `SDKERR_MEETING_ANNOTATION_IS_OFF` | Annotation is disabled |
| 25 | `SDKERR_SETTING_OS_DONT_SUPPORT` | Current OS doesn't support the setting |
| 26 | `SDKERR_EMAIL_LOGIN_IS_DISABLED` | Email login is disabled |
| 27 | `SDKERR_HARDWARE_NOT_MEET_FOR_VB` | Computer doesn't meet minimum requirements for virtual background |
| 28 | `SDKERR_NEED_USER_CONFIRM_RECORD_DISCLAIMER` | Need to process recording disclaimer |
| 29 | `SDKERR_NO_SHARE_DATA` | There is no raw data from sharing |
| 30 | `SDKERR_SHARE_CANNOT_SUBSCRIBE_MYSELF` | Cannot subscribe to my own stream |
| 31 | `SDKERR_NOT_IN_MEETING` | Not in the meeting |

### Authentication Error Codes (AUTHRET_*)

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| 0 | `AUTHRET_SUCCESS` | Authentication success | N/A |
| 1 | `AUTHRET_KEYORSECRETEMPTY` | SDK key or secret is empty | Verify JWT token string is not empty |
| 2 | `AUTHRET_KEYORSECRETWRONG` | SDK key or secret is incorrect | Check app credentials match |
| 3 | `AUTHRET_ACCOUNTNOTSUPPORT` | Account does not support SDK | Verify account has SDK access |
| 4 | `AUTHRET_ACCOUNTNOTENABLESDK` | Account does not have SDK enabled | Enable SDK for account |
| 5 | `AUTHRET_UNKNOWN` | Unknown error | Check logs |
| 6 | `AUTHRET_SERVICE_BUSY` | Service is busy | Retry later |
| 7 | `AUTHRET_NONE` | Initial status | N/A |
| 8 | `AUTHRET_OVERTIME` | Timeout | Check network, retry |
| 9 | `AUTHRET_NETWORKISSUE` | Network issues | Check firewall/proxy |
| 10 | `AUTHRET_CLIENT_INCOMPATIBLE` | Account does not support this SDK version | Update SDK |
| 11 | `AUTHRET_JWTTOKENWRONG` | JWT token is wrong | Regenerate JWT with correct credentials |

### Login Error Codes (LoginFail_*)

| Code | Name | Description |
|------|------|-------------|
| 0 | `LoginFail_None` | Initial status |
| 1 | `LoginFail_EmailLoginDisable` | Email login is disabled |
| 2 | `LoginFail_UserNotExist` | User does not exist |
| 3 | `LoginFail_WrongPassword` | Incorrect password |
| 4 | `LoginFail_AccountLocked` | Account is locked |
| 5 | `LoginFail_SDKNeedUpdate` | SDK version is unsupported |
| 6 | `LoginFail_TooManyFailedAttempts` | Too many failed attempts |
| 7 | `LoginFail_SMSCodeError` | SMS verification code error |
| 8 | `LoginFail_SMSCodeExpired` | SMS verification code expired |
| 9 | `LoginFail_PhoneNumberFormatInValid` | Phone number format invalid |
| 10 | `LoginFail_LoginTokenInvalid` | Login token is invalid |
| 11 | `LoginFail_UserDisagreeLoginDisclaimer` | User disagreed login disclaimer |
| 12 | `LoginFail_Mfa_Required` | MFA is required |
| 13 | `LoginFail_Need_Bitrthday_ask` | Need to provide DOB information |
| 100 | `LoginFail_OtherIssue` | Other issue |

### Breakout Room Error Codes (BOControllerError_*)

| Code | Name | Description |
|------|------|-------------|
| 0 | `BOControllerError_NULL_POINTER` | BO controller is null, SDK not initialized |
| 1 | `BOControllerError_WRONG_CURRENT_STATUS` | Incorrect current status |
| 2 | `BOControllerError_TOKEN_NOT_READY` | Token is not ready |
| 3 | `BOControllerError_NO_PRIVILEGE` | No privilege |
| 4 | `BOControllerError_BO_LIST_IS_UPLOADING` | BO list is uploading |
| 5 | `BOControllerError_UPLOAD_FAIL` | BO list upload failed |
| 6 | `BOControllerError_NO_ONE_HAS_BEEN_ASSIGNED` | No user assigned to BO |
| 100 | `BOControllerError_UNKNOWN` | Unknown error |

### Phone Error Codes (PhoneFailedReason_*)

| Code | Name | Description |
|------|------|-------------|
| 0 | `PhoneFailedReason_None` | Initial status |
| 1 | `PhoneFailedReason_Busy` | Telephone service is busy |
| 2 | `PhoneFailedReason_Not_Available` | Service not available |
| 3 | `PhoneFailedReason_User_Hangup` | User hung up |
| 4 | `PhoneFailedReason_Other_Fail` | Other failure |
| 5 | `PhoneFailedReason_No_Answer` | No answer |
| 6 | `PhoneFailedReason_Block_No_Host` | Call-out blocked before host joins |
| 7 | `PhoneFailedReason_Block_High_Rate` | Blocked due to high cost |
| 8 | `PhoneFailedReason_Block_Too_Frequent` | Blocked due to high frequency |

### OBF/Anonymous Join Error Codes (2026 Enforcement)

**Important Dates**:
- **February 7, 2026**: OBF tokens must be valid (well-formed, not expired)
- **March 2, 2026**: Anonymous joins no longer allowed - must provide valid OBF/ZAK token

| Code | Name | Description |
|------|------|-------------|
| 503 | `MEETING_FAIL_USER_LEVEL_TOKEN_NOT_HAVE_HOST_ZAK_OBF` | To access raw data with privilege token, must also provide OBF token authorized by host |
| 504 | `MEETING_FAIL_APP_CAN_NOT_ANONYMOUS_JOIN_MEETING` | Anonymous joins not allowed. Provide ZAK or OBF token |
| 6603 | `RESULT_UNKNOWN_ERROR` | Account is blocking your Meeting SDK application |

### General Network/Server Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| 5 | Failed to create data connection | Check network connection |
| 15 | Failed to send create meeting command | Check HTTP request configuration |
| 1002 | Wrong user password | Check password |
| 1019 | Web login locked after 6 failed attempts | Contact support to reactivate |
| 3023 | SDK authentication failure: invalid SDK key/secret | Check credentials |
| 3024 | Account does not support using SDK | Verify license type |
| 5003 | No response from server in 30 seconds | Retry later |
| 4502 | Invalid recurring meeting - no meeting occurrence | Verify meeting recurrence |
| 5004 | DNS resolve failure | Check network adaptor |
| 102006 | Conference does not exist | Verify meeting number |
| 102011 | Client version lower than minimum required | Download latest SDK |
| 102012 | Client version higher than maximum allowed | Download latest SDK |
| 102014 | Conference token expired | Get new token |
| 103008 | Server is too busy | Retry later |
| 103024 | Account does not support requested feature | Verify account features |
| 103025 | Account does not support call out | Verify call out feature |
| 103037 | Too many pending requests | Reduce request frequency |
| 103039 | Account is in blacklist | Contact support |
| 102004/103001 | Conference already exists | Use different meeting number |
| 102010/103006 | Attendee limit reached | Contact sales for more attendees |
| 102015/103011 | Conference is locked | Contact host to unlock |
| 102016/103014 | Account restricted | Contact support |

---

## File Signing Error (105035)

**Symptom**: Error Code `105035` when running the SDK

**Root Cause**: Re-signing or adding new signatures to protected SDK files

**Protected Files (DO NOT re-sign)**:
- `CptControl.exe`
- `CptHost.exe`
- `CptInstall.exe`
- `CptService.exe`
- `CptShare.dll`
- `zzhost.dll`
- `zzplugin.dll`
- `aomhost64.exe`

**Solution**: Skip signing these files during your build/deployment process. If error persists without re-signing, visit the [Zoom Developer Forum](https://devforum.zoom.us/).

---

## Still Having Issues?

1. **Check SDK logs**: `%APPDATA%\Zoom\logs\`
2. **Enable debug output**: Add `std::cout` to all callbacks
3. **Verify SDK version**: Different versions have different requirements
4. **Review working example**: See complete working code in [Authentication Pattern](../examples/authentication-pattern.md)
5. **Check Zoom Developer Forums**: https://devforum.zoom.us/

---

## Related Documentation

- [Windows Message Loop](windows-message-loop.md) - Why callbacks don't fire
- [Build Errors Guide](build-errors.md) - Header dependency issues
- [Interface Methods Guide](../references/interface-methods.md) - Required virtual methods
- [Authentication Pattern](../examples/authentication-pattern.md) - Complete working auth code

---

**Last Updated**: Based on Zoom Windows Meeting SDK v6.7.2.26830
