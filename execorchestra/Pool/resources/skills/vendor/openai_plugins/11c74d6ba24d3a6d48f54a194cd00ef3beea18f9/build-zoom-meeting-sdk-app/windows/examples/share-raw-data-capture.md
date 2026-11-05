# Screen Share Raw Data Capture

## Overview

The Meeting SDK allows you to receive raw screen share data (YUV420 frames) from participants sharing their screen. This uses the same `IZoomSDKRenderer` and `IZoomSDKRendererDelegate` pattern as video capture, but subscribes to `RAW_DATA_TYPE_SHARE` instead of `RAW_DATA_TYPE_VIDEO`.

## Architecture

```
IMeetingService
    ├── GetMeetingShareController() → IMeetingShareController
    │                                      └── GetViewableSharingUserList()
    │
    └── GetMeetingRecordingController() → IMeetingRecordingController
                                               └── StartRawRecording()

createRenderer() → IZoomSDKRenderer
                       ├── subscribe(userId, RAW_DATA_TYPE_SHARE)
                       └── unSubscribe()

IZoomSDKRendererDelegate (your implementation)
    └── onRawDataFrameReceived(YUVRawDataI420*)
```

## Required Headers

```cpp
#include <meeting_service_interface.h>
#include <meeting_service_components/meeting_sharing_interface.h>
#include <meeting_service_components/meeting_recording_interface.h>
#include <rawdata/zoom_rawdata_api.h>
#include <rawdata/rawdata_renderer_interface.h>
```

## Step 1: Implement the Renderer Delegate

```cpp
// ZoomSDKShareRendererDelegate.h
#pragma once
#include <rawdata/rawdata_renderer_interface.h>
#include <fstream>
#include <string>

class ZoomSDKShareRendererDelegate : public ZOOMSDK::IZoomSDKRendererDelegate {
public:
    ZoomSDKShareRendererDelegate();
    virtual ~ZoomSDKShareRendererDelegate();

    // Called when a share frame is received
    virtual void onRawDataFrameReceived(ZOOMSDK::YUVRawDataI420* data) override;

    // Called when renderer status changes
    virtual void onRawDataStatusChanged(
        ZOOMSDK::RawDataStatus status
    ) override;

    // Called when resolution changes
    virtual void onRendererBeDestroyed() override;

    // Frame statistics
    unsigned int getFrameCount() const { return m_frameCount; }
    void resetFrameCount() { m_frameCount = 0; }

    // Enable/disable file output
    void enableFileOutput(const std::string& filename);
    void disableFileOutput();

private:
    unsigned int m_frameCount;
    std::ofstream m_outputFile;
    bool m_writeToFile;
    int m_lastWidth;
    int m_lastHeight;
};
```

```cpp
// ZoomSDKShareRendererDelegate.cpp
#include "ZoomSDKShareRendererDelegate.h"
#include <iostream>

using namespace ZOOMSDK;

ZoomSDKShareRendererDelegate::ZoomSDKShareRendererDelegate()
    : m_frameCount(0)
    , m_writeToFile(false)
    , m_lastWidth(0)
    , m_lastHeight(0) {}

ZoomSDKShareRendererDelegate::~ZoomSDKShareRendererDelegate() {
    disableFileOutput();
}

void ZoomSDKShareRendererDelegate::onRawDataFrameReceived(YUVRawDataI420* data) {
    if (!data) return;

    m_frameCount++;

    // Get frame dimensions
    unsigned int width = data->GetStreamWidth();
    unsigned int height = data->GetStreamHeight();

    // Check for resolution change
    if (width != m_lastWidth || height != m_lastHeight) {
        std::cout << "[Share] Resolution changed: "
                  << width << "x" << height << std::endl;
        m_lastWidth = width;
        m_lastHeight = height;
    }

    // Log periodically
    if (m_frameCount % 30 == 0) {
        std::cout << "[Share] Frame " << m_frameCount
                  << " - " << width << "x" << height
                  << std::endl;
    }

    // YUV420 data access
    char* yBuffer = data->GetYBuffer();
    char* uBuffer = data->GetUBuffer();
    char* vBuffer = data->GetVBuffer();

    // Calculate buffer sizes for YUV420
    unsigned int ySize = width * height;
    unsigned int uvSize = (width / 2) * (height / 2);

    // Write to file if enabled
    if (m_writeToFile && m_outputFile.is_open()) {
        m_outputFile.write(yBuffer, ySize);
        m_outputFile.write(uBuffer, uvSize);
        m_outputFile.write(vBuffer, uvSize);
    }

    // Process the frame (e.g., display, encode, analyze)
    // The data is in YUV I420 format:
    // - Y plane: width * height bytes (luminance)
    // - U plane: (width/2) * (height/2) bytes (chrominance)
    // - V plane: (width/2) * (height/2) bytes (chrominance)
}

void ZoomSDKShareRendererDelegate::onRawDataStatusChanged(RawDataStatus status) {
    switch (status) {
        case RawData_On:
            std::cout << "[Share] Raw data: ON" << std::endl;
            break;
        case RawData_Off:
            std::cout << "[Share] Raw data: OFF" << std::endl;
            break;
        default:
            std::cout << "[Share] Raw data status: " << status << std::endl;
    }
}

void ZoomSDKShareRendererDelegate::onRendererBeDestroyed() {
    std::cout << "[Share] Renderer being destroyed" << std::endl;
    disableFileOutput();
}

void ZoomSDKShareRendererDelegate::enableFileOutput(const std::string& filename) {
    disableFileOutput();
    m_outputFile.open(filename, std::ios::binary);
    if (m_outputFile.is_open()) {
        m_writeToFile = true;
        std::cout << "[Share] Writing to: " << filename << std::endl;
    }
}

void ZoomSDKShareRendererDelegate::disableFileOutput() {
    if (m_outputFile.is_open()) {
        m_outputFile.close();
    }
    m_writeToFile = false;
}
```

