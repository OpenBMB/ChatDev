# Common Build Errors and Solutions

## SDK Header Dependency Issues

The Zoom Windows SDK has several header dependency bugs that cause compilation errors. This guide covers the most common issues and their solutions.

---

## Error 1: `uint32_t` Undefined

### Symptoms

```
Error C2061: syntax error: identifier 'uint32_t'
Error C3646: 'GetAudioJoinType': unknown override specifier
Error C2059: syntax error: ')'
Error C2238: unexpected token(s) preceding ';'
```

Errors occur in SDK headers:
- `rawdata/rawdata_renderer_interface.h` (lines 57, 65)
- `meeting_service_components/meeting_participants_ctrl_interface.h` (line 139)

### Root Cause

The SDK headers use `uint32_t` but don't include `<cstdint>` where it's defined.

### Solution

**Add `#include <cstdint>` to ALL your header files**, right after `<windows.h>`:

```cpp
// YourListener.h
#pragma once
#include <windows.h>
#include <cstdint>  // CRITICAL: Must come before SDK headers!
#include <auth_service_interface.h>
```

**Required in**:
- All `.h` files that include SDK headers
- `main.cpp` or any `.cpp` that includes SDK headers directly

### Critical Include Order

```cpp
// 1. Windows header FIRST
#include <windows.h>

// 2. Standard int types SECOND (for uint32_t)
#include <cstdint>

// 3. Other standard headers
#include <iostream>
#include <vector>

// 4. Zoom SDK headers LAST
#include <zoom_sdk.h>
#include <meeting_service_interface.h>
```

**This order is MANDATORY and must be followed in every file!**

---

## Error 2: `AudioType` Undefined

### Symptoms

```
Error C3646: 'GetAudioJoinType': unknown override specifier
Error C2059: syntax error: ')'
```

Error occurs when including:
```cpp
#include <meeting_service_components/meeting_participants_ctrl_interface.h>
```

### Root Cause

`meeting_participants_ctrl_interface.h` uses `AudioType` enum (line 139) but doesn't include `meeting_audio_interface.h` where `AudioType` is defined.

### Solution

**Include `meeting_audio_interface.h` BEFORE `meeting_participants_ctrl_interface.h`**:

```cpp
// Correct order
#include <meeting_service_components/meeting_audio_interface.h>      // FIRST
#include <meeting_service_components/meeting_participants_ctrl_interface.h>  // SECOND
```

**Wrong order will fail**:
```cpp
// ❌ This will cause errors!
#include <meeting_service_components/meeting_participants_ctrl_interface.h>
#include <meeting_service_components/meeting_audio_interface.h>
```

---

## Error 3: `YUVRawDataI420` Incomplete Type

### Symptoms

```
Error: use of undefined type 'YUVRawDataI420'
Error: incomplete type is not allowed
```

### Root Cause

`rawdata/rawdata_renderer_interface.h` only forward-declares `YUVRawDataI420`:
```cpp
class YUVRawDataI420;  // Forward declaration only!
```

The full class definition is in `zoom_sdk_raw_data_def.h`.

### Solution

**Include `zoom_sdk_raw_data_def.h` in your renderer delegate header**:

```cpp
// YourRendererDelegate.h
#pragma once
#include <windows.h>
#include <cstdint>
#include <rawdata/rawdata_renderer_interface.h>
#include <zoom_sdk_raw_data_def.h>  // Full YUVRawDataI420 definition
```

---

## Error 4: Abstract Class Cannot Be Instantiated

### Symptoms

```
Error C2259: 'MeetingServiceEventListener': cannot instantiate abstract class
Error: pure virtual function "IMeetingServiceEvent::onUserNetworkStatusChanged" has no overrider
Error: pure virtual function "IMeetingServiceEvent::onAppSignalPanelUpdated" has no overrider
```

### Root Cause

Missing implementation of pure virtual methods (methods marked with `= 0`) required by SDK interfaces.

### Solution

**Implement ALL pure virtual methods** from the SDK interface.

For `IMeetingServiceEvent` (SDK v6.7.2.26830):
```cpp
class MyMeetingListener : public IMeetingServiceEvent {
public:
    // Required by ALL versions
    void onMeetingStatusChanged(MeetingStatus status, int iResult) override;
    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override;
    void onMeetingParameterNotification(const MeetingParameter* param) override;
    void onSuspendParticipantsActivities() override;
    void onAICompanionActiveChangeNotice(bool isActive) override;
    void onMeetingTopicChanged(const zchar_t* sTopic) override;
    void onMeetingFullToWatchLiveStream(const zchar_t* sLiveStreamUrl) override;
    void onUserNetworkStatusChanged(MeetingComponentType type, ConnectionQuality level,
                                   unsigned int userId, bool uplink) override;

    // Required when WIN32 is defined
    #if defined(WIN32)
    void onAppSignalPanelUpdated(IMeetingAppSignalHandler* pHandler) override;
    #endif
};
```

### How to Find All Required Methods

1. Open the SDK header file (e.g., `meeting_service_interface.h`)
2. Search for the interface class (e.g., `class IMeetingServiceEvent`)
3. Look for all methods marked with `= 0` (pure virtual)
4. Implement every single one

**Example from SDK header**:
```cpp
class IMeetingServiceEvent {
public:
    virtual void onMeetingStatusChanged(...) = 0;  // Must implement!
    virtual void onMeetingStatisticsWarningNotification(...) = 0;  // Must implement!
    // ... etc
};
```

---

## Error 5: Override Specifier Did Not Override

### Symptoms

```
Error C3668: method with override specifier 'override' did not override any base class methods
```

### Root Cause

Method signature doesn't exactly match the base class, or the method doesn't exist in the SDK interface (usually due to conditional compilation).

