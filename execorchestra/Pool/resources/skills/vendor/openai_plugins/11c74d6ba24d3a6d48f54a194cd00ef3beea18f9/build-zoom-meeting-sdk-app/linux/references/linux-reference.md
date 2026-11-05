# Meeting SDK - Linux Reference

Complete reference for Zoom Meeting SDK on Linux including dependencies, Docker setup, and troubleshooting.

## System Requirements

- **OS**: Ubuntu 22+, CentOS 8/9, Oracle Linux 8
- **Architecture**: x86_64
- **Build Tools**: cmake 3.16+, gcc/g++ with C++11 support

## Dependencies

### Ubuntu 22/23

```bash
# Build essentials
apt-get update
apt-get install -y build-essential cmake

# X11/XCB libraries (required by SDK)
apt-get install -y --no-install-recommends --no-install-suggests \
    libx11-xcb1 \
    libxcb-xfixes0 \
    libxcb-shape0 \
    libxcb-shm0 \
    libxcb-randr0 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-xtest0

# Optional but recommended
apt-get install -y --no-install-recommends --no-install-suggests \
    libdbus-1-3 \
    libglib2.0-0 \
    libgbm1 \
    libxfixes3 \
    libgl1 \
    libdrm2 \
    libgssapi-krb5-2

# For curl-based JWT fetching
apt-get install -y \
    libcurl4-openssl-dev \
    openssl \
    ca-certificates \
    pkg-config

# Audio support (PulseAudio)
apt-get install -y \
    libasound2 \
    libasound2-plugins \
    alsa \
    alsa-utils \
    alsa-oss \
    pulseaudio \
    pulseaudio-utils

# Optional: FFmpeg for video processing
apt-get install -y libavformat-dev libavfilter-dev libavdevice-dev ffmpeg

# If SDL2 errors occur
apt-get install -y libegl-mesa0 libsdl2-dev g++-multilib
```

### CentOS 8/9

```bash
# Build essentials
sudo yum install cmake gcc gcc-c++

# Enable required repos (CentOS 9)
sudo dnf config-manager --set-enabled crb
sudo dnf install epel-release epel-next-release

# XCB libraries
sudo yum install \
    libxcb-devel \
    xcb-util-devel \
    xcb-util-image \
    xcb-util-keysyms

# OpenGL/Mesa (for runtime)
sudo yum install \
    mesa-libGL \
    mesa-libGL-devel \
    mesa-dri-drivers

# Curl support
sudo yum install -y openssl-devel libcurl-devel

# PulseAudio
sudo yum install -y pulseaudio pulseaudio-utils

# Optional: FFmpeg
sudo yum install -y libavformat-dev libavfilter-dev libavdevice-dev ffmpeg

# If SDL2 errors occur
sudo yum install -y SDL2-devel
```

## CMakeLists.txt Template