## Step 2: Initialize Share Capture

```cpp
// Global variables
ZoomSDKShareRendererDelegate* g_shareDelegate = nullptr;
IZoomSDKRenderer* g_shareRenderer = nullptr;
IMeetingShareController* g_shareController = nullptr;
IMeetingRecordingController* g_recordController = nullptr;

void initializeShareCapture(IMeetingService* meetingService) {
    // Get controllers
    g_shareController = meetingService->GetMeetingShareController();
    g_recordController = meetingService->GetMeetingRecordingController();

    if (!g_shareController || !g_recordController) {
        std::cerr << "Failed to get controllers" << std::endl;
        return;
    }

    // Create delegate
    g_shareDelegate = new ZoomSDKShareRendererDelegate();

    std::cout << "Share capture initialized" << std::endl;
}
```

## Step 3: Find Sharing User and Subscribe

```cpp
unsigned int getSharingUserId() {
    if (!g_shareController) return 0;

    // Get list of users currently sharing
    IList<unsigned int>* sharingUsers = g_shareController->GetViewableSharingUserList();

    if (!sharingUsers || sharingUsers->GetCount() == 0) {
        std::cout << "No one is sharing" << std::endl;
        return 0;
    }

    // Get first sharing user
    unsigned int userId = sharingUsers->GetItem(0);
    std::cout << "User " << userId << " is sharing" << std::endl;

    return userId;
}

void startShareCapture() {
    if (!g_shareDelegate) return;

    // Start raw recording first (required for raw data access)
    SDKError err = g_recordController->StartRawRecording();
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to start raw recording: " << err << std::endl;
        return;
    }

    // Create renderer
    err = createRenderer(&g_shareRenderer, g_shareDelegate);
    if (err != SDKERR_SUCCESS) {
        std::cerr << "Failed to create renderer: " << err << std::endl;
        return;
    }

    // Get sharing user
    unsigned int userId = getSharingUserId();
    if (userId == 0) {
        std::cout << "No sharing user to subscribe to" << std::endl;
        return;
    }

    // Subscribe to share raw data
    err = g_shareRenderer->subscribe(userId, RAW_DATA_TYPE_SHARE);
    if (err == SDKERR_SUCCESS) {
        std::cout << "Subscribed to share from user " << userId << std::endl;

        // Optionally save to file
        g_shareDelegate->enableFileOutput("share_capture.yuv");
    } else {
        std::cerr << "Failed to subscribe: " << err << std::endl;
    }
}

void stopShareCapture() {
    if (g_shareRenderer) {
        g_shareRenderer->unSubscribe();
        std::cout << "Unsubscribed from share" << std::endl;
    }

    if (g_shareDelegate) {
        g_shareDelegate->disableFileOutput();
    }
}
```

