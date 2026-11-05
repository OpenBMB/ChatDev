# Meeting SDK - Windows Reference

Complete reference for Zoom Meeting SDK on Windows including dependencies, Visual Studio setup, and troubleshooting.

## System Requirements

- **OS**: Windows 10 or later, Windows Server 2016+
- **Architecture**: x86 (32-bit) and x64 (64-bit)
- **IDE**: Visual Studio 2019, 2022, or later
- **C++ Standard**: C++11 or later

## Dependencies

### Required Tools

```powershell
# Install vcpkg (package manager for C++)
git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install
```

### Required Libraries

```powershell
# For x64
.\vcpkg install jsoncpp:x64-windows
.\vcpkg install curl:x64-windows

# For x86
.\vcpkg install jsoncpp:x86-windows
.\vcpkg install curl:x86-windows

# Set default triplet (optional)
$env:VCPKG_DEFAULT_TRIPLET = "x64-windows"
```

### Visual Studio Workloads

Required workloads in Visual Studio Installer:
- Desktop development with C++
- Windows 10/11 SDK
- C++ CMake tools (optional, for CMake projects)

## Visual Studio Project Configuration

### Project Properties Template

Create a new C++ Console Application, then configure:

#### C/C++ Settings

**General → Additional Include Directories:**
```
$(SolutionDir)SDK\$(PlatformTarget)\h
$(SolutionDir)SDK\$(PlatformTarget)\h\meeting_service_components
$(SolutionDir)SDK\$(PlatformTarget)\h\rawdata
C:\vcpkg\packages\jsoncpp_$(PlatformTarget)-windows\include
C:\vcpkg\packages\curl_$(PlatformTarget)-windows\include
```

**Preprocessor → Preprocessor Definitions:**
```
WIN32
_DEBUG (for Debug config)
_CONSOLE
_UNICODE
UNICODE
%(PreprocessorDefinitions)
```

**Code Generation → Runtime Library:**
- Debug: Multi-threaded Debug DLL (/MDd)
- Release: Multi-threaded DLL (/MD)

#### Linker Settings

**General → Additional Library Directories:**
```
$(SolutionDir)SDK\$(PlatformTarget)\lib
C:\vcpkg\packages\jsoncpp_$(PlatformTarget)-windows\lib
C:\vcpkg\packages\curl_$(PlatformTarget)-windows\lib
```

**Input → Additional Dependencies:**
```
sdk.lib
ws2_32.lib
%(AdditionalDependencies)
```

#### Build Events

**Post-Build Event → Command Line:**
```cmd
xcopy /Y /D "$(SolutionDir)SDK\$(PlatformTarget)\bin\*.*" "$(OutDir)"
xcopy /Y /D "$(ProjectDir)config.json" "$(OutDir)"
```

This copies all SDK DLLs and config.json to your output directory.

### CMakeLists.txt Template (Alternative)

```cmake
cmake_minimum_required(VERSION 3.16)

project(ZoomMeetingSDK CXX)
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set output directories
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/lib)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin)

# Find vcpkg packages
find_package(jsoncpp CONFIG REQUIRED)
find_package(CURL REQUIRED)

# Include directories
include_directories(
    ${CMAKE_SOURCE_DIR}/SDK/x64/h
    ${CMAKE_SOURCE_DIR}/SDK/x64/h/meeting_service_components
    ${CMAKE_SOURCE_DIR}/SDK/x64/h/rawdata
)

# Link directories
link_directories(
    ${CMAKE_SOURCE_DIR}/SDK/x64/lib
    ${CMAKE_SOURCE_DIR}/SDK/x64/bin
)

# Source files
add_executable(YourApp
    YourApp.cpp
    AuthServiceEventListener.cpp
    MeetingServiceEventListener.cpp
    NetworkConnectionHandler.cpp
    WebService.cpp
    # Add more source files as needed
)

# Link libraries
target_link_libraries(YourApp
    sdk.lib
    JsonCpp::JsonCpp
    CURL::libcurl
)

# Copy DLLs to output directory
add_custom_command(TARGET YourApp POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
    "${CMAKE_SOURCE_DIR}/SDK/x64/bin"
    $<TARGET_FILE_DIR:YourApp>
)

# Copy config.json
configure_file(
    ${CMAKE_SOURCE_DIR}/config.json
    ${CMAKE_SOURCE_DIR}/bin/config.json
    COPYONLY
)
```