```cmake
cmake_minimum_required(VERSION 3.16)

project(meetingSDKDemo CXX)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11 -g -O0")
add_definitions(-std=c++11)
set(CMAKE_BUILD_TYPE Debug)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/lib)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin)

find_package(PkgConfig REQUIRED)
find_package(ZLIB REQUIRED)

# GLib (required for main loop)
pkg_check_modules(GLIB REQUIRED glib-2.0)
pkg_check_modules(GIO REQUIRED gio-2.0)

# Include directories
include_directories(${CMAKE_SOURCE_DIR}/include)
include_directories(${CMAKE_SOURCE_DIR}/include/h)
include_directories(${GLIB_INCLUDE_DIRS} ${GIO_INCLUDE_DIRS})

# Common GLib paths
include_directories(/usr/include/glib-2.0/)
include_directories(/usr/include/glib-2.0/glib)
include_directories(/usr/lib/x86_64-linux-gnu/glib-2.0/include/)
include_directories(/usr/lib64/glib-2.0/include/)

# Link directories
link_directories(${GLIB_LIBRARY_DIRS} ${GIO_LIBRARY_DIRS})
link_directories(${CMAKE_SOURCE_DIR}/lib/zoom_meeting_sdk)
link_directories(${CMAKE_SOURCE_DIR}/lib/zoom_meeting_sdk/qt_libs)
link_directories(${CMAKE_SOURCE_DIR}/lib/zoom_meeting_sdk/qt_libs/Qt/lib)

add_definitions(${GLIB_CFLAGS_OTHER} ${GIO_CFLAGS_OTHER})

# Source files
add_executable(meetingSDKDemo
    ${CMAKE_SOURCE_DIR}/meeting_sdk_demo.cpp
    ${CMAKE_SOURCE_DIR}/AuthServiceEventListener.cpp
    ${CMAKE_SOURCE_DIR}/MeetingServiceEventListener.cpp
    ${CMAKE_SOURCE_DIR}/MeetingReminderEventListener.cpp
    ${CMAKE_SOURCE_DIR}/MeetingParticipantsCtrlEventListener.cpp
    ${CMAKE_SOURCE_DIR}/MeetingRecordingCtrlEventListener.cpp
    # Raw data handlers (if needed)
    ${CMAKE_SOURCE_DIR}/ZoomSDKRenderer.cpp
    ${CMAKE_SOURCE_DIR}/ZoomSDKAudioRawData.cpp
    ${CMAKE_SOURCE_DIR}/ZoomSDKVideoSource.cpp
    ${CMAKE_SOURCE_DIR}/ZoomSDKVirtualAudioMicEvent.cpp
)

# Link libraries
target_link_libraries(meetingSDKDemo ${GLIB_LIBRARIES} ${GIO_LIBRARIES})
target_link_libraries(meetingSDKDemo gcc_s gcc)
target_link_libraries(meetingSDKDemo meetingsdk)
target_link_libraries(meetingSDKDemo glib-2.0)
target_link_libraries(meetingSDKDemo curl)
target_link_libraries(meetingSDKDemo pthread)

# Create symlink for SDK
execute_process(COMMAND ln -sf libmeetingsdk.so libmeetingsdk.so.1
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}/lib/zoom_meeting_sdk
)

# Copy config to bin
configure_file(${CMAKE_SOURCE_DIR}/config.txt ${CMAKE_SOURCE_DIR}/bin/config.txt COPYONLY)

# Copy SDK files to bin
file(COPY ${CMAKE_SOURCE_DIR}/lib/zoom_meeting_sdk/ DESTINATION ${CMAKE_SOURCE_DIR}/bin)
```

## Configuration File

### config.txt Format

```
meeting_number: "1234567890"
token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
meeting_password: "abc123"
recording_token: ""
onBehalfOf_Token: ""
GetVideoRawData: "true"
GetAudioRawData: "true"
SendVideoRawData: "false"
SendAudioRawData: "false"
```

### config.json Format (Alternative)

```json
{
  "meeting_number": "1234567890",
  "token": "YOUR_JWT_TOKEN",
  "meeting_password": "abc123",
  "recording_token": "",
  "remote_url": "https://your-auth-endpoint.com",
  "useJWTTokenFromWebService": "false",
  "useRecordingTokenFromWebService": "false"
}
```

## Docker Setup

### Dockerfile (Ubuntu)

```dockerfile
FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential cmake \
    libx11-xcb1 libxcb-xfixes0 libxcb-shape0 libxcb-shm0 \
    libxcb-randr0 libxcb-image0 libxcb-keysyms1 libxcb-xtest0 \
    libdbus-1-3 libglib2.0-0 libgbm1 libxfixes3 libgl1 libdrm2 \
    libcurl4-openssl-dev openssl ca-certificates pkg-config \
    pulseaudio pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY . .

# Build
RUN cd demo && cmake -B build && cd build && make

# Setup audio config
RUN mkdir -p ~/.config && \
    echo "[General]" > ~/.config/zoomus.conf && \
    echo "system.audio.type=default" >> ~/.config/zoomus.conf

CMD ["./demo/bin/meetingSDKDemo"]
```

### PulseAudio Setup (Headless)

Create `setup-pulseaudio.sh`:

