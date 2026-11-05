# Official Sample Applications

Reference guide for Zoom Video SDK Windows sample applications.

**Official Repository**: https://github.com/zoom/videosdk-windows-rawdata-sample

---

## Sample Overview

| Sample | Description | Key Features |
|--------|-------------|--------------|
| **VSDK_SkeletonDemo** | Minimal session join | Simplest starting point |
| **VSDK_getRawVideo** | Capture raw video | YUV420 frame extraction |
| **VSDK_getRawAudio** | Capture raw audio | PCM audio extraction |
| **VSDK_getRawShare** | Capture screen share | Share content capture |
| **VSDK_sendRawVideo** | Send custom video | Virtual camera injection |
| **VSDK_sendRawAudio** | Send custom audio | Virtual microphone injection |
| **VSDK_sendRawShare** | Send custom share | Custom screen share source |
| **VSDK_CloudRecording** | Cloud recording | Start/stop cloud recording |
| **VSDK_CommandChannel** | Custom messaging | Send/receive custom commands |
| **VSDK_CallIn** | PSTN dial-in | Phone dial-in support |
| **VSDK_Callout** | PSTN dial-out | Phone dial-out support |
| **VSDK_ServiceQuality** | Network statistics | Quality monitoring |
| **VSDK_TranscriptionAndTranslation** | Live transcription | Real-time captions |
| **VSDK_MultiStreamVideo** | Multiple video streams | Multi-camera support |
| **VSDK_PreviewCameraAndMicrophone** | Device preview | Pre-join device testing |
| **VSDK_Share2ndCameraAsMultiCam** | Secondary camera | Multi-camera sharing |
| **VSDK_Share2ndCameraAsShareScreenDemo** | Camera as share | Camera content sharing |
| **VSDK_ShareScreenPreprocessorDemo** | Share preprocessing | Custom share processing |
| **VSDK_RTMSDemo** | Real-time messaging | RTMS integration |
| **VSDK_DuilibDemo2** | Full UI demo | Complete GUI application |

---

## Recommended Learning Path

### 1. Start Here: VSDK_SkeletonDemo

Minimal code to join a session. Demonstrates:
- SDK initialization
- JWT authentication
- Session join/leave
- Windows message loop
- Basic delegate implementation

**Key patterns to learn:**
```cpp
// 1. Create SDK
IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();

// 2. Initialize
ZoomVideoSDKInitParams params;
params.domain = L"https://zoom.us";
sdk->initialize(params);

// 3. Add delegate
sdk->addListener(myDelegate);

// 4. Join session
ZoomVideoSDKSessionContext ctx;
ctx.sessionName = L"session";
ctx.token = L"jwt";
ctx.audioOption.connect = false;
sdk->joinSession(ctx);

// 5. Message loop (CRITICAL)
while (running) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    Sleep(10);
}
```

### 2. Video Capture: VSDK_getRawVideo

Capture raw YUV420 video frames. Demonstrates:
- `IZoomVideoSDKRawDataPipeDelegate` implementation
- `onRawDataFrameReceived()` callback
- YUV buffer extraction (Y, U, V planes)
- Resolution and rotation handling

**Key patterns:**
```cpp
class VideoCapture : public IZoomVideoSDKRawDataPipeDelegate {
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();
        char* yBuffer = data->GetYBuffer();
        char* uBuffer = data->GetUBuffer();
        char* vBuffer = data->GetVBuffer();
        // Process frames...
    }
};

// Subscribe
IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
pipe->subscribe(ZoomVideoSDKResolution_720P, videoCapture);
```

### 3. Audio Capture: VSDK_getRawAudio

Capture raw PCM audio. Demonstrates:
- Mixed audio (all participants)
- Per-user audio separation
- Audio format (sample rate, channels)

**Key patterns:**
```cpp
void onMixedAudioRawDataReceived(AudioRawData* data) override {
    char* buffer = data->GetBuffer();
    int length = data->GetBufferLen();
    int sampleRate = data->GetSampleRate();  // 32000 Hz
    int channels = data->GetChannelNum();     // 1 or 2
    // Process PCM audio...
}
```

### 4. Video Injection: VSDK_sendRawVideo

