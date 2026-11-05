# Service Quality Monitoring

## Overview

Monitor video, audio, and screen sharing quality during meetings to detect network issues and notify users of unstable conditions. Works with both **Default UI** and **Custom UI**.

---

## Connection Quality Enum

All quality methods return a `ConnectionQuality` value:

```cpp
enum ConnectionQuality {
    Conn_Quality_Unknown,    // Unknown connection status
    Conn_Quality_Very_Bad,   // Very poor quality
    Conn_Quality_Bad,        // Poor quality
    Conn_Quality_Not_Good,   // Not good quality
    Conn_Quality_Normal,     // Normal quality
    Conn_Quality_Good,       // Good quality
    Conn_Quality_Excellent,  // Excellent quality
};
```

---

## Video Quality

Get video connection quality for the local user:

```cpp
// Get quality of video YOU ARE SENDING
ConnectionQuality sentQuality = meetingService->GetVideoConnQuality(true);
std::cout << "Sent video quality: " << sentQuality << std::endl;

// Get quality of video YOU ARE RECEIVING
ConnectionQuality receivedQuality = meetingService->GetVideoConnQuality(false);
std::cout << "Received video quality: " << receivedQuality << std::endl;
```

**Requirements**: At least 2 users must be sending/receiving video.

---

## Audio Quality

Get audio connection quality for the local user:

```cpp
// Get quality of audio YOU ARE SENDING
ConnectionQuality sentQuality = meetingService->GetAudioConnQuality(true);
std::cout << "Sent audio quality: " << sentQuality << std::endl;

// Get quality of audio YOU ARE RECEIVING
ConnectionQuality receivedQuality = meetingService->GetAudioConnQuality(false);
std::cout << "Received audio quality: " << receivedQuality << std::endl;
```

**Requirements**: At least 2 users must be actively sending audio.

---

## Screen Share Quality

Get screen sharing connection quality for the local user:

```cpp
// Get quality of screen share YOU ARE SENDING
ConnectionQuality sentQuality = meetingService->GetSharingConnQuality(true);
std::cout << "Sent share quality: " << sentQuality << std::endl;

// Get quality of screen share YOU ARE RECEIVING
ConnectionQuality receivedQuality = meetingService->GetSharingConnQuality(false);
std::cout << "Received share quality: " << receivedQuality << std::endl;
```

**Requirements**: At least 2 users in session, with at least one sharing their screen.

---

## Real-Time Quality Callback

Get quality updates for ALL users (not just local user) via the `onUserNetworkStatusChanged` callback:

```cpp
class MeetingServiceEventListener : public IMeetingServiceEvent {
public:
    void onUserNetworkStatusChanged(
        MeetingComponentType type,    // What type: audio, video, or share
        ConnectionQuality level,       // Quality level
        unsigned int userId,           // Which user
        bool uplink                    // true=sending, false=receiving
    ) override {
        const char* typeStr = "";
        switch (type) {
            case MeetingComponentType_AUDIO: typeStr = "Audio"; break;
            case MeetingComponentType_VIDEO: typeStr = "Video"; break;
            case MeetingComponentType_SHARE: typeStr = "Share"; break;
            default: typeStr = "Unknown"; break;
        }

        std::cout << "[QUALITY] User " << userId
                  << " " << typeStr
                  << " " << (uplink ? "send" : "receive")
                  << " quality: " << level << std::endl;

        // Alert user if quality is poor
        if (level <= Conn_Quality_Bad) {
            std::cout << "[WARNING] Poor " << typeStr << " quality detected!" << std::endl;
        }
    }

    // ... other IMeetingServiceEvent methods
};
```

**MeetingComponentType enum**:
```cpp
enum MeetingComponentType {
    MeetingComponentType_Def = 0,   // Default/unknown
    MeetingComponentType_AUDIO,     // Audio component
    MeetingComponentType_VIDEO,     // Video component
    MeetingComponentType_SHARE,     // Screen share component
};
```

---

## Detailed Statistics

Get detailed statistics (latency, packet loss, etc.) via `ISettingService`:

