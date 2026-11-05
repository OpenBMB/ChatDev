# Raw Video Capture

Complete working code for capturing raw YUV420 video frames for custom processing.

## Overview

Use Raw Data Pipe when you need frame-level access for:
- AI/ML video processing
- Custom video effects
- Recording to custom formats
- Video compositing

```
┌─────────────────────────────────────────────────────────────────┐
│                    RAW DATA FLOW                                │
├─────────────────────────────────────────────────────────────────┤
│  GetVideoPipe() → subscribe(resolution, delegate)               │
│       ↓                                                         │
│  onRawDataFrameReceived(YUVRawDataI420*)                        │
│       ↓                                                         │
│  Process: GetYBuffer(), GetUBuffer(), GetVBuffer()              │
└─────────────────────────────────────────────────────────────────┘
```

---

## YUV420 Format Explained

### Memory Layout (I420 Planar)

```
┌─────────────────────────────────────────┐
│  Y Plane (Luminance/Brightness)         │  width × height bytes
│  Full resolution                        │
├─────────────────────────────────────────┤
│  U Plane (Blue-difference Chrominance)  │  (width/2) × (height/2) bytes
│  Quarter resolution                     │
├─────────────────────────────────────────┤
│  V Plane (Red-difference Chrominance)   │  (width/2) × (height/2) bytes
│  Quarter resolution                     │
└─────────────────────────────────────────┘

Total size = width × height × 1.5 bytes
Example: 1280×720 = 1,382,400 bytes (~1.3 MB per frame)
```

### Buffer Sizes

| Resolution | Y Buffer | U Buffer | V Buffer | Total |
|------------|----------|----------|----------|-------|
| 720p (1280×720) | 921,600 | 230,400 | 230,400 | 1,382,400 |
| 1080p (1920×1080) | 2,073,600 | 518,400 | 518,400 | 3,110,400 |
| 360p (640×360) | 230,400 | 57,600 | 57,600 | 345,600 |

---

## Complete Working Code

### RawVideoCapture.h

```cpp
#pragma once
#include <windows.h>
#include <fstream>
#include <string>
#include <mutex>
#include "zoom_video_sdk_interface.h"
#include "zoom_sdk_raw_data_def.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

class RawVideoCapture : public IZoomVideoSDKRawDataPipeDelegate {
public:
    RawVideoCapture(const std::string& outputPath);
    ~RawVideoCapture();

    // IZoomVideoSDKRawDataPipeDelegate
    void onRawDataFrameReceived(YUVRawDataI420* data) override;
    void onRawDataStatusChanged(RawDataStatus status) override;

    // Statistics
    int GetFrameCount() const { return m_frameCount; }
    int GetWidth() const { return m_width; }
    int GetHeight() const { return m_height; }

private:
    std::ofstream m_outputFile;
    std::mutex m_mutex;
    int m_frameCount;
    int m_width;
    int m_height;
    std::string m_outputPath;
};
```

### RawVideoCapture.cpp

```cpp
#include "RawVideoCapture.h"
#include <iostream>

RawVideoCapture::RawVideoCapture(const std::string& outputPath)
    : m_outputPath(outputPath)
    , m_frameCount(0)
    , m_width(0)
    , m_height(0) {

    m_outputFile.open(outputPath, std::ios::binary);
    if (!m_outputFile.is_open()) {
        std::cerr << "Failed to open output file: " << outputPath << std::endl;
    }
}

RawVideoCapture::~RawVideoCapture() {
    std::lock_guard<std::mutex> lock(m_mutex);
    if (m_outputFile.is_open()) {
        m_outputFile.close();
    }
    std::cout << "Captured " << m_frameCount << " frames" << std::endl;
}

void RawVideoCapture::onRawDataFrameReceived(YUVRawDataI420* data) {
    if (!data) return;

    std::lock_guard<std::mutex> lock(m_mutex);

    int width = data->GetStreamWidth();
    int height = data->GetStreamHeight();

    // Detect resolution change
    if (width != m_width || height != m_height) {
        std::cout << "Resolution: " << width << "x" << height << std::endl;
        m_width = width;
        m_height = height;
    }

    // Calculate buffer sizes
    size_t ySize = width * height;
    size_t uvSize = ySize / 4;  // Quarter resolution

    // Write YUV data to file
    if (m_outputFile.is_open()) {
        m_outputFile.write(data->GetYBuffer(), ySize);
        m_outputFile.write(data->GetUBuffer(), uvSize);
        m_outputFile.write(data->GetVBuffer(), uvSize);
    }

    m_frameCount++;

    // Log progress every 100 frames
    if (m_frameCount % 100 == 0) {
        std::cout << "Captured " << m_frameCount << " frames" << std::endl;
    }
}

void RawVideoCapture::onRawDataStatusChanged(RawDataStatus status) {
    if (status == RawData_On) {
        std::cout << "Raw data started" << std::endl;
    } else {
        std::cout << "Raw data stopped" << std::endl;
    }
}
```