## Configuration File

### config.json Format

```json
{
  "sdk_jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "meeting_number": "1234567890",
  "passcode": "abc123",
  "video_source": "Big_Buck_Bunny_720_10s_1MB.mp4",
  "zak": ""
}
```

### Reading Config in Code

```cpp
#include <fstream>
#include <json/json.h>

void LoadConfig() {
    std::ifstream f("config.json");
    Json::Value config;

    if (f.is_open()) {
        try {
            f >> config;

            // Extract values
            std::string jwt = config["sdk_jwt"].asString();
            std::string meetingNum = config["meeting_number"].asString();
            std::string passcode = config["passcode"].asString();

            // Convert to wstring for SDK
            sdk_jwt = std::wstring(jwt.begin(), jwt.end());
            meeting_number = std::stoull(meetingNum);
            // ...
        } catch (const std::exception& e) {
            std::cerr << "Error parsing config.json: " << e.what() << std::endl;
        }
    } else {
        std::cerr << "config.json not found" << std::endl;
    }
}
```

## Event Listeners

### Complete Event Listener Templates

#### AuthServiceEventListener.cpp

```cpp
#include "AuthServiceEventListener.h"
#include <iostream>

AuthServiceEventListener::AuthServiceEventListener(void (*onComplete)())
    : onAuthComplete(onComplete) {}

void AuthServiceEventListener::onAuthenticationReturn(AuthResult ret) {
    switch (ret) {
    case AUTHRET_SUCCESS:
        std::cout << "Authentication successful" << std::endl;
        if (onAuthComplete) onAuthComplete();
        break;
    case AUTHRET_KEYORSECRETEMPTY:
        std::cerr << "SDK Key or Secret is empty" << std::endl;
        break;
    case AUTHRET_JWTTOKENWRONG:
        std::cerr << "JWT token is invalid" << std::endl;
        break;
    case AUTHRET_OVERTIME:
        std::cerr << "Authentication timeout" << std::endl;
        break;
    default:
        std::cerr << "Authentication failed: " << ret << std::endl;
    }
}

void AuthServiceEventListener::onLoginReturnWithReason(
    LOGINSTATUS ret,
    IAccountInfo* info,
    LoginFailReason reason) {
    // Handle login status
}

void AuthServiceEventListener::onLogout() {
    std::cout << "Logged out" << std::endl;
}

void AuthServiceEventListener::onZoomIdentityExpired() {
    std::cout << "Zoom identity expired" << std::endl;
}

void AuthServiceEventListener::onZoomAuthIdentityExpired() {
    std::cout << "Zoom auth identity expired - need to re-authenticate" << std::endl;
}
```

#### MeetingServiceEventListener.cpp

```cpp
#include "MeetingServiceEventListener.h"
#include <iostream>

MeetingServiceEventListener::MeetingServiceEventListener(
    void (*onJoined)(),
    void (*onEnded)(),
    void (*onInMeeting)()
) : onMeetingJoined(onJoined),
    onMeetingEnded(onEnded),
    onInMeetingCallback(onInMeeting) {}

void MeetingServiceEventListener::onMeetingStatusChanged(
    MeetingStatus status,
    int iResult) {

    switch (status) {
    case MEETING_STATUS_IDLE:
        std::cout << "Meeting status: IDLE" << std::endl;
        break;
    case MEETING_STATUS_CONNECTING:
        std::cout << "Meeting status: CONNECTING" << std::endl;
        if (onMeetingJoined) onMeetingJoined();
        break;
    case MEETING_STATUS_WAITINGFORHOST:
        std::cout << "Meeting status: WAITING FOR HOST" << std::endl;
        break;
    case MEETING_STATUS_INMEETING:
        std::cout << "Meeting status: IN MEETING" << std::endl;
        if (onInMeetingCallback) onInMeetingCallback();
        break;
    case MEETING_STATUS_DISCONNECTING:
        std::cout << "Meeting status: DISCONNECTING" << std::endl;
        break;
    case MEETING_STATUS_RECONNECTING:
        std::cout << "Meeting status: RECONNECTING" << std::endl;
        break;
    case MEETING_STATUS_FAILED:
        std::cerr << "Meeting status: FAILED (code: " << iResult << ")" << std::endl;
        if (onMeetingEnded) onMeetingEnded();
        break;
    case MEETING_STATUS_ENDED:
        std::cout << "Meeting status: ENDED" << std::endl;
        if (onMeetingEnded) onMeetingEnded();
        break;
    default:
        std::cout << "Meeting status: UNKNOWN (" << status << ")" << std::endl;
    }
}

void MeetingServiceEventListener::onMeetingStatisticsWarningNotification(
    StatisticsWarningType type) {
    std::cout << "Meeting statistics warning: " << type << std::endl;
}

void MeetingServiceEventListener::onMeetingParameterNotification(
    const MeetingParameter* param) {
    if (param) {
        std::cout << "Meeting parameter notification" << std::endl;
    }
}

void MeetingServiceEventListener::onSuspendParticipantsActivities() {
    std::cout << "Participants activities suspended" << std::endl;
}

void MeetingServiceEventListener::onAICompanionActiveChangeNotice(bool isActive) {
    std::cout << "AI Companion " << (isActive ? "activated" : "deactivated") << std::endl;
}
```

