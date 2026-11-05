# Raw Data - The ONLY Rendering Option on Linux

## Linux vs Windows/Mac: Key Difference

**CRITICAL**: Unlike Windows and macOS, Linux SDK **does NOT have Canvas API**.

| Platform | Canvas API | Raw Data Pipe |
|----------|-----------|---------------|
| **Windows** | ✅ Yes (SDK renders to HWND) | ✅ Yes (YUV420 frames) |
| **macOS** | ✅ Yes (SDK renders to NSView) | ✅ Yes (YUV420 frames) |
| **Linux** | ❌ **NO** | ✅ **ONLY OPTION** (YUV420 frames) |

**What this means**: On Linux, you MUST use the Raw Data Pipe and implement your own rendering. There is no built-in rendering like on Windows/Mac.

---

## What is Raw Data?

Raw data is uncompressed, unprocessed media data:
- **Video**: YUV420 (I420) format - separate Y, U, V planes
- **Audio**: PCM 16-bit format - raw audio samples
- **Share**: YUV420 format (same as video)

### YUV420 (I420) Format

```
Y Plane (Luminance - full resolution):
[Y Y Y Y Y Y Y Y]
[Y Y Y Y Y Y Y Y]
[Y Y Y Y Y Y Y Y]
[Y Y Y Y Y Y Y Y]

U Plane (Chrominance - 1/4 resolution):
[U U U U]
[U U U U]

V Plane (Chrominance - 1/4 resolution):
[V V V V]
[V V V V]
```

**Why YUV420?**
- Efficient: 12 bits per pixel (vs 24 for RGB)
- Standard: Used by video codecs (H.264, VP8, VP9)
- Human vision: Less sensitive to color than brightness

### PCM Audio Format

```
PCM 16-bit Mono (32kHz):
Sample Rate: 32000 Hz
Bit Depth: 16 bits per sample
Channels: 1 (mono)
Buffer: char* array of signed 16-bit integers
```

---

## Raw Data Pipe Architecture

### Receive Pattern

```cpp
// 1. Implement delegate
class VideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
public:
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Receive YUV420 frame
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        char* yBuffer = data->GetYBuffer();
        char* uBuffer = data->GetUBuffer();
        char* vBuffer = data->GetVBuffer();

        // Convert YUV to RGB
        unsigned char* rgbBuffer = ConvertYUVToRGB(yBuffer, uBuffer, vBuffer, width, height);

        // Render with Qt/GTK/SDL/OpenGL
        RenderFrame(rgbBuffer, width, height);
    }

    void onRawDataStatusChanged(RawDataStatus status) override {
        if (status == RawData_On) {
            printf("Video started\n");
        } else {
            printf("Video stopped\n");
        }
    }
};

// 2. Subscribe to user's video
IZoomVideoSDKUser* user = /* from callback */;
IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
pipe->subscribe(ZoomVideoSDKResolution_720P, new VideoRenderer());
```

### Send Pattern (Virtual Devices)

```cpp
// 1. Implement virtual video source
class VirtualCamera : public IZoomVideoSDKVideoSource {
    IZoomVideoSDKVideoSender* sender_;

public:
    void onInitialize(IZoomVideoSDKVideoSender* sender,
                     IVideoSDKVector<VideoSourceCapability>* caps,
                     VideoSourceCapability& suggest) override {
        sender_ = sender;
    }

    void onStartSend() override {
        // Start sending frames
        while (sending_) {
            // Load or generate YUV420 frame
            char* yBuffer = /* Y plane */;
            char* uBuffer = /* U plane */;
            char* vBuffer = /* V plane */;

            sender_->sendVideoFrame(yBuffer, uBuffer, vBuffer,
                                   width, height, 0, rotation);

            std::this_thread::sleep_for(std::chrono::milliseconds(33));  // ~30 FPS
        }
    }

    void onStopSend() override {
        sending_ = false;
    }

    void onPropertyChange(...) override {}
    void onUninitialized() override { sender_ = nullptr; }

private:
    bool sending_ = false;
};

// 2. Set before joining
session_context.externalVideoSource = new VirtualCamera();
```

---

## YUV to RGB Conversion

