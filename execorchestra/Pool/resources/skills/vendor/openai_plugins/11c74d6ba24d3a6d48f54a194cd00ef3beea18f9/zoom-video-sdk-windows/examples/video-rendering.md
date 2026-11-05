# Video Rendering with Canvas API

Complete working code for subscribing to and displaying video using the Canvas API.

## Overview

The Canvas API lets the SDK render video directly to your window. This is the **recommended approach** for standard video applications.

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIDEO SUBSCRIPTION FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│  onSessionJoin       →  Subscribe to self video                 │
│  onUserVideoStatusChanged →  Subscribe to remote video (when ON)│
│  onUserLeave         →  Unsubscribe and cleanup                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Critical Rule

### Subscribe in onUserVideoStatusChanged, NOT onUserJoin

```cpp
// WRONG - Video may not be ready yet!
void onUserJoin(IZoomVideoSDKUserHelper* helper,
                IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
    for (int i = 0; i < userList->GetCount(); i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        // This returns Error 2 (Internal_Error) - video not ready!
        user->GetVideoCanvas()->subscribeWithView(hwnd, aspect, resolution);
    }
}

// CORRECT - Wait for video status change
void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                               IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
    IZoomVideoSDKUser* myself = g_sdk->getSessionInfo()->getMyself();

    for (int i = 0; i < userList->GetCount(); i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);

        // Skip self (handled separately)
        if (user == myself) continue;

        // Check if video is actually on
        ZoomVideoSDKVideoStatus status = user->GetVideoPipe()->getVideoStatus();
        if (status.isOn) {
            // NOW it's safe to subscribe
            SubscribeToUser(user);
        } else {
            // Video turned off - unsubscribe
            UnsubscribeFromUser(user);
        }
    }
}
```

---

## Complete Working Code

### VideoCanvasManager.h

```cpp
#pragma once
#include <windows.h>
#include <map>
#include <vector>
#include "zoom_video_sdk_interface.h"

USING_ZOOM_VIDEO_SDK_NAMESPACE

class VideoCanvasManager {
public:
    VideoCanvasManager(HWND parentWindow, IZoomVideoSDK* sdk);
    ~VideoCanvasManager();

    // Subscribe to self video
    void SubscribeToSelf();

    // Subscribe/unsubscribe to remote user
    void SubscribeToUser(IZoomVideoSDKUser* user);
    void UnsubscribeFromUser(IZoomVideoSDKUser* user);

    // Cleanup
    void UnsubscribeAll();

    // Layout
    void UpdateLayout();

private:
    HWND CreateVideoWindow();
    void DestroyVideoWindow(HWND hwnd);

    IZoomVideoSDK* m_sdk;
    HWND m_parentWindow;

    // Self video
    HWND m_selfVideoWindow;
    IZoomVideoSDKCanvas* m_selfCanvas;

    // Remote users: user -> window mapping
    std::map<IZoomVideoSDKUser*, HWND> m_userWindows;
    std::map<IZoomVideoSDKUser*, IZoomVideoSDKCanvas*> m_userCanvases;
};
```

### VideoCanvasManager.cpp