#### MeetingRecordingCtrlEventListener.cpp

```cpp
#include "MeetingRecordingCtrlEventListener.h"
#include <iostream>

void MeetingRecordingCtrlEventListener::onRecordingStatus(RecordingStatus status) {
    switch (status) {
    case Recording_Start:
        std::cout << "Recording started" << std::endl;
        break;
    case Recording_Stop:
        std::cout << "Recording stopped" << std::endl;
        break;
    case Recording_DiskFull:
        std::cerr << "Recording stopped - disk full" << std::endl;
        break;
    case Recording_Pause:
        std::cout << "Recording paused" << std::endl;
        break;
    case Recording_Connecting:
        std::cout << "Recording connecting" << std::endl;
        break;
    default:
        std::cout << "Recording status: " << status << std::endl;
    }
}

void MeetingRecordingCtrlEventListener::onRecordPrivilegeChanged(bool bCanRec) {
    std::cout << "Recording privilege: " << (bCanRec ? "granted" : "revoked") << std::endl;
}

void MeetingRecordingCtrlEventListener::onCloudRecordingStatus(RecordingStatus status) {
    std::cout << "Cloud recording status: " << status << std::endl;
}

void MeetingRecordingCtrlEventListener::onRecordingPrivilegeRequestStatus(
    RequestRecPrivilegeStatus status) {
    std::cout << "Recording privilege request status: " << status << std::endl;
}

void MeetingRecordingCtrlEventListener::onLocalRecordingPrivilegeRequestStatus(
    RequestLocalRecordingStatus status) {
    std::cout << "Local recording privilege request status: " << status << std::endl;
}

void MeetingRecordingCtrlEventListener::onLocalRecordingPrivilegeResponse(
    bool bAccept) {
    std::cout << "Local recording privilege "
              << (bAccept ? "accepted" : "denied") << std::endl;
}

void MeetingRecordingCtrlEventListener::onCustomizedLocalRecordingSourceNotification(
    ICustomizedLocalRecordingLayoutHelper* layout_helper) {
    std::cout << "Customized local recording source notification" << std::endl;
}
```

## Raw Data Requirements

### Recording Permission

Raw data access requires one of:
1. **Host** status
2. **Co-host** status
3. **Recording permission** from host
4. **Recording token** (app_privilege_token)

```cpp
bool CheckAndStartRawRecording() {
    IMeetingRecordingController* recordCtrl =
        meetingService->GetMeetingRecordingController();

    if (!recordCtrl) {
        std::cerr << "Failed to get recording controller" << std::endl;
        return false;
    }

    SDKError canStart = recordCtrl->CanStartRecording(false, 0);

    if (canStart == SDKERR_SUCCESS) {
        SDKError err = recordCtrl->StartRawRecording();
        if (err == SDKERR_SUCCESS) {
            std::cout << "Raw recording started" << std::endl;
            return true;
        } else {
            std::cerr << "StartRawRecording failed: " << err << std::endl;
            return false;
        }
    } else {
        std::cout << "Need host/cohost/recording permission" << std::endl;
        std::cout << "Requesting recording privilege..." << std::endl;
        recordCtrl->RequestLocalRecordingPrivilege();
        return false;
    }
}
```

