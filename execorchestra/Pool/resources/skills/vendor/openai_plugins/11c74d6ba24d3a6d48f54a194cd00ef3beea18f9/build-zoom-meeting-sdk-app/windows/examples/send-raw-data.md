# Send Raw Data (Virtual Camera & Microphone)

Send custom video and audio into a Zoom meeting as a virtual camera or microphone. This enables:
- Streaming pre-recorded video files
- AI-generated video/audio
- Custom video effects
- Screen capture injection
- Audio playback into meetings

---

## Overview

The SDK provides three "send" interfaces:
1. **IZoomSDKVideoSource** - Virtual camera (send video)
2. **IZoomSDKVirtualAudioMicEvent** - Virtual microphone (send audio)
3. **IZoomSDKShareSource** - Virtual share source (send screen share)

All follow the same pattern:
1. Implement the interface
2. Pass it during meeting join/start
3. SDK calls your callbacks when ready to send

---

## Send Video (Virtual Camera)

### Interface: IZoomSDKVideoSource

```cpp
#include <rawdata/rawdata_video_source_helper_interface.h>

class ZoomSDKVideoSource : public IZoomSDKVideoSource {
private:
    IZoomSDKVideoSender* video_sender_ = nullptr;
    string video_source_;

public:
    ZoomSDKVideoSource(string video_source) : video_source_(video_source) {}

    void onInitialize(IZoomSDKVideoSender* sender,
                      IList<VideoSourceCapability>* support_cap_list,
                      VideoSourceCapability& suggest_cap) override {
        // Store the sender - you'll use this to send frames
        video_sender_ = sender;
        std::cout << "Video source initialized" << std::endl;
    }

    void onPropertyChange(IList<VideoSourceCapability>* support_cap_list,
                          VideoSourceCapability suggest_cap) override {
        // SDK suggests resolution/framerate based on network
        std::cout << "Suggested: " << suggest_cap.width << "x"
                  << suggest_cap.height << " @ " << suggest_cap.frame << "fps" << std::endl;
    }

    void onStartSend() override {
        // SDK is ready - start sending frames in a separate thread
        std::thread([this]() { PlayVideo(); }).detach();
    }

    void onStopSend() override {
        // Stop sending frames
        running_ = false;
    }

    void onUninitialized() override {
        video_sender_ = nullptr;
    }

private:
    bool running_ = false;

    void PlayVideo() {
        running_ = true;

        // Open video file with OpenCV
        cv::VideoCapture cap(video_source_);
        if (!cap.isOpened()) {
            std::cerr << "Failed to open video: " << video_source_ << std::endl;
            return;
        }

        while (running_ && video_sender_) {
            cv::Mat frame;
            if (!cap.read(frame)) {
                cap.set(cv::CAP_PROP_POS_FRAMES, 0);  // Loop video
                continue;
            }

            // Convert BGR to YUV420 (I420)
            cv::Mat yuv;
            cv::cvtColor(frame, yuv, cv::COLOR_BGR2YUV_I420);

            // Send frame
            char* buffer = (char*)yuv.data;
            int width = frame.cols;
            int height = frame.rows;
            int frameLen = yuv.total() * yuv.elemSize();

            SDKError err = video_sender_->sendVideoFrame(buffer, width, height, frameLen, 0);
            if (err != SDKERR_SUCCESS) {
                std::cerr << "sendVideoFrame failed: " << err << std::endl;
            }

            // Control framerate (e.g., 30fps = 33ms per frame)
            std::this_thread::sleep_for(std::chrono::milliseconds(33));
        }
    }
};
```

### Register Virtual Camera

```cpp
// Create your video source
ZoomSDKVideoSource* videoSource = new ZoomSDKVideoSource("my_video.mp4");

// Get the raw data helper
IZoomSDKVideoSourceHelper* videoSourceHelper = GetRawdataVideoSourceHelper();

// Set as external video source
videoSourceHelper->setExternalVideoSource(videoSource);

// Join meeting - your video will be the "camera"
meetingService->Join(joinParam);
```

### Frame Format: YUV420 (I420)

```
YUV420 Layout (1920x1080 example):
┌────────────────────────┐
│         Y plane        │  1920 x 1080 = 2,073,600 bytes
│      (luminance)       │
├────────────────────────┤
│    U plane (Cb)        │  960 x 540 = 518,400 bytes
├────────────────────────┤
│    V plane (Cr)        │  960 x 540 = 518,400 bytes
└────────────────────────┘
Total: width * height * 1.5 = 3,110,400 bytes
```

---

## Send Audio (Virtual Microphone)

### Interface: IZoomSDKVirtualAudioMicEvent

