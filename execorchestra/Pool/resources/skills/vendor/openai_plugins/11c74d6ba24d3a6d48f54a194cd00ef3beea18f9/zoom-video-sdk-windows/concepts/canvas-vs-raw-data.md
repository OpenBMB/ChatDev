# Canvas API vs Raw Data Pipe

## The Two Rendering Paths

The Zoom Video SDK provides **two distinct ways** to render video. Your choice affects quality, performance, and capabilities.

```
┌─────────────────────────────────────────────────────────────────┐
│                     RENDERING DECISION                          │
├─────────────────────────────────────────────────────────────────┤
│  Canvas API (SDK-Rendered)     │  Raw Data Pipe (Self-Rendered) │
│  ─────────────────────────────│──────────────────────────────── │
│  SDK renders to your HWND      │  You receive YUV420 frames     │
│  Best quality, zero effort     │  Full control, more work       │
│  Standard video apps           │  AI, effects, recording        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Decision Guide

| Use Case | Recommended Approach |
|----------|---------------------|
| Standard video conferencing UI | **Canvas API** |
| Video grid/gallery layout | **Canvas API** |
| Simple video display | **Canvas API** |
| Custom video effects/filters | Raw Data Pipe |
| AI/ML video processing | Raw Data Pipe |
| Custom recording format | Raw Data Pipe |
| Video compositing | Raw Data Pipe |

**Default recommendation: Canvas API** unless you need frame-level access.

---

## Canvas API (SDK-Rendered)

### How It Works

```
IZoomVideoSDKUser
    └── GetVideoCanvas()
        └── IZoomVideoSDKCanvas
            └── subscribeWithView(HWND, aspect, resolution)
                └── SDK renders directly to your window
                    └── Hardware-accelerated, optimized
```

### Code Example

```cpp
// Get user's canvas
IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();

// Subscribe - SDK renders to your window
ZoomVideoSDKErrors err = canvas->subscribeWithView(
    hwnd,                                    // Your window handle
    ZoomVideoSDKVideoAspect_PanAndScan,     // Aspect ratio handling
    ZoomVideoSDKResolution_Auto              // Let SDK choose
);

if (err == ZoomVideoSDKErrors_Success) {
    // Done! SDK is now rendering to your window
}

// To stop
canvas->unSubscribeWithView(hwnd);
```

### Aspect Ratio Options

| Option | Behavior |
|--------|----------|
| `ZoomVideoSDKVideoAspect_Original` | Letterbox/pillarbox, no cropping |
| `ZoomVideoSDKVideoAspect_FullFilled` | Fill window, may crop edges |
| `ZoomVideoSDKVideoAspect_PanAndScan` | Smart crop to fill window |
| `ZoomVideoSDKVideoAspect_LetterBox` | Show full video with black bars |

### Resolution Options

| Option | Resolution |
|--------|------------|
| `ZoomVideoSDKResolution_90P` | 160x90 |
| `ZoomVideoSDKResolution_180P` | 320x180 |
| `ZoomVideoSDKResolution_360P` | 640x360 |
| `ZoomVideoSDKResolution_720P` | 1280x720 |
| `ZoomVideoSDKResolution_1080P` | 1920x1080 |
| `ZoomVideoSDKResolution_Auto` | SDK chooses (recommended) |

### Advantages

- **Best quality** - Hardware-accelerated rendering
- **No artifacts** - Professional video quality
- **Simple code** - 3 lines to subscribe
- **Better performance** - No CPU-intensive YUV conversion
- **Automatic scaling** - SDK handles window resizing
- **Aspect ratio** - Built-in handling

### Disadvantages

- No access to raw frames
- Can't apply custom effects
- Can't process video for AI/ML

---

## Raw Data Pipe (Self-Rendered)

### How It Works

```
IZoomVideoSDKUser
    └── GetVideoPipe()
        └── IZoomVideoSDKRawDataPipe
            └── subscribe(resolution, delegate)
                └── Your IZoomVideoSDKRawDataPipeDelegate
                    └── onRawDataFrameReceived(YUVRawDataI420*)
                        └── You convert YUV→RGB and render
```

### Code Example

```cpp
// Implement delegate to receive frames
class VideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
public:
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        if (!data) return;

        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        char* yBuffer = data->GetYBuffer();
        char* uBuffer = data->GetUBuffer();
        char* vBuffer = data->GetVBuffer();

        // Convert YUV420 to RGB
        ConvertYUVToRGB(yBuffer, uBuffer, vBuffer, width, height);

        // Render to window (GDI, DirectX, OpenGL, etc.)
        RenderToWindow(rgbBuffer, width, height);
    }

    void onRawDataStatusChanged(RawDataStatus status) override {
        if (status == RawData_On) {
            std::cout << "Video started" << std::endl;
        } else {
            std::cout << "Video stopped" << std::endl;
        }
    }
};