Send custom video as virtual camera. Demonstrates:
- `IZoomVideoSDKVideoSource` implementation
- Frame sending with `sendVideoFrame()`
- YUV frame creation
- Frame rate control

### 5. Audio Injection: VSDK_sendRawAudio

Send custom audio as virtual microphone. Demonstrates:
- `IZoomVideoSDKVirtualAudioMic` implementation
- PCM audio sending
- Sample rate matching

---

## Sample Categories

### Raw Data Capture

| Sample | Input | Output |
|--------|-------|--------|
| VSDK_getRawVideo | Remote video | YUV420 frames |
| VSDK_getRawAudio | Session audio | PCM samples |
| VSDK_getRawShare | Screen share | YUV420 frames |

### Raw Data Injection

| Sample | Input | Output |
|--------|-------|--------|
| VSDK_sendRawVideo | YUV420 frames | Virtual camera |
| VSDK_sendRawAudio | PCM samples | Virtual mic |
| VSDK_sendRawShare | YUV420 frames | Screen share |

### Communication

| Sample | Feature |
|--------|---------|
| VSDK_CommandChannel | Custom command messaging (60 msgs/sec) |
| VSDK_CallIn | PSTN phone dial-in |
| VSDK_Callout | PSTN phone dial-out |

### Recording & Streaming

| Sample | Feature |
|--------|---------|
| VSDK_CloudRecording | Zoom cloud recording |
| VSDK_RTMSDemo | Real-time messaging service |

### Advanced Features

| Sample | Feature |
|--------|---------|
| VSDK_ServiceQuality | Network quality statistics |
| VSDK_TranscriptionAndTranslation | Live captions |
| VSDK_MultiStreamVideo | Multiple video streams |
| VSDK_PreviewCameraAndMicrophone | Device preview before join |
| VSDK_ShareScreenPreprocessorDemo | Custom share processing |

---

## Common Patterns Across Samples

### 1. Initialization Pattern

All samples follow this pattern:
```cpp
// Initialize SDK
IZoomVideoSDK* sdk = CreateZoomVideoSDKObj();
ZoomVideoSDKInitParams params;
params.domain = L"https://zoom.us";
params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
sdk->initialize(params);
```

### 2. Delegate Registration

Always register before joining:
```cpp
sdk->addListener(new MyDelegate());
sdk->joinSession(context);
```

### 3. Audio Connection

Connect audio in callback, not during join:
```cpp
context.audioOption.connect = false;  // Join config

void onSessionJoin() override {
    sdk->getAudioHelper()->startAudio();  // Connect here
}
```

### 4. Message Loop

All samples include message loop:
```cpp
while (!g_exit) {
    MSG msg;
    while (PeekMessage(&msg, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    Sleep(10);
}
```

---

## Building Samples

### Prerequisites

1. Visual Studio 2019 or 2022
2. Windows SDK 10.0.19041.0+
3. Zoom Video SDK (download from Marketplace)

### Build Steps

1. Open solution file (`.sln`)
2. Set platform to x64
3. Set configuration to Release
4. Build solution (Ctrl+Shift+B)
5. Copy SDK DLLs to output directory

### Configuration

Each sample uses `config.json`:
```json
{
  "jwt": "your-jwt-token",
  "session_name": "test-session",
  "password": "",
  "user_name": "Bot"
}
```

---

## Related Documentation

- [SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md) - Universal patterns
- [Session Join Pattern](../examples/session-join-pattern.md) - Complete join code
- [Raw Video Capture](../examples/raw-video-capture.md) - YUV capture details
- [API Reference](windows-reference.md) - Method signatures
- [Delegate Methods](delegate-methods.md) - All callbacks

---

## External Resources

- **GitHub Repository**: https://github.com/zoom/videosdk-windows-rawdata-sample
- **Official Documentation**: https://developers.zoom.us/docs/video-sdk/windows/
- **API Reference**: https://marketplacefront.zoom.us/sdk/custom/windows/
- **Developer Forum**: https://devforum.zoom.us/

---

**Recommendation**: Start with `VSDK_SkeletonDemo` to understand the basic flow, then move to `VSDK_getRawVideo` or `VSDK_getRawAudio` based on your needs.