**Required for rendering**: Most UI frameworks expect RGB/RGBA, not YUV.

### ITU-R BT.601 Formula

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

            // YUV to RGB conversion
            int C = Y - 16;
            int D = U - 128;
            int E = V - 128;

            int R = (298 * C + 409 * E + 128) >> 8;
            int G = (298 * C - 100 * D - 208 * E + 128) >> 8;
            int B = (298 * C + 516 * D + 128) >> 8;

            // Clamp to [0, 255]
            R = std::max(0, std::min(255, R));
            G = std::max(0, std::min(255, G));
            B = std::max(0, std::min(255, B));

            // Store RGB
            int rgbIndex = yIndex * 3;
            rgbBuffer[rgbIndex + 0] = (unsigned char)R;
            rgbBuffer[rgbIndex + 1] = (unsigned char)G;
            rgbBuffer[rgbIndex + 2] = (unsigned char)B;
        }
    }
}
```

### Optimized with libyuv (Recommended)

```cpp
#include <libyuv/convert.h>

void ConvertYUV420ToRGB(char* yBuffer, char* uBuffer, char* vBuffer,
                        int width, int height, unsigned char* rgbBuffer) {
    libyuv::I420ToRGB24(
        (const uint8_t*)yBuffer, width,
        (const uint8_t*)uBuffer, width / 2,
        (const uint8_t*)vBuffer, width / 2,
        rgbBuffer, width * 3,
        width, height
    );
}
```

**Install libyuv**:
```bash
sudo apt install -y libyuv-dev
```

---

## Rendering Options

### Option 1: Qt (Recommended for Cross-Platform)

```cpp
class QtVideoWidget : public QWidget, public IZoomVideoSDKRawDataPipeDelegate {
    Q_OBJECT

signals:
    void frameReceived(QImage frame);

public:
    QtVideoWidget(QWidget* parent = nullptr) : QWidget(parent) {
        connect(this, &QtVideoWidget::frameReceived,
                this, &QtVideoWidget::updateFrame);
    }

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        // Convert YUV to RGB
        unsigned char* rgbBuffer = new unsigned char[width * height * 3];
        ConvertYUV420ToRGB(data->GetYBuffer(), data->GetUBuffer(), data->GetVBuffer(),
                          width, height, rgbBuffer);

        // Create QImage (takes ownership of buffer)
        QImage img(rgbBuffer, width, height, width * 3, QImage::Format_RGB888,
                  [](void* ptr) { delete[] (unsigned char*)ptr; }, rgbBuffer);

        // Emit signal (thread-safe)
        emit frameReceived(img.copy());
    }

    void onRawDataStatusChanged(RawDataStatus status) override {}

private slots:
    void updateFrame(QImage img) {
        pixmap_ = QPixmap::fromImage(img);
        update();  // Trigger repaint
    }

protected:
    void paintEvent(QPaintEvent*) override {
        if (!pixmap_.isNull()) {
            QPainter painter(this);
            painter.drawPixmap(rect(), pixmap_);
        }
    }

private:
    QPixmap pixmap_;
};
```

### Option 2: GTK with Cairo

```cpp
class GtkVideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
public:
    GtkVideoRenderer(GtkWidget* drawingArea) : drawing_area_(drawingArea) {
        g_signal_connect(drawing_area_, "draw", G_CALLBACK(on_draw_static), this);
    }

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        // Allocate RGB buffer
        std::lock_guard<std::mutex> lock(mutex_);
        if (rgb_buffer_) delete[] rgb_buffer_;
        rgb_buffer_ = new unsigned char[width * height * 3];
        width_ = width;
        height_ = height;

        // Convert YUV to RGB
        ConvertYUV420ToRGB(data->GetYBuffer(), data->GetUBuffer(), data->GetVBuffer(),
                          width, height, rgb_buffer_);

        // Trigger redraw on main thread
        g_idle_add([](gpointer user_data) {
            gtk_widget_queue_draw((GtkWidget*)user_data);
            return G_SOURCE_REMOVE;
        }, drawing_area_);
    }

    void onRawDataStatusChanged(RawDataStatus status) override {}