```bash
#!/bin/bash

# Start PulseAudio daemon
pulseaudio --start --exit-idle-time=-1

# Create virtual speaker
pactl load-module module-null-sink sink_name=virtual_speaker sink_properties=device.description="Virtual_Speaker"

# Create virtual microphone
pactl load-module module-null-sink sink_name=virtual_mic sink_properties=device.description="Virtual_Microphone"

# Create zoomus.conf
mkdir -p ~/.config
cat > ~/.config/zoomus.conf << EOF
[General]
system.audio.type=default
EOF

echo "PulseAudio configured for headless operation"
```

### Docker Compose

```yaml
version: '3.8'
services:
  meeting-bot:
    build: .
    environment:
      - PULSE_SERVER=unix:/run/user/1000/pulse/native
    volumes:
      - ./config.txt:/app/demo/bin/config.txt
      - /run/user/1000/pulse:/run/user/1000/pulse
    network_mode: host
```

## Event Listeners

### AuthServiceEventListener

```cpp
// AuthServiceEventListener.h
#include "auth_service_interface.h"

class AuthServiceEventListener : public IAuthServiceEvent {
public:
    AuthServiceEventListener(void (*onComplete)())
        : onAuthComplete(onComplete) {}

    void onAuthenticationReturn(AuthResult ret) override {
        if (ret == AUTHRET_SUCCESS && onAuthComplete) {
            onAuthComplete();
        }
    }

    void onLoginReturnWithReason(LOGINSTATUS ret, IAccountInfo* info, LoginFailReason reason) override {}
    void onLogout() override {}
    void onZoomIdentityExpired() override {}
    void onZoomAuthIdentityExpired() override {}

private:
    void (*onAuthComplete)();
};
```

### MeetingServiceEventListener

```cpp
// MeetingServiceEventListener.h
#include "meeting_service_interface.h"

class MeetingServiceEventListener : public IMeetingServiceEvent {
public:
    MeetingServiceEventListener(
        void (*onJoined)(),
        void (*onEnded)(),
        void (*onInMeeting)()
    ) : onMeetingJoined(onJoined),
        onMeetingEnded(onEnded),
        onInMeetingCallback(onInMeeting) {}

    void onMeetingStatusChanged(MeetingStatus status, int iResult) override {
        if (status == MEETING_STATUS_CONNECTING) {
            if (onMeetingJoined) onMeetingJoined();
        }
        else if (status == MEETING_STATUS_INMEETING) {
            if (onInMeetingCallback) onInMeetingCallback();
        }
        else if (status == MEETING_STATUS_ENDED) {
            if (onMeetingEnded) onMeetingEnded();
        }
    }

    void onMeetingStatisticsWarningNotification(StatisticsWarningType type) override {}
    void onMeetingParameterNotification(const MeetingParameter* param) override {}
    void onSuspendParticipantsActivities() override {}
    void onAICompanionActiveChangeNotice(bool isActive) override {}

private:
    void (*onMeetingJoined)();
    void (*onMeetingEnded)();
    void (*onInMeetingCallback)();
};
```

### MeetingParticipantsCtrlEventListener

```cpp
// MeetingParticipantsCtrlEventListener.h
#include "meeting_service_components/meeting_participants_ctrl_interface.h"

class MeetingParticipantsCtrlEventListener : public IMeetingParticipantsCtrlEvent {
public:
    MeetingParticipantsCtrlEventListener(
        void (*onHost)(),
        void (*onCoHost)()
    ) : onIsHost(onHost), onIsCoHost(onCoHost) {}

    void onUserJoin(IList<unsigned int>* lstUserID, const zchar_t* strUserList) override {}
    void onUserLeft(IList<unsigned int>* lstUserID, const zchar_t* strUserList) override {}
    void onHostChangeNotification(unsigned int userId) override {
        if (onIsHost) onIsHost();
    }
    void onCoHostChangeNotification(unsigned int userId, bool isCoHost) override {
        if (isCoHost && onIsCoHost) onIsCoHost();
    }
    void onLowOrRaiseHandStatusChanged(bool bLow, unsigned int userid) override {}

private:
    void (*onIsHost)();
    void (*onIsCoHost)();
};
```