### Solution

**Check for conditional compilation**:

```cpp
// ❌ Wrong: Will fail if WIN32 is not defined
void onNotificationServiceStatus(...) override;

// ✅ Correct: Match SDK's conditional compilation
#if defined(WIN32)
void onNotificationServiceStatus(...) override;
#endif
```

**Verify method signature matches exactly**:
- Parameter types must match exactly
- `const` qualifiers must match
- Parameter names don't matter, but types do

---

## Complete Include Template

### For Main Application File

```cpp
// main.cpp
#include <windows.h>
#include <cstdint>
#include <iostream>
#include <fstream>
#include <string>
#include <thread>
#include <chrono>

// Zoom SDK headers - ORDER MATTERS!
#include <zoom_sdk.h>
#include <auth_service_interface.h>
#include <meeting_service_interface.h>
#include <meeting_service_components/meeting_recording_interface.h>
#include <meeting_service_components/meeting_audio_interface.h>  // BEFORE participants!
#include <meeting_service_components/meeting_participants_ctrl_interface.h>
#include <rawdata/zoom_rawdata_api.h>
#include <rawdata/rawdata_renderer_interface.h>

// Third-party libraries
#include <json/json.h>

// Your headers
#include "AuthServiceEventListener.h"
#include "MeetingServiceEventListener.h"
#include "ZoomSDKRendererDelegate.h"
```

### For Event Listener Headers

```cpp
// AuthServiceEventListener.h
#pragma once
#include <windows.h>
#include <cstdint>
#include <auth_service_interface.h>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class AuthServiceEventListener : public IAuthServiceEvent {
public:
    // ... methods ...
};
```

### For Renderer Delegate Headers

```cpp
// ZoomSDKRendererDelegate.h
#pragma once
#include <windows.h>
#include <cstdint>
#include <rawdata/rawdata_renderer_interface.h>
#include <zoom_sdk_raw_data_def.h>
#include <fstream>
#include <iostream>

using namespace ZOOM_SDK_NAMESPACE;

class ZoomSDKRendererDelegate : public IZoomSDKRendererDelegate {
public:
    // ... methods ...
};
```

---

## Preprocessor Definitions

### Required Definition: WIN32

For correct SDK interface behavior, define `WIN32` in project settings:

**Visual Studio `.vcxproj`**:
```xml
<PreprocessorDefinitions>WIN32;_DEBUG;_CONSOLE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
```

**CMake**:
```cmake
target_compile_definitions(YourTarget PRIVATE WIN32)
```

**Why**: SDK uses `#if defined(WIN32)` to conditionally include platform-specific methods. Without it, you'll miss required methods or have methods that don't exist in the interface.

---

## Quick Troubleshooting Checklist

When you get build errors:

- [ ] Is `<windows.h>` the FIRST include?
- [ ] Is `<cstdint>` included after `<windows.h>` in ALL headers?
- [ ] Is `<cstdint>` included BEFORE any SDK headers?
- [ ] Is `meeting_audio_interface.h` included before `meeting_participants_ctrl_interface.h`?
- [ ] Is `zoom_sdk_raw_data_def.h` included for raw data delegates?
- [ ] Are ALL pure virtual methods implemented?
- [ ] Is `WIN32` defined in preprocessor definitions?
- [ ] Do method signatures exactly match the SDK interface (including `const`)?
- [ ] Are conditional methods (`#if defined(WIN32)`) handled correctly?

---

## Common Patterns for Each Error

### Pattern: "identifier 'X' is undefined"
→ Missing include for header that defines `X`
→ Wrong include order (SDK header before `<cstdint>`)

### Pattern: "unknown override specifier"
→ Type used in method signature is undefined
→ Usually means missing include or wrong include order

### Pattern: "cannot instantiate abstract class"
→ Missing pure virtual method implementation
→ Check SDK header for ALL methods with `= 0`

### Pattern: "incomplete type"
→ Only forward declaration available
→ Need to include header with full definition

### Pattern: "did not override any base class methods"
→ Method doesn't exist in interface (check conditional compilation)
→ Method signature doesn't match exactly

---

## SDK Version Differences

SDK versions may have different required methods. Always check your specific SDK version's headers.

**To check required methods**:
```bash
# Search for pure virtual methods in interface
grep "= 0" SDK/x64/h/meeting_service_interface.h
```

**SDK v6.7.2.26830 requirements**:
- `IMeetingServiceEvent`: 9 methods (8 + 1 WIN32-specific)
- `IAuthServiceEvent`: 6 methods (5 + 1 WIN32-specific)
- `IZoomSDKRendererDelegate`: 3 methods

---

---

## MSBuild Command Pattern

When building from git bash on Windows, use this invocation pattern:

```bash
# Git bash requires unix-style path for the exe and //p: (double slash) for switches
"/c/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/MSBuild/Current/Bin/MSBuild.exe" \
  "C:\tempsdk\zoom-windows-sdk-sample\ZoomSDKSample.vcxproj" \
  //p:Configuration=Release //p:Platform=x64
```

**Key gotchas:**
- Use forward slashes for the MSBuild exe path (`/c/Program Files/...`)
- Use `//p:` not `/p:` — git bash interprets single `/p` as a path
- Use `//t:Rebuild` for clean rebuilds
- The `.vcxproj` path can use either forward or backslashes

**From cmd.exe / PowerShell** (normal Windows paths):
```cmd
"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe" ^
  ZoomSDKSample.vcxproj /p:Configuration=Release /p:Platform=x64
```

---

## See Also

- [Windows Message Loop](windows-message-loop.md) - Runtime callback issues
- [Virtual Method Implementation](../references/interface-methods.md) - Complete method listings
- [Authentication Pattern](../examples/authentication-pattern.md) - Getting started