### Video Resolutions

```cpp
// Available resolutions
videoHelper->setRawDataResolution(ZoomSDKResolution_90P);    // 160x90
videoHelper->setRawDataResolution(ZoomSDKResolution_180P);   // 320x180
videoHelper->setRawDataResolution(ZoomSDKResolution_360P);   // 640x360
videoHelper->setRawDataResolution(ZoomSDKResolution_720P);   // 1280x720
videoHelper->setRawDataResolution(ZoomSDKResolution_1080P);  // 1920x1080
```

### Audio Format

- **Format**: PCM (raw, uncompressed)
- **Sample Rate**: 32000 Hz (typical)
- **Channels**: Mono (1) or Stereo (2)
- **Bit Depth**: 16-bit
- **Byte Order**: Little-endian

## API Reference

### InitParam Structure

```cpp
struct tagInitParam {
    const wchar_t* strWebDomain;        // "https://zoom.us"
    const wchar_t* strSupportUrl;       // Support URL
    SDK_LANGUAGE_ID emLanguageID;       // LANGUAGE_English, etc.
    bool enableGenerateDump;            // Enable crash dump
    bool enableLogByDefault;            // Enable logging
    unsigned int uiLogFileSize;         // Log file size (MB, default: 5)
    const wchar_t* strLogFileFolder;    // Custom log folder path
    RawDataOptions rawdataOpts;         // Raw data options
    ConfigurableOptions obConfigOpts;   // Config options
};
```

### IAuthService Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `SetEvent(IAuthServiceEvent*)` | Set auth callback | `SDKError` |
| `SDKAuth(AuthContext&)` | Authenticate with JWT | `SDKError` |
| `GetAuthResult()` | Get auth status | `AuthResult` |
| `LogOut()` | Logout | `SDKError` |
| `GetAccountInfo()` | Get account info | `IAccountInfo*` |

### IMeetingService Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `SetEvent(IMeetingServiceEvent*)` | Set meeting callback | `SDKError` |
| `Join(JoinParam&)` | Join meeting | `SDKError` |
| `Start(StartParam&)` | Start meeting | `SDKError` |
| `Leave(LeaveMeetingCmd)` | Leave meeting | `SDKError` |
| `GetMeetingStatus()` | Get status | `MeetingStatus` |
| `GetMeetingInfo()` | Get meeting info | `IMeetingInfo*` |
| `GetMeetingVideoController()` | Video control | `IMeetingVideoController*` |
| `GetMeetingAudioController()` | Audio control | `IMeetingAudioController*` |
| `GetMeetingRecordingController()` | Recording control | `IMeetingRecordingController*` |
| `GetMeetingParticipantsController()` | Participants | `IMeetingParticipantsController*` |
| `GetMeetingChatController()` | Chat control | `IMeetingChatController*` |

### JoinParam4WithoutLogin Structure

```cpp
struct JoinParam4WithoutLogin {
    UINT64 meetingNumber;               // Meeting number
    const wchar_t* userName;            // Display name
    const wchar_t* psw;                 // Meeting password
    const wchar_t* vanityID;            // Personal link name
    const wchar_t* customer_key;        // Customer key
    const wchar_t* webinarToken;        // Webinar token
    const wchar_t* userZAK;             // Zoom Access Key
    const wchar_t* app_privilege_token; // App privilege token (for raw data)
    const wchar_t* onBehalfToken;       // On behalf token
    bool isVideoOff;                    // Start with video off
    bool isAudioOff;                    // Start with audio off
    bool isDirectShareDesktop;          // Share desktop directly
    bool isAudioAutoConnect;            // Auto-connect to audio
    bool isAutoRecording;               // Auto-start recording
};
```

### IZoomSDKRenderer Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `setRawDataResolution(ZoomSDKResolution)` | Set resolution | `SDKError` |
| `subscribe(uint32_t userId, ZoomSDKRawDataType)` | Subscribe to video | `SDKError` |
| `unSubscribe()` | Unsubscribe | `SDKError` |
| `getResolution()` | Get resolution | `ZoomSDKResolution` |
| `getSubscribeId()` | Get user ID | `uint32_t` |