```cpp
#include "VideoCanvasManager.h"
#include <iostream>

VideoCanvasManager::VideoCanvasManager(HWND parentWindow, IZoomVideoSDK* sdk)
    : m_parentWindow(parentWindow)
    , m_sdk(sdk)
    , m_selfVideoWindow(nullptr)
    , m_selfCanvas(nullptr) {
}

VideoCanvasManager::~VideoCanvasManager() {
    UnsubscribeAll();
}

HWND VideoCanvasManager::CreateVideoWindow() {
    // Create a child window for video rendering
    HWND hwnd = CreateWindowExW(
        0,
        L"STATIC",  // Simple static window class
        L"",
        WS_CHILD | WS_VISIBLE | WS_BORDER,
        0, 0, 320, 240,  // Size will be set by UpdateLayout()
        m_parentWindow,
        nullptr,
        GetModuleHandle(nullptr),
        nullptr
    );

    return hwnd;
}

void VideoCanvasManager::DestroyVideoWindow(HWND hwnd) {
    if (hwnd) {
        DestroyWindow(hwnd);
    }
}

void VideoCanvasManager::SubscribeToSelf() {
    IZoomVideoSDKSession* session = m_sdk->getSessionInfo();
    if (!session) return;

    IZoomVideoSDKUser* myself = session->getMyself();
    if (!myself) return;

    // Create window for self video
    if (!m_selfVideoWindow) {
        m_selfVideoWindow = CreateVideoWindow();
    }

    // Subscribe
    m_selfCanvas = myself->GetVideoCanvas();
    if (m_selfCanvas) {
        ZoomVideoSDKErrors err = m_selfCanvas->subscribeWithView(
            m_selfVideoWindow,
            ZoomVideoSDKVideoAspect_PanAndScan,
            ZoomVideoSDKResolution_Auto
        );

        if (err == ZoomVideoSDKErrors_Success) {
            std::cout << "Self video subscribed" << std::endl;
        } else {
            std::cout << "Self video subscribe failed: " << err << std::endl;
        }
    }

    UpdateLayout();
}

void VideoCanvasManager::SubscribeToUser(IZoomVideoSDKUser* user) {
    if (!user) return;

    // Skip if already subscribed
    if (m_userWindows.find(user) != m_userWindows.end()) {
        return;
    }

    // Check if video is on
    IZoomVideoSDKRawDataPipe* pipe = user->GetVideoPipe();
    if (!pipe || !pipe->getVideoStatus().isOn) {
        return;
    }

    // Create window for this user
    HWND hwnd = CreateVideoWindow();
    m_userWindows[user] = hwnd;

    // Subscribe to canvas
    IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();
    if (canvas) {
        ZoomVideoSDKErrors err = canvas->subscribeWithView(
            hwnd,
            ZoomVideoSDKVideoAspect_PanAndScan,
            ZoomVideoSDKResolution_Auto
        );

        if (err == ZoomVideoSDKErrors_Success) {
            m_userCanvases[user] = canvas;
            std::wcout << L"Subscribed to: " << user->getUserName() << std::endl;
        } else {
            std::wcout << L"Subscribe failed for: " << user->getUserName()
                       << L" error: " << err << std::endl;
            // Cleanup on failure
            DestroyVideoWindow(hwnd);
            m_userWindows.erase(user);
        }
    }

    UpdateLayout();
}

void VideoCanvasManager::UnsubscribeFromUser(IZoomVideoSDKUser* user) {
    if (!user) return;

    auto it = m_userWindows.find(user);
    if (it == m_userWindows.end()) {
        return;
    }

    HWND hwnd = it->second;

    // Unsubscribe from canvas
    auto canvasIt = m_userCanvases.find(user);
    if (canvasIt != m_userCanvases.end()) {
        IZoomVideoSDKCanvas* canvas = canvasIt->second;
        if (canvas) {
            canvas->unSubscribeWithView(hwnd);
        }
        m_userCanvases.erase(canvasIt);
    }

    // Destroy window
    DestroyVideoWindow(hwnd);
    m_userWindows.erase(it);

    std::wcout << L"Unsubscribed from: " << user->getUserName() << std::endl;

    UpdateLayout();
}

void VideoCanvasManager::UnsubscribeAll() {
    // Unsubscribe self
    if (m_selfCanvas && m_selfVideoWindow) {
        m_selfCanvas->unSubscribeWithView(m_selfVideoWindow);
        DestroyVideoWindow(m_selfVideoWindow);
        m_selfVideoWindow = nullptr;
        m_selfCanvas = nullptr;
    }

    // Unsubscribe all remote users
    for (auto& pair : m_userCanvases) {
        IZoomVideoSDKCanvas* canvas = pair.second;
        IZoomVideoSDKUser* user = pair.first;

        auto windowIt = m_userWindows.find(user);
        if (windowIt != m_userWindows.end() && canvas) {
            canvas->unSubscribeWithView(windowIt->second);
        }
    }

    for (auto& pair : m_userWindows) {
        DestroyVideoWindow(pair.second);
    }

    m_userCanvases.clear();
    m_userWindows.clear();
}

void VideoCanvasManager::UpdateLayout() {
    RECT parentRect;
    GetClientRect(m_parentWindow, &parentRect);

    int totalVideos = (m_selfVideoWindow ? 1 : 0) + m_userWindows.size();
    if (totalVideos == 0) return;

    // Calculate grid dimensions
    int cols = (int)ceil(sqrt((double)totalVideos));
    int rows = (int)ceil((double)totalVideos / cols);

    int cellWidth = (parentRect.right - parentRect.left) / cols;
    int cellHeight = (parentRect.bottom - parentRect.top) / rows;

    int index = 0;

    // Position self video (top-left)
    if (m_selfVideoWindow) {
        int row = index / cols;
        int col = index % cols;
        SetWindowPos(m_selfVideoWindow, NULL,
                     col * cellWidth, row * cellHeight,
                     cellWidth, cellHeight,
                     SWP_NOZORDER);
        index++;
    }

    // Position remote videos
    for (auto& pair : m_userWindows) {
        HWND hwnd = pair.second;
        int row = index / cols;
        int col = index % cols;
        SetWindowPos(hwnd, NULL,
                     col * cellWidth, row * cellHeight,
                     cellWidth, cellHeight,
                     SWP_NOZORDER);
        index++;
    }
}
```