### Using in Delegate

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
private:
    IZoomVideoSDK* m_sdk;
    std::map<IZoomVideoSDKUser*, RawVideoCapture*> m_captures;
    std::map<IZoomVideoSDKUser*, IZoomVideoSDKRawDataPipe*> m_pipes;

public:
    MyDelegate(IZoomVideoSDK* sdk) : m_sdk(sdk) {}

    ~MyDelegate() {
        // Cleanup all captures
        for (auto& pair : m_captures) {
            delete pair.second;
        }
    }

    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                                   IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        IZoomVideoSDKUser* myself = m_sdk->getSessionInfo()->getMyself();

        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);

            ZoomVideoSDKVideoStatus status = user->GetVideoPipe()->getVideoStatus();

            if (status.isOn) {
                // Start capture if not already capturing
                if (m_captures.find(user) == m_captures.end()) {
                    StartCapture(user);
                }
            } else {
                // Stop capture
                StopCapture(user);
            }
        }
    }

    void StartCapture(IZoomVideoSDKUser* user) {
        // Create unique filename
        std::wstring name = user->getUserName();
        std::string filename = "video_" +
            std::string(name.begin(), name.end()) + ".yuv";

        // Create capture delegate
        RawVideoCapture* capture = new RawVideoCapture(filename);
        m_captures[user] = capture;

        // Subscribe to raw data
        IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
        if (pipe) {
            ZoomVideoSDKErrors err = pipe->subscribe(
                ZoomVideoSDKResolution_720P,
                capture
            );

            if (err == ZoomVideoSDKErrors_Success) {
                m_pipes[user] = pipe;
                std::wcout << L"Started capture for: " << user->getUserName() << std::endl;
            } else {
                std::wcout << L"Failed to subscribe: " << err << std::endl;
                delete capture;
                m_captures.erase(user);
            }
        }
    }

    void StopCapture(IZoomVideoSDKUser* user) {
        auto pipeIt = m_pipes.find(user);
        auto captureIt = m_captures.find(user);

        if (pipeIt != m_pipes.end() && captureIt != m_captures.end()) {
            pipeIt->second->unSubscribe(captureIt->second);
            delete captureIt->second;

            m_pipes.erase(pipeIt);
            m_captures.erase(captureIt);

            std::wcout << L"Stopped capture for: " << user->getUserName() << std::endl;
        }
    }

    void onUserLeave(IZoomVideoSDKUserHelper* helper,
                     IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        for (int i = 0; i < userList->GetCount(); i++) {
            StopCapture(userList->GetItem(i));
        }
    }

    // ... other callbacks
};
```

---

## Playing Raw YUV Files

Raw YUV files have no headers - you must specify format explicitly.

### Play with FFplay

```cmd
ffplay -video_size 1280x720 -pixel_format yuv420p -f rawvideo video.yuv
```

### Convert to MP4

```cmd
ffmpeg -video_size 1280x720 -pixel_format yuv420p -framerate 30 -f rawvideo -i video.yuv -c:v libx264 output.mp4
```

### Key FFmpeg Flags

| Flag | Description |
|------|-------------|
| `-video_size WxH` | Frame dimensions (must match!) |
| `-pixel_format yuv420p` | I420/YUV420 planar format |
| `-f rawvideo` | Raw video input (no container) |
| `-framerate 30` | Assumed frame rate |

---

## YUV to RGB Conversion

For real-time display, convert YUV420 to RGB:

```cpp
void ConvertYUV420ToRGB(YUVRawDataI420* data, unsigned char* rgbBuffer) {
    int width = data->GetStreamWidth();
    int height = data->GetStreamHeight();

    char* yBuffer = data->GetYBuffer();
    char* uBuffer = data->GetUBuffer();
    char* vBuffer = data->GetVBuffer();

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int yIndex = y * width + x;
            int uvIndex = (y / 2) * (width / 2) + (x / 2);

            int Y = (unsigned char)yBuffer[yIndex];
            int U = (unsigned char)uBuffer[uvIndex];
            int V = (unsigned char)vBuffer[uvIndex];

            // ITU-R BT.601 conversion
            int C = Y - 16;
            int D = U - 128;
            int E = V - 128;

            int R = (298 * C + 409 * E + 128) >> 8;
            int G = (298 * C - 100 * D - 208 * E + 128) >> 8;
            int B = (298 * C + 516 * D + 128) >> 8;

            // Clamp to [0, 255]
            R = (R < 0) ? 0 : (R > 255) ? 255 : R;
            G = (G < 0) ? 0 : (G > 255) ? 255 : G;
            B = (B < 0) ? 0 : (B > 255) ? 255 : B;

            // Store as BGR (Windows format)
            int rgbIndex = yIndex * 3;
            rgbBuffer[rgbIndex + 0] = (unsigned char)B;
            rgbBuffer[rgbIndex + 1] = (unsigned char)G;
            rgbBuffer[rgbIndex + 2] = (unsigned char)R;
        }
    }
}
```

---

## YUVRawDataI420 Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `GetYBuffer()` | `char*` | Y plane (luminance) |
| `GetUBuffer()` | `char*` | U plane (chrominance) |
| `GetVBuffer()` | `char*` | V plane (chrominance) |
| `GetStreamWidth()` | `unsigned int` | Frame width |
| `GetStreamHeight()` | `unsigned int` | Frame height |
| `GetRotation()` | `unsigned int` | 0, 90, 180, 270 |
| `GetTimeStamp()` | `unsigned long long` | Frame timestamp |
| `GetBufferLen()` | `unsigned int` | Total buffer size |
| `CanAddRef()` | `bool` | Can add reference? |
| `AddRef()` | `bool` | Add reference |
| `Release()` | `int` | Release reference |

---

## Performance Tips

### 1. Pre-allocate Buffers

```cpp
class OptimizedCapture : public IZoomVideoSDKRawDataPipeDelegate {
    unsigned char* m_rgbBuffer = nullptr;
    int m_bufferSize = 0;

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int size = data->GetStreamWidth() * data->GetStreamHeight() * 3;