// Subscribe to raw frames
IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
VideoRenderer* renderer = new VideoRenderer();
pipe->subscribe(ZoomVideoSDKResolution_720P, renderer);

// To stop
pipe->unSubscribe(renderer);
```

### YUV420 to RGB Conversion

```cpp
void ConvertYUV420ToRGB(char* yBuffer, char* uBuffer, char* vBuffer,
                        int width, int height, unsigned char* rgbBuffer) {
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
            rgbBuffer[yIndex * 3 + 0] = (unsigned char)B;
            rgbBuffer[yIndex * 3 + 1] = (unsigned char)G;
            rgbBuffer[yIndex * 3 + 2] = (unsigned char)R;
        }
    }
}
```

### GDI Rendering

```cpp
void RenderToWindow(unsigned char* rgbBuffer, int width, int height, HWND hwnd) {
    HDC hdc = GetDC(hwnd);

    BITMAPINFO bmi = {};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = width;
    bmi.bmiHeader.biHeight = -height;  // Negative for top-down
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 24;
    bmi.bmiHeader.biCompression = BI_RGB;

    RECT rect;
    GetClientRect(hwnd, &rect);

    StretchDIBits(hdc,
        0, 0, rect.right, rect.bottom,  // Destination
        0, 0, width, height,             // Source
        rgbBuffer, &bmi,
        DIB_RGB_COLORS, SRCCOPY);

    ReleaseDC(hwnd, hdc);
}
```

### Advantages

- Full access to raw YUV frames
- Can apply custom video effects
- Can process for AI/ML
- Can record to custom formats
- Can composite multiple streams

### Disadvantages

- **CPU intensive** - YUV conversion can cause frame drops
- **Artifacts** - Manual rendering may show tearing
- **Complex** - More code to maintain
- **Performance** - Slower than Canvas API

---

## Comparison Table

| Aspect | Canvas API | Raw Data Pipe |
|--------|------------|---------------|
| **Complexity** | 3 lines of code | 50+ lines of code |
| **Performance** | Hardware-accelerated | CPU-bound |
| **Quality** | Professional | Depends on implementation |
| **Frame Access** | No | Yes (YUV420) |
| **Custom Effects** | No | Yes |
| **AI Processing** | No | Yes |
| **Recording** | No | Yes |
| **Recommended For** | Standard apps | Advanced processing |

---

## Hybrid Approach

You can use **both** simultaneously:

```cpp
// Use Canvas for display
user->GetVideoCanvas()->subscribeWithView(displayHwnd, aspect, resolution);

// Use Raw Data for processing (different delegate)
user->GetVideoPipe()->subscribe(ZoomVideoSDKResolution_360P, processingDelegate);
```

**Tip**: Use lower resolution for processing to reduce CPU load.

---

## Performance Considerations

### Canvas API
- Zero CPU overhead for rendering
- SDK handles all optimization
- Scales automatically with window resize

### Raw Data Pipe
- YUV conversion: ~5-10ms per frame at 720p
- Memory allocation: Consider pre-allocated buffers
- Threading: Move conversion off UI thread
- Frame drops: Expect some at high resolutions

### Optimization Tips for Raw Data

```cpp
// Pre-allocate buffers
class OptimizedRenderer : public IZoomVideoSDKRawDataPipeDelegate {
    unsigned char* rgbBuffer = nullptr;
    int bufferWidth = 0;
    int bufferHeight = 0;

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int w = data->GetStreamWidth();
        int h = data->GetStreamHeight();

        // Reallocate only if resolution changed
        if (w != bufferWidth || h != bufferHeight) {
            delete[] rgbBuffer;
            rgbBuffer = new unsigned char[w * h * 3];
            bufferWidth = w;
            bufferHeight = h;
        }

        // Convert and render
        ConvertYUV420ToRGB(..., rgbBuffer);
        RenderToWindow(rgbBuffer, w, h);
    }
};
```

---

## Related Documentation

- [Video Rendering Example](../examples/video-rendering.md) - Canvas API code
- [Raw Video Capture Example](../examples/raw-video-capture.md) - Raw Data code
- [Singleton Hierarchy](singleton-hierarchy.md) - Canvas/Pipe navigation
- [API Reference](../references/windows-reference.md) - Method details

---

**TL;DR**: Use Canvas API for standard video display. Use Raw Data Pipe only when you need frame-level access for AI, effects, or custom recording.