## Raw Data Requirements

### Recording Permission

Raw data access requires one of:
1. **Host** status
2. **Co-host** status
3. **Recording permission** from host
4. **Recording token** (app_privilege_token)

```cpp
// Check and start raw recording
void CheckAndStartRawRecording() {
    IMeetingRecordingController* recordCtrl =
        m_pMeetingService->GetMeetingRecordingController();

    SDKError canStart = recordCtrl->CanStartRawRecording();

    if (canStart == SDKERR_SUCCESS) {
        recordCtrl->StartRawRecording();
        // Now subscribe to raw data
    } else {
        std::cout << "Need host/cohost/recording permission" << std::endl;
    }
}
```

### Video Resolutions

```cpp
videoHelper->setRawDataResolution(ZoomSDKResolution_90P);
videoHelper->setRawDataResolution(ZoomSDKResolution_180P);
videoHelper->setRawDataResolution(ZoomSDKResolution_360P);
videoHelper->setRawDataResolution(ZoomSDKResolution_720P);
videoHelper->setRawDataResolution(ZoomSDKResolution_1080P);
```

### Audio Format

- **Format**: PCM (raw)
- **Sample Rate**: 32000 Hz
- **Channels**: Mono or Stereo
- **Bit Depth**: 16-bit

## Compilation Tips

> **Note**: Specific methods/types may vary by SDK version. Always check SDK headers.

### Event Listener Interfaces
SDK event listener interfaces have many pure virtual methods. **Implement ALL of them** (even with empty bodies) or you'll get "invalid new-expression of abstract class type" errors. Check the SDK header for the complete interface definition.

### Include Order Issues
Some SDK headers don't include their dependencies. If you get undefined type errors:
- Add standard includes (`<ctime>`, `<cstdint>`) before SDK headers
- Include related SDK headers in dependency order (e.g., `meeting_audio_interface.h` before `meeting_participants_ctrl_interface.h`)

### Method Signatures
Reference samples may have outdated method names. The SDK header files are the authoritative source - always verify method signatures there.

## Troubleshooting

### Segmentation Fault on AuthSDK

**Cause**: OpenSSL version incompatibility (needs 1.1.x)

**Fix** (Ubuntu):
```bash
cd /tmp
wget http://security.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.20_amd64.deb
sudo dpkg -i libssl1.1_1.1.1f-1ubuntu2.20_amd64.deb
```

### libGL Error (Mesa)

```
libGL error: MESA-LOADER: failed to open swrast
```

**Fix**:
```bash
# Ubuntu
apt-get install mesa-libGL mesa-dri-drivers

# CentOS
yum install mesa-libGL mesa-libGL-devel mesa-dri-drivers
```

### XCB Libraries Missing

```
libxcb-image.so.0 not found
libxcb-keysyms.so.1 not found
```

**Fix**:
```bash
# Ubuntu
apt-get install libxcb-image0 libxcb-keysyms1

# CentOS
yum install xcb-util-image xcb-util-keysyms
```

### No Audio in Docker

**Fix**: Create zoomus.conf before running:
```bash
mkdir -p ~/.config
echo -e "[General]\nsystem.audio.type=default" > ~/.config/zoomus.conf
```

### Cannot Start Raw Recording

**Cause**: No recording permission