```cpp
// Get setting service
ISettingService* settingService = nullptr;
CreateSettingService(&settingService);

if (settingService) {
    IStatisticSettingContext* statsSettings = settingService->GetStatisticSettings();

    if (statsSettings) {
        // Video statistics
        ASVSessionStatisticInfo videoInfo;
        statsSettings->QueryVideoStatisticInfo(videoInfo);
        std::cout << "Video latency: " << videoInfo.latency << "ms" << std::endl;
        std::cout << "Video packet loss: " << videoInfo.packetLossAvg << "%" << std::endl;

        // Audio statistics
        ASVSessionStatisticInfo audioInfo;
        statsSettings->QueryAudioStatisticInfo(audioInfo);
        std::cout << "Audio latency: " << audioInfo.latency << "ms" << std::endl;

        // Share statistics
        ASVSessionStatisticInfo shareInfo;
        statsSettings->QueryShareStatisticInfo(shareInfo);
        std::cout << "Share latency: " << shareInfo.latency << "ms" << std::endl;
    }
}
```

---

## Complete Example: Quality Monitor

```cpp
class QualityMonitor : public IMeetingServiceEvent {
public:
    QualityMonitor(IMeetingService* meetingService)
        : m_meetingService(meetingService) {}

    void CheckQuality() {
        // Check video quality
        ConnectionQuality videoSend = m_meetingService->GetVideoConnQuality(true);
        ConnectionQuality videoRecv = m_meetingService->GetVideoConnQuality(false);

        // Check audio quality
        ConnectionQuality audioSend = m_meetingService->GetAudioConnQuality(true);
        ConnectionQuality audioRecv = m_meetingService->GetAudioConnQuality(false);

        // Log current status
        std::cout << "=== Connection Quality ===" << std::endl;
        std::cout << "Video: Send=" << QualityToString(videoSend)
                  << ", Recv=" << QualityToString(videoRecv) << std::endl;
        std::cout << "Audio: Send=" << QualityToString(audioSend)
                  << ", Recv=" << QualityToString(audioRecv) << std::endl;

        // Warn if any quality is poor
        if (videoSend <= Conn_Quality_Bad || videoRecv <= Conn_Quality_Bad) {
            std::cout << "[!] Video quality issues detected" << std::endl;
        }
        if (audioSend <= Conn_Quality_Bad || audioRecv <= Conn_Quality_Bad) {
            std::cout << "[!] Audio quality issues detected" << std::endl;
        }
    }

    // Real-time callback
    void onUserNetworkStatusChanged(
        MeetingComponentType type,
        ConnectionQuality level,
        unsigned int userId,
        bool uplink
    ) override {
        if (level <= Conn_Quality_Bad) {
            std::cout << "[ALERT] Poor network quality for user " << userId << std::endl;
            // Could trigger UI notification here
        }
    }

private:
    IMeetingService* m_meetingService;

    const char* QualityToString(ConnectionQuality q) {
        switch (q) {
            case Conn_Quality_Unknown:   return "Unknown";
            case Conn_Quality_Very_Bad:  return "Very Bad";
            case Conn_Quality_Bad:       return "Bad";
            case Conn_Quality_Not_Good:  return "Not Good";
            case Conn_Quality_Normal:    return "Normal";
            case Conn_Quality_Good:      return "Good";
            case Conn_Quality_Excellent: return "Excellent";
            default: return "Unknown";
        }
    }

    // ... implement other required IMeetingServiceEvent methods
};
```

---

## Use Cases

1. **User Notifications**: Alert users when their connection quality drops
2. **Adaptive Quality**: Automatically lower video resolution when quality is poor
3. **Debugging**: Log quality metrics for troubleshooting
4. **Analytics**: Track meeting quality metrics for analysis
5. **Bot Health Monitoring**: Ensure bot has stable connection before processing

---

## Related Documentation

- [Common Issues](../troubleshooting/common-issues.md) - Network error codes
- [Raw Video Capture](raw-video-capture.md) - Video quality affects frame rate
- [Interface Methods](../references/interface-methods.md) - IMeetingServiceEvent methods

---

**Last Updated**: Based on Zoom Windows Meeting SDK v6.7.2.26830
