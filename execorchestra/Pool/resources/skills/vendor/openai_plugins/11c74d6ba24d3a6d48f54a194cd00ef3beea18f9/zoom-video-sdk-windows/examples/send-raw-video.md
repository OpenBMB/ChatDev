# Send Raw Video

Complete working code for sending custom video as a virtual camera.

**Official Sample**: `VSDK_sendRawVideo` in [videosdk-windows-rawdata-sample](https://github.com/zoom/videosdk-windows-rawdata-sample)

---

## Overview

Inject custom video frames into your session. Use cases:
- Virtual camera with custom content
- Video filters/effects
- Pre-recorded video playback
- Computer-generated graphics

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIDEO INJECTION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│  Your Video Source (file, camera, generated)                    │
│       ↓                                                         │
│  Convert to YUV420 (I420)                                       │
│       ↓                                                         │
│  IZoomVideoSDKVideoSource::onInitialize()                       │
│       ↓                                                         │
│  IZoomVideoSDKVideoSender::sendVideoFrame()                     │
│       ↓                                                         │
│  Participants see your custom video                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Video Format Requirements

| Property | Value |
|----------|-------|
| Format | YUV420 (I420) planar |
| Color Space | YUV (not RGB) |
| Supported Resolutions | 90p, 180p, 360p, 720p, 1080p |
| Frame Rate | Up to 30 fps |

---

## Complete Working Code

### VideoSource.h

```cpp
#pragma once
#include <windows.h>
#include <thread>
#include <atomic>
#include "zoom_video_sdk_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

class VideoSource : public IZoomVideoSDKVideoSource {
public:
    VideoSource();
    ~VideoSource();

    // IZoomVideoSDKVideoSource interface
    void onInitialize(IZoomVideoSDKVideoSender* sender,
                      IVideoSDKVector<VideoSourceCapability>* support_cap_list,
                      VideoSourceCapability& suggest_cap) override;
    void onPropertyChange(IVideoSDKVector<VideoSourceCapability>* support_cap_list,
                          VideoSourceCapability suggest_cap) override;
    void onStartSend() override;
    void onStopSend() override;
    void onUninitialized() override;

private:
    void SendLoop();
    void GenerateTestFrame(char* yBuffer, char* uBuffer, char* vBuffer,
                           int width, int height, int frameNum);

    IZoomVideoSDKVideoSender* m_sender;
    std::thread m_sendThread;
    std::atomic<bool> m_sending;
    int m_width;
    int m_height;
    int m_fps;
};
```

### VideoSource.cpp

```cpp
#include "VideoSource.h"
#include <iostream>
#include <chrono>

VideoSource::VideoSource()
    : m_sender(nullptr)
    , m_sending(false)
    , m_width(1280)
    , m_height(720)
    , m_fps(30) {
}

VideoSource::~VideoSource() {
    m_sending = false;
    if (m_sendThread.joinable()) {
        m_sendThread.join();
    }
}

void VideoSource::onInitialize(IZoomVideoSDKVideoSender* sender,
                                IVideoSDKVector<VideoSourceCapability>* support_cap_list,
                                VideoSourceCapability& suggest_cap) {
    std::cout << "VideoSource initialized" << std::endl;
    m_sender = sender;

    // Use suggested capability
    m_width = suggest_cap.width;
    m_height = suggest_cap.height;
    m_fps = suggest_cap.frame;

    std::cout << "Resolution: " << m_width << "x" << m_height
              << " @ " << m_fps << " fps" << std::endl;
}

void VideoSource::onPropertyChange(IVideoSDKVector<VideoSourceCapability>* support_cap_list,
                                    VideoSourceCapability suggest_cap) {
    std::cout << "Property changed: " << suggest_cap.width << "x"
              << suggest_cap.height << std::endl;
    m_width = suggest_cap.width;
    m_height = suggest_cap.height;
    m_fps = suggest_cap.frame;
}

void VideoSource::onStartSend() {
    std::cout << "Start sending video" << std::endl;
    m_sending = true;
    m_sendThread = std::thread(&VideoSource::SendLoop, this);
}

void VideoSource::onStopSend() {
    std::cout << "Stop sending video" << std::endl;
    m_sending = false;
    if (m_sendThread.joinable()) {
        m_sendThread.join();
    }
}

void VideoSource::onUninitialized() {
    std::cout << "VideoSource uninitialized" << std::endl;
    m_sender = nullptr;
}

void VideoSource::SendLoop() {
    int frameNum = 0;
    auto frameInterval = std::chrono::milliseconds(1000 / m_fps);

    // Allocate YUV buffers
    size_t ySize = m_width * m_height;
    size_t uvSize = ySize / 4;

    char* yBuffer = new char[ySize];
    char* uBuffer = new char[uvSize];
    char* vBuffer = new char[uvSize];

    while (m_sending && m_sender) {
        auto startTime = std::chrono::steady_clock::now();

        // Generate or load frame
        GenerateTestFrame(yBuffer, uBuffer, vBuffer, m_width, m_height, frameNum);

        // Send frame
        ZoomVideoSDKErrors err = m_sender->sendVideoFrame(
            yBuffer,
            uBuffer,
            vBuffer,
            m_width,
            m_height,
            ySize,
            0  // rotation
        );

        if (err != ZoomVideoSDKErrors_Success) {
            std::cout << "sendVideoFrame error: " << err << std::endl;
        }

        frameNum++;

        // Maintain frame rate
        auto elapsed = std::chrono::steady_clock::now() - startTime;
        auto sleepTime = frameInterval - elapsed;
        if (sleepTime.count() > 0) {
            std::this_thread::sleep_for(sleepTime);
        }
    }

    delete[] yBuffer;
    delete[] uBuffer;
    delete[] vBuffer;

    std::cout << "Sent " << frameNum << " frames" << std::endl;
}

void VideoSource::GenerateTestFrame(char* yBuffer, char* uBuffer, char* vBuffer,
                                     int width, int height, int frameNum) {
    // Generate a simple color gradient that changes over time
    int colorShift = frameNum % 256;

    // Y plane (brightness)
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            // Gradient pattern
            int brightness = ((x + colorShift) % 256);
            yBuffer[y * width + x] = (char)brightness;
        }
    }

    // U and V planes (color)
    int uvWidth = width / 2;
    int uvHeight = height / 2;

    for (int y = 0; y < uvHeight; y++) {
        for (int x = 0; x < uvWidth; x++) {
            int index = y * uvWidth + x;
            uBuffer[index] = (char)(128 + (colorShift / 2));  // Blue tint
            vBuffer[index] = (char)(128 - (colorShift / 2));  // Red tint
        }
    }
}
```

### Registering the Video Source

```cpp
void StartVirtualCamera() {
    IZoomVideoSDKVideoHelper* videoHelper = sdk->getVideoHelper();
    if (!videoHelper) return;

    // Create and set video source
    VideoSource* videoSource = new VideoSource();

    ZoomVideoSDKErrors err = videoHelper->setExternalVideoSource(videoSource);
    if (err != ZoomVideoSDKErrors_Success) {
        std::cout << "setExternalVideoSource failed: " << err << std::endl;
        return;
    }

    // Start video (this triggers onStartSend)
    videoHelper->startVideo();
}

void StopVirtualCamera() {
    IZoomVideoSDKVideoHelper* videoHelper = sdk->getVideoHelper();
    if (videoHelper) {
        videoHelper->stopVideo();
    }
}
```

---

## Loading Video from File

### Read YUV File

```cpp
bool LoadYUVFrame(const std::string& filename, int frameIndex,
                  char* yBuffer, char* uBuffer, char* vBuffer,
                  int width, int height) {
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) return false;

    size_t ySize = width * height;
    size_t uvSize = ySize / 4;
    size_t frameSize = ySize + uvSize * 2;

    // Seek to frame
    file.seekg(frameIndex * frameSize);

    // Read YUV planes
    file.read(yBuffer, ySize);
    file.read(uBuffer, uvSize);
    file.read(vBuffer, uvSize);

    return file.good();
}
```

### Convert RGB to YUV

```cpp
void RGBToYUV420(unsigned char* rgb, char* yBuffer, char* uBuffer, char* vBuffer,
                  int width, int height) {
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int rgbIndex = (y * width + x) * 3;
            int R = rgb[rgbIndex + 2];  // BGR order
            int G = rgb[rgbIndex + 1];
            int B = rgb[rgbIndex + 0];

            // RGB to YUV conversion (BT.601)
            int Y = ((66 * R + 129 * G + 25 * B + 128) >> 8) + 16;

            yBuffer[y * width + x] = (char)Y;

            // U and V at quarter resolution
            if (y % 2 == 0 && x % 2 == 0) {
                int uvIndex = (y / 2) * (width / 2) + (x / 2);
                int U = ((-38 * R - 74 * G + 112 * B + 128) >> 8) + 128;
                int V = ((112 * R - 94 * G - 18 * B + 128) >> 8) + 128;

                uBuffer[uvIndex] = (char)U;
                vBuffer[uvIndex] = (char)V;
            }
        }
    }
}
```

---

## sendVideoFrame Parameters

```cpp
ZoomVideoSDKErrors sendVideoFrame(
    char* frameBuffer,     // Y plane or full frame
    char* uBuffer,         // U plane (can be nullptr for NV12)
    char* vBuffer,         // V plane (can be nullptr for NV12)
    int width,             // Frame width
    int height,            // Frame height
    int frameLength,       // Y plane size (width * height)
    int rotation           // 0, 90, 180, 270
);
```

---

## Common Issues

### Video Not Showing

**Cause**: Not calling `startVideo()` after setting source

**Fix**:
```cpp
videoHelper->setExternalVideoSource(source);
videoHelper->startVideo();  // Required!
```

### Frame Rate Too Low

**Cause**: Frame generation slower than frame rate

**Fix**: Optimize frame generation or reduce resolution

### Color Looks Wrong

**Cause**: RGB/BGR order mismatch or wrong YUV conversion

**Fix**: Verify color space conversion formula

---

## Related Documentation

- [Raw Video Capture](raw-video-capture.md) - Capture video
- [Send Raw Audio](send-raw-audio.md) - Audio injection
- [Canvas vs Raw Data](../concepts/canvas-vs-raw-data.md) - Rendering approaches
- [API Reference](../references/windows-reference.md) - Method signatures