## Step 4: Handle Share Events

To know when sharing starts/stops, implement a share controller event listener:

```cpp
// MeetingShareCtrlEventListener.h
#pragma once
#include <meeting_service_components/meeting_sharing_interface.h>

class MeetingShareCtrlEventListener : public ZOOMSDK::IMeetingShareCtrlEvent {
public:
    using ShareStartedCallback = std::function<void(unsigned int)>;
    using ShareStoppedCallback = std::function<void()>;

    MeetingShareCtrlEventListener(
        ShareStartedCallback onStarted = nullptr,
        ShareStoppedCallback onStopped = nullptr
    );

    // Sharing status changed
    virtual void onSharingStatus(
        ZOOMSDK::SharingStatus status,
        unsigned int userId
    ) override;

    // Someone started sharing
    virtual void onLockShareStatus(bool bLocked) override;

    // Share content changed
    virtual void onShareContentNotification(
        ZOOMSDK::ShareInfo* shareInfo
    ) override;

    // Multi-share
    virtual void onMultiShareSwitchToSingleShareNeedConfirm(
        ZOOMSDK::IShareSwitchMultiToSingleConfirmHandler* handler
    ) override;

    virtual void onShareSettingTypeChangedNotification(
        ZOOMSDK::ShareSettingType type
    ) override;

    virtual void onSharedVideoEnded() override;

private:
    ShareStartedCallback m_onStarted;
    ShareStoppedCallback m_onStopped;
};
```

```cpp
// MeetingShareCtrlEventListener.cpp
#include "MeetingShareCtrlEventListener.h"
#include <iostream>

using namespace ZOOMSDK;

MeetingShareCtrlEventListener::MeetingShareCtrlEventListener(
    ShareStartedCallback onStarted,
    ShareStoppedCallback onStopped
) : m_onStarted(onStarted), m_onStopped(onStopped) {}

void MeetingShareCtrlEventListener::onSharingStatus(
    SharingStatus status,
    unsigned int userId
) {
    switch (status) {
        case Sharing_Self_Send_Begin:
            std::cout << "Started sharing (self)" << std::endl;
            break;
        case Sharing_Self_Send_End:
            std::cout << "Stopped sharing (self)" << std::endl;
            break;
        case Sharing_Other_Share_Begin:
            std::cout << "User " << userId << " started sharing" << std::endl;
            if (m_onStarted) m_onStarted(userId);
            break;
        case Sharing_Other_Share_End:
            std::cout << "User " << userId << " stopped sharing" << std::endl;
            if (m_onStopped) m_onStopped();
            break;
        case Sharing_View_Other_Sharing:
            std::cout << "Viewing share from user " << userId << std::endl;
            break;
        case Sharing_Pause:
            std::cout << "Sharing paused" << std::endl;
            break;
        case Sharing_Resume:
            std::cout << "Sharing resumed" << std::endl;
            break;
        default:
            std::cout << "Sharing status: " << status << std::endl;
    }
}

void MeetingShareCtrlEventListener::onLockShareStatus(bool bLocked) {
    std::cout << "Share lock: " << (bLocked ? "LOCKED" : "UNLOCKED") << std::endl;
}

void MeetingShareCtrlEventListener::onShareContentNotification(ShareInfo* shareInfo) {
    if (shareInfo) {
        std::cout << "Share content changed" << std::endl;
    }
}

void MeetingShareCtrlEventListener::onMultiShareSwitchToSingleShareNeedConfirm(
    IShareSwitchMultiToSingleConfirmHandler* handler
) {
    // Handle multi-share to single-share switch
}

void MeetingShareCtrlEventListener::onShareSettingTypeChangedNotification(
    ShareSettingType type
) {
    std::cout << "Share setting changed" << std::endl;
}

void MeetingShareCtrlEventListener::onSharedVideoEnded() {
    std::cout << "Shared video ended" << std::endl;
}
```

## Complete Integration Example