private:
    static gboolean on_draw_static(GtkWidget* widget, cairo_t* cr, gpointer user_data) {
        return ((GtkVideoRenderer*)user_data)->on_draw(widget, cr);
    }

    gboolean on_draw(GtkWidget* widget, cairo_t* cr) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!rgb_buffer_) return FALSE;

        // Create Cairo surface from RGB buffer
        cairo_surface_t* surface = cairo_image_surface_create_for_data(
            rgb_buffer_,
            CAIRO_FORMAT_RGB24,
            width_, height_,
            cairo_format_stride_for_width(CAIRO_FORMAT_RGB24, width_)
        );

        // Scale to widget size
        int widget_width = gtk_widget_get_allocated_width(widget);
        int widget_height = gtk_widget_get_allocated_height(widget);

        cairo_scale(cr,
                   (double)widget_width / width_,
                   (double)widget_height / height_);

        // Draw
        cairo_set_source_surface(cr, surface, 0, 0);
        cairo_paint(cr);

        cairo_surface_destroy(surface);
        return TRUE;
    }

    GtkWidget* drawing_area_;
    unsigned char* rgb_buffer_ = nullptr;
    int width_ = 0;
    int height_ = 0;
    std::mutex mutex_;
};
```

### Option 3: SDL2 (Lightweight)

```cpp
class SDL2VideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
public:
    SDL2VideoRenderer() {
        SDL_Init(SDL_INIT_VIDEO);
        window_ = SDL_CreateWindow("Zoom Video",
                                   SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                   1280, 720, SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE);
        renderer_ = SDL_CreateRenderer(window_, -1, SDL_RENDERER_ACCELERATED);
    }

    ~SDL2VideoRenderer() {
        if (texture_) SDL_DestroyTexture(texture_);
        if (renderer_) SDL_DestroyRenderer(renderer_);
        if (window_) SDL_DestroyWindow(window_);
        SDL_Quit();
    }

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        int width = data->GetStreamWidth();
        int height = data->GetStreamHeight();

        // Create texture if needed
        if (!texture_ || width_ != width || height_ != height) {
            if (texture_) SDL_DestroyTexture(texture_);
            texture_ = SDL_CreateTexture(renderer_, SDL_PIXELFORMAT_IYUV,
                                        SDL_TEXTUREACCESS_STREAMING, width, height);
            width_ = width;
            height_ = height;
        }

        // Update texture with YUV data (no conversion needed!)
        SDL_UpdateYUVTexture(texture_, nullptr,
                            (Uint8*)data->GetYBuffer(), width,
                            (Uint8*)data->GetUBuffer(), width / 2,
                            (Uint8*)data->GetVBuffer(), width / 2);

        // Render
        SDL_RenderClear(renderer_);
        SDL_RenderCopy(renderer_, texture_, nullptr, nullptr);
        SDL_RenderPresent(renderer_);
    }

    void onRawDataStatusChanged(RawDataStatus status) override {}

private:
    SDL_Window* window_ = nullptr;
    SDL_Renderer* renderer_ = nullptr;
    SDL_Texture* texture_ = nullptr;
    int width_ = 0;
    int height_ = 0;
};
```

**Advantage**: SDL2 supports YUV textures natively - no RGB conversion needed!

### Option 4: OpenGL (High Performance)

```cpp
class OpenGLVideoRenderer : public IZoomVideoSDKRawDataPipeDelegate {
public:
    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        // Upload YUV planes as textures
        glBindTexture(GL_TEXTURE_2D, yTexture_);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE,
                    width, height, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE,
                    data->GetYBuffer());

        glBindTexture(GL_TEXTURE_2D, uTexture_);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE,
                    width/2, height/2, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE,
                    data->GetUBuffer());

        glBindTexture(GL_TEXTURE_2D, vTexture_);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_LUMINANCE,
                    width/2, height/2, 0, GL_LUMINANCE, GL_UNSIGNED_BYTE,
                    data->GetVBuffer());

        // Use shader to convert YUV to RGB on GPU
        RenderWithYUVShader();
    }

    void onRawDataStatusChanged(RawDataStatus status) override {}