        // Reallocate only if needed
        if (size != m_bufferSize) {
            delete[] m_rgbBuffer;
            m_rgbBuffer = new unsigned char[size];
            m_bufferSize = size;
        }

        // Process...
    }
};
```

### 2. Process on Separate Thread

```cpp
void onRawDataFrameReceived(YUVRawDataI420* data) override {
    // Add reference so frame survives after callback
    if (data->CanAddRef()) {
        data->AddRef();

        // Queue for processing thread
        m_frameQueue.push(data);
    }
}

// Processing thread
void ProcessingLoop() {
    while (m_running) {
        YUVRawDataI420* frame = m_frameQueue.pop();
        if (frame) {
            ProcessFrame(frame);
            frame->Release();  // Release when done
        }
    }
}
```

### 3. Use Lower Resolution for Processing

```cpp
// Subscribe at lower resolution for AI processing
pipe->subscribe(ZoomVideoSDKResolution_360P, aiDelegate);

// Subscribe at higher resolution for display (Canvas API)
user->GetVideoCanvas()->subscribeWithView(hwnd, aspect, ZoomVideoSDKResolution_720P);
```

---

## Related Documentation

- [Canvas vs Raw Data](../concepts/canvas-vs-raw-data.md) - Choose your approach
- [Video Rendering](video-rendering.md) - Canvas API (easier)
- [API Reference](../references/windows-reference.md) - Full method signatures

---

**TL;DR**: Subscribe via `GetVideoPipe()->subscribe(resolution, delegate)`, receive frames in `onRawDataFrameReceived()`, write Y/U/V buffers to file or convert to RGB.
