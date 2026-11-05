# Send Raw Audio

Complete working code for sending custom audio as a virtual microphone.

**Official Sample**: `VSDK_sendRawAudio` in [videosdk-windows-rawdata-sample](https://github.com/zoom/videosdk-windows-rawdata-sample)

---

## Overview

Inject custom audio into your session. Use cases:
- Virtual microphone with custom content
- Text-to-speech output
- Pre-recorded audio playback
- Audio effects/processing pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUDIO INJECTION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│  Your Audio Source (file, TTS, generated)                       │
│       ↓                                                         │
│  PCM format (16-bit, 32000 Hz)                                  │
│       ↓                                                         │
│  IZoomVideoSDKVirtualAudioMic::onMicInitialize()                │
│       ↓                                                         │
│  IZoomVideoSDKAudioSender::send()                               │
│       ↓                                                         │
│  Participants hear your custom audio                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Audio Format Requirements

| Property | Value |
|----------|-------|
| Format | PCM (uncompressed) |
| Sample Rate | 32000 Hz (required) |
| Bit Depth | 16-bit signed |
| Channels | Mono (1) |
| Byte Order | Little-endian |

**Important**: The SDK requires exactly 32000 Hz sample rate.

---

## Complete Working Code

### VirtualMic.h

```cpp
#pragma once
#include <windows.h>
#include <thread>
#include <atomic>
#include <fstream>
#include "zoom_video_sdk_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

class VirtualMic : public IZoomVideoSDKVirtualAudioMic {
public:
    VirtualMic();
    ~VirtualMic();

    // Set audio source file
    void SetAudioFile(const std::string& pcmFile);

    // IZoomVideoSDKVirtualAudioMic interface
    void onMicInitialize(IZoomVideoSDKAudioSender* sender) override;
    void onMicStartSend() override;
    void onMicStopSend() override;
    void onMicUninitialized() override;

private:
    void SendLoop();
    void GenerateSineWave(char* buffer, int samples, int frequency);

    IZoomVideoSDKAudioSender* m_sender;
    std::thread m_sendThread;
    std::atomic<bool> m_sending;
    std::string m_audioFile;
    std::ifstream m_fileStream;

    static const int SAMPLE_RATE = 32000;
    static const int CHANNELS = 1;
    static const int BITS_PER_SAMPLE = 16;
};
```

### VirtualMic.cpp

```cpp
#include "VirtualMic.h"
#include <iostream>
#include <chrono>
#include <cmath>

VirtualMic::VirtualMic()
    : m_sender(nullptr)
    , m_sending(false) {
}

VirtualMic::~VirtualMic() {
    m_sending = false;
    if (m_sendThread.joinable()) {
        m_sendThread.join();
    }
}

void VirtualMic::SetAudioFile(const std::string& pcmFile) {
    m_audioFile = pcmFile;
}

void VirtualMic::onMicInitialize(IZoomVideoSDKAudioSender* sender) {
    std::cout << "VirtualMic initialized" << std::endl;
    m_sender = sender;
}

void VirtualMic::onMicStartSend() {
    std::cout << "VirtualMic start sending" << std::endl;

    // Open audio file if specified
    if (!m_audioFile.empty()) {
        m_fileStream.open(m_audioFile, std::ios::binary);
        if (!m_fileStream.is_open()) {
            std::cerr << "Failed to open: " << m_audioFile << std::endl;
        }
    }

    m_sending = true;
    m_sendThread = std::thread(&VirtualMic::SendLoop, this);
}

void VirtualMic::onMicStopSend() {
    std::cout << "VirtualMic stop sending" << std::endl;
    m_sending = false;
    if (m_sendThread.joinable()) {
        m_sendThread.join();
    }

    if (m_fileStream.is_open()) {
        m_fileStream.close();
    }
}

void VirtualMic::onMicUninitialized() {
    std::cout << "VirtualMic uninitialized" << std::endl;
    m_sender = nullptr;
}

void VirtualMic::SendLoop() {
    // Send 20ms chunks (640 samples at 32000 Hz)
    const int SAMPLES_PER_CHUNK = 640;
    const int BYTES_PER_CHUNK = SAMPLES_PER_CHUNK * sizeof(short);

    char* buffer = new char[BYTES_PER_CHUNK];
    int sampleOffset = 0;

    auto chunkInterval = std::chrono::milliseconds(20);

    while (m_sending && m_sender) {
        auto startTime = std::chrono::steady_clock::now();

        bool hasData = false;

        // Read from file or generate tone
        if (m_fileStream.is_open() && m_fileStream.good()) {
            m_fileStream.read(buffer, BYTES_PER_CHUNK);
            hasData = m_fileStream.gcount() > 0;

            // Loop file
            if (!hasData) {
                m_fileStream.clear();
                m_fileStream.seekg(0);
                m_fileStream.read(buffer, BYTES_PER_CHUNK);
                hasData = m_fileStream.gcount() > 0;
            }
        } else {
            // Generate 440 Hz sine wave (A4 note)
            GenerateSineWave(buffer, SAMPLES_PER_CHUNK, 440);
            sampleOffset += SAMPLES_PER_CHUNK;
            hasData = true;
        }

        if (hasData) {
            // Send audio chunk
            ZoomVideoSDKErrors err = m_sender->send(
                buffer,
                BYTES_PER_CHUNK,
                SAMPLE_RATE
            );

            if (err != ZoomVideoSDKErrors_Success) {
                std::cout << "Audio send error: " << err << std::endl;
            }
        }

        // Maintain timing
        auto elapsed = std::chrono::steady_clock::now() - startTime;
        auto sleepTime = chunkInterval - elapsed;
        if (sleepTime.count() > 0) {
            std::this_thread::sleep_for(sleepTime);
        }
    }

    delete[] buffer;
}

void VirtualMic::GenerateSineWave(char* buffer, int samples, int frequency) {
    short* samples16 = reinterpret_cast<short*>(buffer);
    static int phase = 0;

    const double amplitude = 16000;  // ~50% volume
    const double twoPi = 2.0 * 3.14159265358979323846;

    for (int i = 0; i < samples; i++) {
        double t = (double)(phase + i) / SAMPLE_RATE;
        double value = amplitude * sin(twoPi * frequency * t);
        samples16[i] = (short)value;
    }

    phase += samples;
}
```

### Registering the Virtual Mic

```cpp
void StartVirtualMic() {
    IZoomVideoSDKAudioHelper* audioHelper = sdk->getAudioHelper();
    if (!audioHelper) return;

    // Create virtual mic
    VirtualMic* virtualMic = new VirtualMic();

    // Optional: set audio file
    // virtualMic->SetAudioFile("audio.pcm");

    // Set as audio source
    ZoomVideoSDKErrors err = audioHelper->setExternalAudioSource(virtualMic);
    if (err != ZoomVideoSDKErrors_Success) {
        std::cout << "setExternalAudioSource failed: " << err << std::endl;
        return;
    }

    // Start audio (this triggers onMicStartSend)
    audioHelper->startAudio();
}
```

---

## Audio File Preparation

### Convert WAV to PCM

```cmd
ffmpeg -i input.wav -f s16le -ar 32000 -ac 1 output.pcm
```

### Convert MP3 to PCM

```cmd
ffmpeg -i input.mp3 -f s16le -ar 32000 -ac 1 output.pcm
```

### Key FFmpeg Flags

| Flag | Description |
|------|-------------|
| `-f s16le` | 16-bit signed little-endian PCM |
| `-ar 32000` | Sample rate 32000 Hz (required!) |
| `-ac 1` | Mono channel |

---

## IZoomVideoSDKAudioSender::send()

```cpp
ZoomVideoSDKErrors send(
    char* data,        // PCM audio buffer
    unsigned int length,    // Buffer size in bytes
    int sampleRate         // Must be 32000
);
```

**Timing**: Send 20ms chunks (640 samples = 1280 bytes at 32000 Hz mono)

---

## Common Issues

### No Audio Output

**Cause**: Not calling `startAudio()` after setting source

**Fix**:
```cpp
audioHelper->setExternalAudioSource(virtualMic);
audioHelper->startAudio();  // Required!
```

### Audio is Choppy

**Cause**: Inconsistent send timing

**Fix**: Use precise 20ms intervals:
```cpp
auto chunkInterval = std::chrono::milliseconds(20);
// ... send chunk ...
auto elapsed = std::chrono::steady_clock::now() - startTime;
std::this_thread::sleep_for(chunkInterval - elapsed);
```

### Wrong Sample Rate

**Cause**: Using 44100 Hz instead of 32000 Hz

**Fix**: Always use 32000 Hz:
```cmd
ffmpeg -ar 32000 ...  # Not 44100!
```

### Audio Too Loud/Quiet

**Cause**: PCM amplitude out of range

**Fix**: Normalize to ±32767 range:
```cpp
const double amplitude = 16000;  // 50% volume
```

---

## Related Documentation

- [Raw Audio Capture](raw-audio-capture.md) - Capture audio
- [Send Raw Video](send-raw-video.md) - Video injection
- [Session Join Pattern](session-join-pattern.md) - Audio setup
- [API Reference](../references/windows-reference.md) - Method signatures