private:
    GLuint yTexture_, uTexture_, vTexture_;
};
```

---

## Performance Considerations

### CPU vs GPU Conversion

| Method | Performance | Complexity |
|--------|-------------|-----------|
| **Manual CPU** | Slowest | Simple |
| **libyuv (SIMD)** | Fast | Simple |
| **SDL2 YUV texture** | Very Fast | Simple |
| **OpenGL shader** | Fastest | Complex |

**Recommendation**:
- **Simple apps**: libyuv
- **Cross-platform**: Qt + libyuv
- **Performance-critical**: SDL2 or OpenGL

### Memory Management

**CRITICAL**: YUV frames can be large. Use heap mode and manage memory carefully.

```cpp
// Initialize with heap mode
init_params.videoRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;
init_params.shareRawDataMemoryMode = ZoomVideoSDKRawDataMemoryModeHeap;

// Reference counting for async processing
void onRawDataFrameReceived(YUVRawDataI420* data) override {
    if (data->CanAddRef()) {
        data->AddRef();

        // Queue for background processing
        processing_queue_.push(data);

        // Later, after processing
        data->Release();
    }
}
```

### Frame Rate Control

```cpp
class ThrottledRenderer : public IZoomVideoSDKRawDataPipeDelegate {
    auto last_frame_ = std::chrono::steady_clock::now();
    const int target_fps_ = 30;

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_frame_);

        // Throttle to target FPS
        if (elapsed.count() < (1000 / target_fps_)) {
            return;  // Skip frame
        }

        last_frame_ = now;
        RenderFrame(data);
    }
};
```

---

## Audio Raw Data

### Receive Audio

```cpp
// In IZoomVideoSDKDelegate
void onMixedAudioRawDataReceived(AudioRawData* data) override {
    char* buffer = data->GetBuffer();           // PCM 16-bit
    unsigned int len = data->GetBufferLen();    // Bytes
    unsigned int sampleRate = data->GetSampleRate();  // Hz
    unsigned int channels = data->GetChannelNum();    // 1=mono, 2=stereo

    // Play or save audio
    PlayAudio(buffer, len, sampleRate, channels);
}

void onOneWayAudioRawDataReceived(AudioRawData* data, IZoomVideoSDKUser* user) override {
    // Per-user audio
}
```

### Send Audio (Virtual Mic)

```cpp
class VirtualMic : public IZoomVideoSDKVirtualAudioMic {
    IZoomVideoSDKAudioSender* sender_;

    void onMicInitialize(IZoomVideoSDKAudioSender* sender) override {
        sender_ = sender;
    }

    void onMicStartSend() override {
        // Load PCM audio file
        char* audioBuffer = LoadPCMAudio("audio.pcm");
        int length = GetAudioLength();
        int sampleRate = 32000;

        // Send in chunks
        int chunkSize = sampleRate * 2 / 100;  // 10ms chunks (16-bit = 2 bytes)
        for (int offset = 0; offset < length; offset += chunkSize) {
            sender_->Send(audioBuffer + offset, chunkSize, sampleRate);
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    }

    void onMicStopSend() override {}
    void onMicUninitialized() override { sender_ = nullptr; }
};
```

---

## Summary

| Feature | Linux SDK |
|---------|-----------|
| **Canvas API** | ❌ Not available |
| **Raw Data Pipe** | ✅ ONLY rendering option |
| **YUV to RGB** | ✅ Required for most UIs |
| **Qt Integration** | ✅ Recommended |
| **GTK Integration** | ✅ Supported |
| **SDL2** | ✅ Best performance |
| **OpenGL** | ✅ Maximum performance |
| **Virtual Devices** | ✅ For custom media injection |
| **Memory Mode** | ✅ Always use Heap |

**Key Takeaway**: Linux requires manual rendering. Choose your rendering framework (Qt, GTK, SDL2, OpenGL) and implement YUV to RGB conversion.

---

## See Also

- **[SDK Architecture Pattern](sdk-architecture-pattern.md)** - Universal pattern
- **[Raw Video Capture](../examples/raw-video-capture.md)** - Complete capture example
- **[Raw Audio Capture](../examples/raw-audio-capture.md)** - Audio capture example
- **[Qt/GTK Integration](../examples/qt-gtk-integration.md)** - UI framework integration
- **[Virtual Audio/Video](../examples/virtual-audio-video.md)** - Custom media injection