### YUVRawDataI420 Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `GetStreamWidth()` | Video width | `uint32_t` |
| `GetStreamHeight()` | Video height | `uint32_t` |
| `GetYBuffer()` | Y plane buffer | `char*` |
| `GetUBuffer()` | U plane buffer | `char*` |
| `GetVBuffer()` | V plane buffer | `char*` |
| `GetBufferLen()` | Total buffer length | `uint32_t` |
| `GetRotation()` | Rotation angle | `int` |

**Video Format:**
- YUV420 (I420) planar format
- Y plane: `width * height` bytes
- U plane: `(width/2) * (height/2)` bytes
- V plane: `(width/2) * (height/2)` bytes
- Total size: `width * height * 1.5` bytes

### AudioRawData Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `GetBuffer()` | Audio buffer | `char*` |
| `GetBufferLen()` | Buffer length (bytes) | `uint32_t` |
| `GetSampleRate()` | Sample rate (Hz) | `uint32_t` |
| `GetChannelNum()` | Number of channels | `uint32_t` |

### Error Codes (SDKError)

| Code | Description |
|------|-------------|
| `SDKERR_SUCCESS` | Success |
| `SDKERR_INVALID_PARAMETER` | Invalid parameter |
| `SDKERR_UNINITIALIZE` | SDK not initialized |
| `SDKERR_UNAUTHENTICATION` | Not authenticated |
| `SDKERR_NO_PERMISSION` | No permission |
| `SDKERR_NO_AUDIODEVICE_ISFOUND` | No audio device |
| `SDKERR_NO_VIDEODEVICE_ISFOUND` | No video device |
| `SDKERR_INTERNAL_ERROR` | Internal error |
| `SDKERR_SERVICE_FAILED` | Service failed |
| `SDKERR_MEMORY_FAILED` | Memory allocation failed |
| `SDKERR_TOO_FREQUENT_CALL` | API called too frequently |
| `SDKERR_WRONG_USAGE` | Wrong API usage |

### Authentication Results (AuthResult)

| Result | Description |
|--------|-------------|
| `AUTHRET_SUCCESS` | Authentication successful |
| `AUTHRET_KEYORSECRETEMPTY` | Key or secret empty |
| `AUTHRET_JWTTOKENWRONG` | JWT token invalid |
| `AUTHRET_OVERTIME` | Operation timed out |

### Meeting Status (MeetingStatus)

| Status | Description |
|--------|-------------|
| `MEETING_STATUS_IDLE` | No meeting |
| `MEETING_STATUS_CONNECTING` | Connecting |
| `MEETING_STATUS_INMEETING` | In meeting |
| `MEETING_STATUS_RECONNECTING` | Reconnecting |
| `MEETING_STATUS_FAILED` | Failed |
| `MEETING_STATUS_ENDED` | Meeting ended |
| `MEETING_STATUS_WAITINGFORHOST` | Waiting for host |
| `MEETING_STATUS_DISCONNECTING` | Disconnecting |

## Troubleshooting

### Common Build Errors

#### Error: Cannot open include file 'json/json.h'

**Cause**: jsoncpp include path not configured

**Fix**:
1. Ensure vcpkg installed jsoncpp: `.\vcpkg install jsoncpp:x64-windows`
2. Add to **Additional Include Directories**:
   ```
   C:\vcpkg\packages\jsoncpp_x64-windows\include
   ```
3. Or in Project Properties → vcpkg → Use vcpkg manifest: Yes

#### Error: unresolved external symbol "InitSDK"

**Cause**: sdk.lib not linked

**Fix**:
1. Add to **Additional Library Directories**:
   ```
   $(SolutionDir)SDK\$(PlatformTarget)\lib
   ```
2. Add to **Additional Dependencies**:
   ```
   sdk.lib
   ```

#### Error: sdk.dll not found when running

**Cause**: DLLs not copied to output directory

**Fix**: Add Post-Build Event:
```cmd
xcopy /Y /D "$(SolutionDir)SDK\$(PlatformTarget)\bin\*.*" "$(OutDir)"
```

### Runtime Errors

#### Error: InitSDK returns SDKERR_INTERNAL_ERROR

**Cause**: Invalid SDK initialization parameters or missing DLLs