**Fix**: Either:
1. Wait for host to grant recording permission
2. Use `recording_token` in config (get from [Recording Token API](https://developers.zoom.us/docs/meeting-sdk/apis/#operation/meetingLocalRecordingJoinToken))
3. Join as host using `onBehalfOf_Token`

## Cleanup

```cpp
void CleanSDK() {
    if (videoHelper) videoHelper->unSubscribe();
    if (audioHelper) audioHelper->unSubscribe();

    if (m_pAuthService) {
        DestroyAuthService(m_pAuthService);
        m_pAuthService = NULL;
    }
    if (m_pSettingService) {
        DestroySettingService(m_pSettingService);
        m_pSettingService = NULL;
    }
    if (m_pMeetingService) {
        DestroyMeetingService(m_pMeetingService);
        m_pMeetingService = NULL;
    }

    CleanUPSDK();
}
```

## API Reference

### InitParam Structure

```cpp
struct tagInitParam {
    const zchar_t* strWebDomain;        // "https://zoom.us"
    const zchar_t* strBrandingName;     // Custom branding name
    const zchar_t* strSupportUrl;       // Support URL
    SDK_LANGUAGE_ID emLanguageID;       // LANGUAGE_English, etc.
    bool enableGenerateDump;            // Enable crash dump
    bool enableLogByDefault;            // Enable logging
    unsigned int uiLogFileSize;         // Log file size (MB, default: 5)
    RawDataOptions rawdataOpts;         // Raw data options
    ConfigurableOptions obConfigOpts;   // Config options
    int wrapperType;                    // SDK wrapper type
};
```

### IAuthService Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `SetEvent(IAuthServiceEvent*)` | Set auth callback | `SDKError` |
| `SDKAuth(AuthContext&)` | Authenticate with JWT | `SDKError` |
| `GetAuthResult()` | Get auth status | `AuthResult` |
| `GetSDKIdentity()` | Get SDK identity | `const zchar_t*` |
| `LogOut()` | Logout | `SDKError` |
| `GetAccountInfo()` | Get account info | `IAccountInfo*` |
| `GetLoginStatus()` | Get login status | `LOGINSTATUS` |

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
    const zchar_t* userName;            // Display name
    const zchar_t* psw;                 // Meeting password
    const zchar_t* vanityID;            // Personal link name
    const zchar_t* customer_key;        // Customer key
    const zchar_t* webinarToken;        // Webinar token
    const zchar_t* userZAK;             // Zoom Access Key
    const zchar_t* app_privilege_token; // App privilege token (for raw data)
    const zchar_t* onBehalfToken;       // On behalf token
    bool isVideoOff;                    // Start with video off
    bool isAudioOff;                    // Start with audio off
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

**ZoomSDKResolution values:** `ZoomSDKResolution_90P`, `_180P`, `_360P`, `_720P`, `_1080P`

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
| `GetAlphaBuffer()` | Alpha channel | `char*` |

**Video Format:**
- YUV420 (I420) contiguous planar format (no strides)
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

**Audio Format:**
- PCM (uncompressed), 16-bit, little-endian
- Sample rate: 32000 Hz (typical)
- Channels: 1 (mono) or 2 (stereo)

### Playing Raw Files with FFmpeg

Raw files have no headers - specify format explicitly:

```bash
# Play YUV video (adjust dimensions to match your output)
ffplay -video_size 640x360 -pixel_format yuv420p -f rawvideo video.yuv

# Convert YUV to MP4
ffmpeg -video_size 640x360 -pixel_format yuv420p -f rawvideo -i video.yuv -c:v libx264 output.mp4

# Play PCM audio
ffplay -f s16le -ar 32000 -ac 1 audio.pcm

# Convert PCM to WAV
ffmpeg -f s16le -ar 32000 -ac 1 -i audio.pcm output.wav

# Combine video + audio into MP4
ffmpeg -video_size 640x360 -pixel_format yuv420p -f rawvideo -i video.yuv \
       -f s16le -ar 32000 -ac 1 -i audio.pcm \
       -c:v libx264 -c:a aac -shortest output.mp4
```

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

## Authentication Requirements (2026 Update)

> **Important**: Beginning **March 2, 2026**, apps joining meetings outside their account must be authorized.

Options:
- **App Privilege Token (OBF)** - Recommended for bots
- **ZAK Token** - Zoom Access Key
- **On Behalf Token** - For specific use cases

## Resources

- **Official docs**: https://developers.zoom.us/docs/meeting-sdk/linux/
- **API Reference**: https://marketplacefront.zoom.us/sdk/meeting/linux/index.html
- **Headless sample**: https://github.com/zoom/meetingsdk-headless-linux-sample
- **Raw recording sample**: https://github.com/zoom/meetingsdk-linux-raw-recording-sample
- **Auth endpoint**: https://github.com/zoom/meetingsdk-auth-endpoint-sample