```cpp
// Global share event listener
MeetingShareCtrlEventListener* g_shareEventListener = nullptr;

void onInMeeting(IMeetingService* meetingService) {
    // Initialize share capture
    initializeShareCapture(meetingService);

    // Set up share event listener
    g_shareEventListener = new MeetingShareCtrlEventListener(
        // On share started
        [](unsigned int userId) {
            std::cout << "Starting capture for user " << userId << std::endl;
            startShareCapture();
        },
        // On share stopped
        []() {
            std::cout << "Stopping capture" << std::endl;
            stopShareCapture();
        }
    );

    g_shareController->SetEvent(g_shareEventListener);

    // Check if someone is already sharing
    unsigned int sharingUser = getSharingUserId();
    if (sharingUser != 0) {
        startShareCapture();
    }
}

// Cleanup
void cleanup() {
    stopShareCapture();

    if (g_shareRenderer) {
        // Renderer will be destroyed when unsubscribed
        g_shareRenderer = nullptr;
    }

    delete g_shareDelegate;
    g_shareDelegate = nullptr;

    delete g_shareEventListener;
    g_shareEventListener = nullptr;
}
```

## Sharing Status Values

```cpp
enum SharingStatus {
    Sharing_Self_Send_Begin,     // You started sharing
    Sharing_Self_Send_End,       // You stopped sharing
    Sharing_Other_Share_Begin,   // Someone else started sharing
    Sharing_Other_Share_End,     // Someone else stopped sharing
    Sharing_View_Other_Sharing,  // Viewing someone's share
    Sharing_Pause,               // Sharing paused
    Sharing_Resume,              // Sharing resumed
    Sharing_ContentTypeChange,   // Content type changed
    Sharing_SelfStartAudioShare, // Started audio share
    Sharing_SelfStopAudioShare   // Stopped audio share
};
```

## Raw Data Types

```cpp
enum RawDataType {
    RAW_DATA_TYPE_VIDEO = 0,  // Video frames
    RAW_DATA_TYPE_SHARE       // Screen share frames
};
```

## Permission Requirements

To receive screen share raw data, you need:

1. **Raw Recording Permission**: Call `StartRawRecording()` before subscribing
2. **Recording Permission**: Either be host, co-host, or have recording permission granted

```cpp
bool checkPermission() {
    SDKError err = g_recordController->CanStartRecording(false, 0);
    if (err != SDKERR_SUCCESS) {
        std::cout << "Requesting recording permission..." << std::endl;
        g_recordController->RequestLocalRecordingPrivilege();
        return false;
    }
    return true;
}
```

## Converting YUV to RGB/Image

The raw data is in YUV420 (I420) format. To convert to RGB or save as image:

```cpp
// Using OpenCV
#include <opencv2/opencv.hpp>

void saveFrameAsImage(YUVRawDataI420* data, const std::string& filename) {
    int width = data->GetStreamWidth();
    int height = data->GetStreamHeight();

    // Create Mat from YUV data
    cv::Mat yuvFrame(height + height/2, width, CV_8UC1);

    // Copy Y plane
    memcpy(yuvFrame.data, data->GetYBuffer(), width * height);

    // Copy U and V planes (interleaved in I420)
    memcpy(yuvFrame.data + width * height,
           data->GetUBuffer(), (width/2) * (height/2));
    memcpy(yuvFrame.data + width * height + (width/2) * (height/2),
           data->GetVBuffer(), (width/2) * (height/2));

    // Convert to BGR
    cv::Mat bgrFrame;
    cv::cvtColor(yuvFrame, bgrFrame, cv::COLOR_YUV2BGR_I420);

    // Save
    cv::imwrite(filename, bgrFrame);
}
```

## Common Pitfalls

1. **No share data**: Make sure someone is actually sharing before subscribing
2. **Raw recording**: Must call `StartRawRecording()` before subscribing to share
3. **Permission**: Recording permission is required for raw data access
4. **Multiple sharers**: Use `GetViewableSharingUserList()` to get all sharing users
5. **Resolution changes**: Screen share resolution can change dynamically (window resize)
6. **Frame rate**: Screen share frame rate is typically lower than video (varies by content)
7. **Subscribe timing**: Subscribe after sharing starts, not before

## Difference from Video Capture

| Aspect | Video Capture | Share Capture |
|--------|---------------|---------------|
| Data Type | `RAW_DATA_TYPE_VIDEO` | `RAW_DATA_TYPE_SHARE` |
| Source | Webcam | Screen/Window/App |
| Resolution | Fixed camera resolution | Dynamic (window size) |
| Frame Rate | Consistent (30fps) | Variable (content-dependent) |
| User List | Participants controller | Share controller |

Both use the same `IZoomSDKRenderer` and `IZoomSDKRendererDelegate` interfaces.