### Using in Delegate

```cpp
class MyDelegate : public IZoomVideoSDKDelegate {
private:
    VideoCanvasManager* m_videoManager;

public:
    MyDelegate(HWND parentWindow, IZoomVideoSDK* sdk) {
        m_videoManager = new VideoCanvasManager(parentWindow, sdk);
    }

    ~MyDelegate() {
        delete m_videoManager;
    }

    void onSessionJoin() override {
        // Subscribe to self video
        m_videoManager->SubscribeToSelf();
    }

    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                                   IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        IZoomVideoSDKUser* myself = g_sdk->getSessionInfo()->getMyself();

        for (int i = 0; i < userList->GetCount(); i++) {
            IZoomVideoSDKUser* user = userList->GetItem(i);
            if (user == myself) continue;

            ZoomVideoSDKVideoStatus status = user->GetVideoPipe()->getVideoStatus();
            if (status.isOn) {
                m_videoManager->SubscribeToUser(user);
            } else {
                m_videoManager->UnsubscribeFromUser(user);
            }
        }
    }

    void onUserLeave(IZoomVideoSDKUserHelper* helper,
                     IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        for (int i = 0; i < userList->GetCount(); i++) {
            m_videoManager->UnsubscribeFromUser(userList->GetItem(i));
        }
    }

    void onSessionLeave() override {
        m_videoManager->UnsubscribeAll();
    }

    // ... other callbacks
};
```

---

## Error Handling

### Subscribe Fail Callback

```cpp
void onVideoCanvasSubscribeFail(ZoomVideoSDKSubscribeFailReason reason,
                                 IZoomVideoSDKUser* user, void* handle) override {
    std::wcout << L"Subscribe failed for: " << user->getUserName()
               << L" reason: " << reason << std::endl;

    switch (reason) {
        case ZoomVideoSDKSubscribeFailReason_HasSubscribe1080POr720P:
            std::cout << "Already have a 1080p/720p subscription" << std::endl;
            break;
        case ZoomVideoSDKSubscribeFailReason_HasSubscribeExceededLimit:
            std::cout << "Subscription limit exceeded" << std::endl;
            break;
        case ZoomVideoSDKSubscribeFailReason_TooFrequentCall:
            std::cout << "Calling too frequently - add Sleep(200)" << std::endl;
            break;
    }
}
```

### Subscribe Fail Reasons

| Code | Reason | Solution |
|------|--------|----------|
| 0 | None | - |
| 1 | HasSubscribe1080POr720P | Already have HD subscription |
| 2 | HasSubscribeTwo720P | Max 2x 720p subscriptions |
| 3 | HasSubscribeExceededLimit | Too many subscriptions |
| 4 | HasSubscribeTwoShare | Max 2 share subscriptions |
| 5 | HasSubscribeVideo1080POr720PAndOneShare | Limit reached |
| 6 | TooFrequentCall | Add `Sleep(200)` between calls |

---

## Aspect Ratio Options

| Option | Behavior | Use Case |
|--------|----------|----------|
| `ZoomVideoSDKVideoAspect_Original` | Letterbox/pillarbox | Show full video |
| `ZoomVideoSDKVideoAspect_FullFilled` | Fill, may crop | Full coverage |
| `ZoomVideoSDKVideoAspect_PanAndScan` | Smart crop | Balanced (recommended) |
| `ZoomVideoSDKVideoAspect_LetterBox` | Black bars | Preserve aspect |

---

## Resolution Options

| Option | Resolution | Use Case |
|--------|------------|----------|
| `ZoomVideoSDKResolution_90P` | 160x90 | Thumbnails |
| `ZoomVideoSDKResolution_180P` | 320x180 | Small previews |
| `ZoomVideoSDKResolution_360P` | 640x360 | Standard |
| `ZoomVideoSDKResolution_720P` | 1280x720 | HD |
| `ZoomVideoSDKResolution_1080P` | 1920x1080 | Full HD |
| `ZoomVideoSDKResolution_Auto` | SDK chooses | Recommended |

---

## Related Documentation

- [Canvas vs Raw Data](../concepts/canvas-vs-raw-data.md) - Rendering approach comparison
- [Raw Video Capture](raw-video-capture.md) - For custom processing
- [Singleton Hierarchy](../concepts/singleton-hierarchy.md) - Canvas/Pipe navigation
- [Common Issues](../troubleshooting/common-issues.md) - Error codes

---

**TL;DR**: Subscribe to self in `onSessionJoin`, subscribe to remote users in `onUserVideoStatusChanged` (when `status.isOn == true`), unsubscribe in `onUserLeave`.
