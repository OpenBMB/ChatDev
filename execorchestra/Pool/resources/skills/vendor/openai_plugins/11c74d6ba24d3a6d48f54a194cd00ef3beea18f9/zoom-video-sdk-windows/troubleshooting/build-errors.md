# Build Errors Guide

Common build errors when working with the Zoom Video SDK for Windows and how to fix them.

---

## Include Order (CRITICAL)

SDK headers have dependency issues. **Include in this exact order**:

```cpp
#include <windows.h>           // MUST be first
#include <cstdint>             // MUST be second (for uint32_t)

// Standard library
#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <thread>

// SDK headers
#include "zoom_video_sdk_api.h"
#include "zoom_video_sdk_interface.h"
#include "zoom_video_sdk_delegate_interface.h"
#include "zoom_sdk_raw_data_def.h"    // For YUVRawDataI420
```

---

## Error: 'uint32_t' is not a member of 'std'

### Symptom

```
error C2039: 'uint32_t': is not a member of 'std'
```

### Cause

SDK headers use `uint32_t` without including `<cstdint>`.

### Fix

Add `#include <cstdint>` **before** SDK headers:

```cpp
#include <windows.h>
#include <cstdint>      // Add this!
#include "zoom_video_sdk_api.h"
```

---

## Error: 'YUVRawDataI420' undeclared identifier

### Symptom

```
error C2065: 'YUVRawDataI420': undeclared identifier
```

### Cause

The class is only forward-declared in some headers.

### Fix

Include the raw data definition header:

```cpp
#include "zoom_sdk_raw_data_def.h"
```

---

## Error: Cannot open include file 'json/json.h'

### Symptom

```
fatal error C1083: Cannot open include file: 'json/json.h': No such file or directory
```

### Cause

jsoncpp library not installed or not in include path.

### Fix

Install via vcpkg and configure include paths:

```powershell
# Install vcpkg
git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install

# Install jsoncpp
.\vcpkg install jsoncpp:x64-windows
```

Then add to **Additional Include Directories**:
```
C:\vcpkg\packages\jsoncpp_x64-windows\include
```

---

## Error: unresolved external symbol 'CreateZoomVideoSDKObj'

### Symptom

```
error LNK2019: unresolved external symbol "CreateZoomVideoSDKObj"
```

### Cause

SDK library not linked.

### Fix

1. Add to **Additional Library Directories**:
   ```
   $(SolutionDir)SDK\lib
   ```

2. Add to **Additional Dependencies**:
   ```
   sdk.lib
   ```

---

## Error: sdk.dll not found

### Symptom

```
The code execution cannot proceed because sdk.dll was not found.
```

### Cause

SDK DLLs not in output directory.

### Fix

Add Post-Build Event:

```cmd
xcopy /Y /D "$(SolutionDir)SDK\bin\*.*" "$(OutDir)"
```

Or manually copy all DLLs from `SDK\bin\` to your output directory.

---

## Error: Abstract class cannot be instantiated

### Symptom

```
error C2259: 'MyDelegate': cannot instantiate abstract class
```

### Cause

Not all pure virtual methods implemented in your delegate class.

### Fix

Implement ALL 80+ methods in `IZoomVideoSDKDelegate`. Even unused methods need empty implementations:

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
public:
    // Implement all methods, even if empty
    void onSessionJoin() override { /* your code */ }
    void onSessionLeave() override {}
    void onError(ZoomVideoSDKErrors, int) override {}
    void onUserJoin(IZoomVideoSDKUserHelper*, IVideoSDKVector<IZoomVideoSDKUser*>*) override {}
    // ... all 80+ methods
};
```

See [Delegate Methods](../references/delegate-methods.md) for complete list.

---

## Error: 'IZoomVideoSDK' is undefined

### Symptom

```
error C2027: use of undefined type 'ZOOMVIDEOSDK_NAMESPACE::IZoomVideoSDK'
```

### Cause

Missing include or namespace.

### Fix

```cpp
#include "zoom_video_sdk_interface.h"

// Use namespace
using namespace ZOOMVIDEOSDK_NAMESPACE;
// Or
USING_ZOOM_VIDEO_SDK_NAMESPACE
```

---

## Visual Studio Project Configuration

### Include Directories

**C/C++ → General → Additional Include Directories:**

```
$(SolutionDir)SDK\h
$(SolutionDir)SDK\h\helpers
C:\vcpkg\packages\jsoncpp_x64-windows\include
```

### Library Directories

**Linker → General → Additional Library Directories:**

```
$(SolutionDir)SDK\lib
C:\vcpkg\packages\jsoncpp_x64-windows\lib
```

### Additional Dependencies

**Linker → Input → Additional Dependencies:**

```
sdk.lib
jsoncpp.lib
```

### Post-Build Event

**Build Events → Post-Build Event → Command Line:**

```cmd
xcopy /Y /D "$(SolutionDir)SDK\bin\*.*" "$(OutDir)"
xcopy /Y /D "$(ProjectDir)config.json" "$(OutDir)"
```

### Runtime Library

**C/C++ → Code Generation → Runtime Library:**

- Debug: Multi-threaded Debug DLL (/MDd)
- Release: Multi-threaded DLL (/MD)

---

## MSBuild from Git Bash

When building from Git Bash, use this pattern:

```bash
MSYS_NO_PATHCONV=1 "/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe" \
    YourProject.vcxproj \
    /p:Configuration=Release \
    /p:Platform=x64 \
    /t:Build \
    /verbosity:minimal
```

**Key points:**
- `MSYS_NO_PATHCONV=1` prevents path conversion issues
- Use full path to MSBuild.exe in quotes
- Escape or quote paths with spaces

---

## SDK Directory Structure

Expected structure:

```
YourProject/
├── SDK/
│   ├── bin/           # DLLs (copy to output)
│   │   ├── sdk.dll
│   │   ├── *.dll      # Many other DLLs
│   ├── h/             # Headers
│   │   ├── zoom_video_sdk_api.h
│   │   ├── zoom_video_sdk_interface.h
│   │   ├── zoom_video_sdk_delegate_interface.h
│   │   ├── zoom_sdk_raw_data_def.h
│   │   └── helpers/
│   │       └── *.h
│   └── lib/           # Libraries
│       └── sdk.lib
├── YourProject.cpp
├── YourProject.vcxproj
└── config.json
```

---

## Related Documentation

- [Windows Reference](../references/windows-reference.md) - Full project setup
- [Delegate Methods](../references/delegate-methods.md) - All required callbacks
- [Common Issues](common-issues.md) - Runtime troubleshooting

---

**TL;DR**: Include `<windows.h>` first, then `<cstdint>`, then SDK headers. Link `sdk.lib`. Copy DLLs to output. Implement all 80+ delegate methods.