```cpp
#include <rawdata/rawdata_audio_helper_interface.h>

class ZoomSDKVirtualAudioMic : public IZoomSDKVirtualAudioMicEvent {
private:
    IZoomSDKAudioRawDataSender* audio_sender_ = nullptr;
    string audio_source_;
    bool running_ = false;

public:
    ZoomSDKVirtualAudioMic(string audio_source) : audio_source_(audio_source) {}

    void onMicInitialize(IZoomSDKAudioRawDataSender* pSender) override {
        audio_sender_ = pSender;
        std::cout << "Virtual mic initialized" << std::endl;
    }

    void onMicStartSend() override {
        // SDK is ready - start sending audio
        std::thread([this]() { PlayAudio(); }).detach();
    }

    void onMicStopSend() override {
        running_ = false;
    }

    void onMicUninitialized() override {
        audio_sender_ = nullptr;
    }

private:
    void PlayAudio() {
        running_ = true;

        // Open WAV file
        std::ifstream file(audio_source_, std::ios::binary);
        if (!file.is_open()) {
            std::cerr << "Failed to open audio: " << audio_source_ << std::endl;
            return;
        }

        // Skip WAV header (44 bytes for standard WAV)
        file.seekg(44, std::ios::beg);

        // Audio parameters (must match your WAV file!)
        const int sampleRate = 48000;  // 48kHz
        const size_t chunkSize = 640;  // Send in 640-byte chunks

        std::vector<char> buffer(chunkSize);

        while (running_ && audio_sender_ && file.good()) {
            file.read(buffer.data(), chunkSize);
            std::streamsize bytesRead = file.gcount();

            if (bytesRead > 0) {
                // Send audio chunk
                SDKError err = audio_sender_->send(
                    buffer.data(),
                    bytesRead,
                    sampleRate,
                    ZoomSDKAudioChannel_Mono  // or ZoomSDKAudioChannel_Stereo
                );

                if (err != SDKERR_SUCCESS) {
                    std::cerr << "send audio failed: " << err << std::endl;
                }
            }

            // Control timing based on sample rate and chunk size
            // 640 bytes / 2 (16-bit) / 48000 Hz = ~6.67ms
            std::this_thread::sleep_for(std::chrono::microseconds(6667));
        }

        file.close();
    }
};
```

### Register Virtual Microphone

```cpp
// Create your audio source
ZoomSDKVirtualAudioMic* virtualMic = new ZoomSDKVirtualAudioMic("my_audio.wav");

// Get audio helper
IZoomSDKAudioRawDataHelper* audioHelper = GetAudioRawdataHelper();

// Set as virtual mic
audioHelper->setExternalAudioSource(virtualMic);

// Join meeting - your audio will be the "microphone"
meetingService->Join(joinParam);
```

### Audio Format: PCM 16-bit

```
Required format:
- Encoding: PCM (signed 16-bit little-endian)
- Sample rates: 8000, 16000, 32000, 44100, or 48000 Hz
- Channels: Mono (1) or Stereo (2)

WAV File Structure:
┌──────────────────┐
│  RIFF Header     │  44 bytes (skip this)
├──────────────────┤
│  Audio Data      │  PCM samples
│  (16-bit signed) │
└──────────────────┘
```

---

## Send Share Screen (Virtual Share)

### Interface: IZoomSDKShareSource

```cpp
#include <rawdata/rawdata_share_source_helper_interface.h>

class ZoomSDKShareSource : public IZoomSDKShareSource {
private:
    IZoomSDKShareSender* share_sender_ = nullptr;

public:
    void onShareSendStarted(IZoomSDKShareSender* pSender) override {
        share_sender_ = pSender;
        std::thread([this]() { SendShareFrames(); }).detach();
    }

    void onShareSendStopped() override {
        share_sender_ = nullptr;
    }

private:
    void SendShareFrames() {
        while (share_sender_) {
            // Capture or generate your share content
            cv::Mat frame = CaptureMyContent();

            // Convert to YUV420
            cv::Mat yuv;
            cv::cvtColor(frame, yuv, cv::COLOR_BGR2YUV_I420);

            char* buffer = (char*)yuv.data;
            int width = frame.cols;
            int height = frame.rows;
            int frameLen = yuv.total() * yuv.elemSize();

            share_sender_->sendShareFrame(buffer, width, height, frameLen);

            std::this_thread::sleep_for(std::chrono::milliseconds(33));
        }
    }
};
```

### Start Virtual Share

```cpp
// Get share helper
IMeetingShareController* shareCtrl = meetingService->GetMeetingShareController();

// Create share source
ZoomSDKShareSource* shareSource = new ZoomSDKShareSource();

// Start sharing with your source
shareCtrl->StartShareWithPreviewEnabled(shareSource);
```