**Fix**:
1. Ensure all SDK DLLs are in the same directory as .exe
2. Check InitParam values are valid
3. Ensure strWebDomain is "https://zoom.us"

#### Error: SDKAuth returns AUTHRET_JWTTOKENWRONG

**Cause**: Invalid JWT token

**Fix**:
1. Verify JWT token is correctly generated with SDK Key and Secret
2. Check token expiration time (iat and exp)
3. Ensure meeting number in JWT matches meeting number in join request
4. See [authorization.md](../../references/authorization.md) for JWT generation

#### Error: Join returns SDKERR_INVALID_PARAMETER

**Cause**: Invalid join parameters

**Fix**:
1. Verify meeting number is correct UINT64
2. Check meeting password is valid
3. Ensure userName is not empty
4. Convert strings to wchar_t* correctly:
   ```cpp
   std::wstring userName = L"Bot User";
   params.userName = userName.c_str();
   ```

#### Cannot start raw recording

**Cause**: No recording permission

**Fix**:
1. Wait for host to grant recording permission
2. Use `RequestLocalRecordingPrivilege()` to request permission
3. Or use `app_privilege_token` in JoinParam:
   ```cpp
   params.app_privilege_token = recording_token.c_str();
   ```
4. Or join as host using `onBehalfToken`

### Video/Audio Issues

#### YUV video file is corrupted when played

**Cause**: Mixed resolutions or incorrect parameters

**Fix**:
1. Check console output for resolution changes
2. Create new file when resolution changes
3. Verify ffmpeg command matches actual resolution:
   ```cmd
   ffmpeg -video_size 1280x720 -pixel_format yuv420p -f rawvideo -i output.yuv output.mp4
   ```

#### Audio file has no sound

**Cause**: Wrong audio format parameters

**Fix**:
1. Check audio sample rate: `data->GetSampleRate()`
2. Verify channel count: `data->GetChannelNum()`
3. Use correct ffmpeg parameters:
   ```cmd
   ffplay -f s16le -ar 32000 -ac 1 audio.pcm
   ```

#### Video subscription fails

**Cause**: Not in meeting or no recording permission

**Fix**:
1. Ensure you're in meeting (`MEETING_STATUS_INMEETING`)
2. Start raw recording first: `StartRawRecording()`
3. Check recording permission: `CanStartRecording()`
4. Subscribe after recording started

## Cleanup

```cpp
void CleanSDK() {
    // Unsubscribe from raw data
    if (videoHelper) {
        videoHelper->unSubscribe();
        videoHelper = nullptr;
    }

    if (audioHelper) {
        audioHelper->unSubscribe();
        audioHelper = nullptr;
    }

    // Destroy services
    if (authService) {
        DestroyAuthService(authService);
        authService = nullptr;
    }

    if (meetingService) {
        DestroyMeetingService(meetingService);
        meetingService = nullptr;
    }

    // Clean up SDK
    CleanUPSDK();
}
```

## Docker Support (Windows Containers)

### Dockerfile

```dockerfile
# Use Windows Server Core
FROM mcr.microsoft.com/windows/servercore:ltsc2022

# Install Visual C++ Redistributables
ADD https://aka.ms/vs/17/release/vc_redist.x64.exe C:\vcredist.exe
RUN C:\vcredist.exe /install /quiet /norestart

# Copy your application
WORKDIR C:\app
COPY SDK C:\app\SDK
COPY x64\Release\YourApp.exe C:\app\
COPY config.json C:\app\

CMD ["C:\\app\\YourApp.exe"]
```

**Note**: Windows containers require Windows-based Docker host. GUI applications are supported but won't display UI.

## Authentication Requirements (2026 Update)

> **Important**: Beginning **March 2, 2026**, apps joining meetings outside their account must be authorized.

Options:
- **App Privilege Token (OBF)** - Recommended for bots (`app_privilege_token`)
- **ZAK Token** - Zoom Access Key (`userZAK`)
- **On Behalf Token** - For specific use cases (`onBehalfToken`)

See [bot-authentication.md](../../references/bot-authentication.md) for details.

## Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/windows/
- **API Reference**: https://marketplacefront.zoom.us/sdk/meeting/windows/annotated.html
- **Sample code**: https://github.com/zoom/meetingsdk-windows-raw-recording-sample
- **Developer forum**: https://devforum.zoom.us/