---

## Complete Example: Video Bot

```cpp
#include <windows.h>
#include <zoom_sdk.h>
#include <meeting_service_interface.h>
#include <rawdata/rawdata_video_source_helper_interface.h>
#include <opencv2/opencv.hpp>
#include <thread>

using namespace ZOOMSDK;

// Global references
IMeetingService* meetingService = nullptr;
IAuthService* authService = nullptr;
ZoomSDKVideoSource* videoSource = nullptr;

void onInMeeting() {
    std::cout << "In meeting - video source active!" << std::endl;
}

void JoinMeeting() {
    CreateMeetingService(&meetingService);

    // Create video source BEFORE joining
    videoSource = new ZoomSDKVideoSource("Big_Buck_Bunny.mp4");
    IZoomSDKVideoSourceHelper* helper = GetRawdataVideoSourceHelper();
    helper->setExternalVideoSource(videoSource);

    // Configure join parameters
    JoinParam joinParam;
    joinParam.userType = SDK_UT_WITHOUT_LOGIN;

    JoinParam4WithoutLogin& params = joinParam.param.withoutloginuserJoin;
    params.meetingNumber = 1234567890;
    params.psw = L"password";
    params.userName = L"Video Bot";
    params.isVideoOff = false;  // Video ON to use virtual camera
    params.isAudioOff = true;

    meetingService->SetEvent(new MeetingServiceEventListener(&onInMeeting));
    meetingService->Join(joinParam);
}

void SDKAuth() {
    CreateAuthService(&authService);
    authService->SetEvent(new AuthServiceEventListener(&JoinMeeting));

    AuthContext ctx;
    ctx.jwt_token = L"your_jwt_token";
    authService->SDKAuth(ctx);
}

int main() {
    // Initialize
    InitParam initParam;
    initParam.strWebDomain = L"https://zoom.us";
    InitSDK(initParam);

    // Start auth flow
    SDKAuth();

    // Message loop
    MSG msg;
    while (GetMessage(&msg, nullptr, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Cleanup
    CleanUPSDK();
    return 0;
}
```

---

## Key Patterns

### 1. Threading is Required

Sending frames in callbacks will block the SDK. Always use a separate thread:

```cpp
void onStartSend() override {
    std::thread([this]() { SendFrames(); }).detach();
}
```

### 2. Match Frame Rate to Network

The SDK suggests resolution/framerate in `onPropertyChange`. Respect these suggestions:

```cpp
void onPropertyChange(IList<VideoSourceCapability>* caps, VideoSourceCapability suggest) override {
    target_width_ = suggest.width;
    target_height_ = suggest.height;
    target_fps_ = suggest.frame;
}
```

### 3. Handle Stop/Restart Gracefully

```cpp
void onStopSend() override {
    running_ = false;  // Signal thread to stop
}

void onStartSend() override {
    running_ = true;   // Signal thread to start
    std::thread([this]() { SendLoop(); }).detach();
}
```

### 4. YUV420 Conversion

Using OpenCV:
```cpp
cv::Mat yuv;
cv::cvtColor(bgrFrame, yuv, cv::COLOR_BGR2YUV_I420);
```

Manual conversion:
```cpp
// Y = 0.299*R + 0.587*G + 0.114*B
// U = -0.169*R - 0.331*G + 0.500*B + 128
// V = 0.500*R - 0.419*G - 0.081*B + 128
```

---

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No video showing | `isVideoOff = true` in join params | Set `isVideoOff = false` |
| Frames not sending | Blocking in callback | Use separate thread |
| Wrong colors | BGR instead of YUV | Convert to YUV420 |
| Choppy video | Wrong timing | Match suggested FPS |
| Audio glitches | Wrong sample rate | Use 48000 Hz |
| Audio silent | Wrong chunk size | Use 640 byte chunks |

---

## Related Documentation

- [Raw Video Capture](raw-video-capture.md) - Receiving video (opposite direction)
- [SDK Architecture Pattern](../concepts/sdk-architecture-pattern.md) - Universal 3-step pattern
- [Authentication Pattern](authentication-pattern.md) - Complete auth workflow

---

## Sample Projects

Local samples demonstrating these concepts:
- `C:\tempsdk\zoom_meetingsdk_windows_rawdatademos\SendVideoRawData\`
- `C:\tempsdk\zoom_meetingsdk_windows_rawdatademos\SendAudioRawData\`
- `C:\tempsdk\zoom_meetingsdk_windows_rawdatademos\SendShareScreenRawData\`
