# Custom UI Video Rendering — Complete Working Example

> **Skill**: Zoom Meeting SDK (Windows)
> **Category**: Examples
> **Prerequisite**: [Custom UI Architecture](../concepts/custom-ui-architecture.md), [Authentication Pattern](authentication-pattern.md)

## Overview

This example shows how to create a Custom UI meeting app that:
1. Creates its own Win32 window
2. Uses `ICustomizedVideoContainer` for SDK-rendered video
3. Shows an active speaker element (auto-follows who's talking)
4. Shows gallery elements for each participant
5. Handles screen sharing via `ICustomizedShareRender`

## Flow

```
InitSDK (with ENABLE_CUSTOMIZED_UI_FLAG)
  -> AuthSDK (JWT)
    -> JoinMeeting
      -> OnConnecting: Create window + CustomUIMgr + VideoContainer
        -> OnInMeeting: Create video elements + subscribe to participants
          -> Message loop (window events + SDK callbacks)
            -> OnEnded: Destroy everything
```

## Step 1: Enable Custom UI in InitParam

```cpp
InitParam initParam;
initParam.strWebDomain = L"https://zoom.us";
initParam.emLanguageID = LANGUAGE_English;
initParam.enableLogByDefault = true;

// CRITICAL: This is what makes it Custom UI mode
initParam.obConfigOpts.optionalFeatures = ENABLE_CUSTOMIZED_UI_FLAG;

SDKError err = InitSDK(initParam);
```

## Step 2: Create the Custom UI Manager (on CONNECTING)

When `onMeetingStatusChanged` fires with `MEETING_STATUS_CONNECTING`, create your window and the Custom UI manager:

```cpp
#include <customized_ui/zoom_customized_ui.h>
#include <customized_ui/customized_ui_mgr.h>
#include <customized_ui/customized_video_container.h>
#include <customized_ui/customized_share_render.h>

ICustomizedUIMgr* pCustomUIMgr = nullptr;
ICustomizedVideoContainer* pVideoContainer = nullptr;

// Create the manager (global SDK function)
SDKError err = CreateCustomizedUIMgr(&pCustomUIMgr);

// Optional: check license (log warning, don't abort)
err = pCustomUIMgr->HasLicense();
if (err != SDKERR_SUCCESS) {
    std::cout << "WARNING: HasLicense returned " << err << std::endl;
}

// Register for destroy notifications
pCustomUIMgr->SetEvent(&myUIMgrEventListener);

// Create video container inside your Win32 window
RECT rc;
::GetClientRect(hMyWindow, &rc);
err = pCustomUIMgr->CreateVideoContainer(&pVideoContainer, hMyWindow, rc);

pVideoContainer->SetEvent(&myVideoContainerEventListener);
pVideoContainer->Show();
pVideoContainer->SetBkColor(RGB(30, 30, 30)); // Dark background
```

## Step 3: Create Video Elements (on IN_MEETING)

When `onMeetingStatusChanged` fires with `MEETING_STATUS_INMEETING`:

### Active Speaker Element (auto-follows current speaker)

```cpp
IVideoRenderElement* pElement = nullptr;
err = pVideoContainer->CreateVideoElement(&pElement, VideoRenderElement_ACTIVE);

IActiveVideoRenderElement* pActive = dynamic_cast<IActiveVideoRenderElement*>(pElement);
RECT activeRect = { 0, 0, windowWidth, (int)(windowHeight * 0.7) };
pActive->SetPos(activeRect);
pActive->Show();
pActive->Start();  // Begin auto-tracking active speaker
```

### Normal Elements (specific participants)

```cpp
IMeetingParticipantsController* pParticipants =
    pMeetingService->GetMeetingParticipantsController();
IList<unsigned int>* pUserList = pParticipants->GetParticipantsList();

for (int i = 0; i < pUserList->GetCount() && i < MAX_GALLERY; i++) {
    unsigned int userId = pUserList->GetItem(i);

    IVideoRenderElement* pNormElement = nullptr;
    err = pVideoContainer->CreateVideoElement(&pNormElement, VideoRenderElement_NORMAL);

    INormalVideoRenderElement* pNormal =
        dynamic_cast<INormalVideoRenderElement*>(pNormElement);

    pNormal->Subscribe(userId);
    pNormal->SetResolution(VideoRenderResolution_360p);
    pNormal->Show();

    // Position in gallery strip
    int elemWidth = windowWidth / galleryCount;
    RECT r = { i * elemWidth, galleryTop, (i+1) * elemWidth, windowHeight };
    pNormal->SetPos(r);
}
```

## Step 4: Handle Layout

Respond to `onLayoutNotification` and `WM_SIZE` to re-layout elements:

```cpp
void LayoutVideoElements() {
    RECT clientRect;
    ::GetClientRect(hMyWindow, &clientRect);
    int totalWidth = clientRect.right - clientRect.left;
    int totalHeight = clientRect.bottom - clientRect.top;

    // Resize container to fill window
    pVideoContainer->Resize(clientRect);

    if (galleryElements.empty()) {
        // Active speaker only — full window
        RECT activeRect = { 0, 0, totalWidth, totalHeight };
        pActiveElement->SetPos(activeRect);
    } else {
        // Active speaker: top 70%, gallery: bottom 30%
        int activeHeight = (int)(totalHeight * 0.7);
        RECT activeRect = { 0, 0, totalWidth, activeHeight };
        pActiveElement->SetPos(activeRect);

        int elemWidth = totalWidth / (int)galleryElements.size();
        for (int i = 0; i < galleryElements.size(); i++) {
            RECT r = { i * elemWidth, activeHeight, (i+1) * elemWidth, totalHeight };
            galleryElements[i]->SetPos(r);
        }
    }
}
```

## Step 5: Handle Screen Sharing

```cpp
// Create share render (hidden until someone shares)
ICustomizedShareRender* pShareRender = nullptr;
RECT rc;
::GetClientRect(hMyWindow, &rc);
pCustomUIMgr->CreateShareRender(&pShareRender, hMyWindow, rc);
pShareRender->SetEvent(&myShareEventListener);
pShareRender->Hide();

// In ShareRenderEventListener:
void onSharingSourceNotification(unsigned int nShareSourceID) {
    if (nShareSourceID > 0) {
        pShareRender->SetShareSourceID(nShareSourceID);
        pShareRender->SetViewMode(CSM_FULLFILL);
        pShareRender->Show();
    } else {
        pShareRender->Hide();
    }
}
```

## Step 6: Cleanup (on meeting end)

```cpp
void Cleanup() {
    if (pVideoContainer) {
        pVideoContainer->DestroyAllVideoElement();
        pCustomUIMgr->DestroyVideoContainer(pVideoContainer);
        pVideoContainer = nullptr;
    }
    if (pShareRender) {
        pCustomUIMgr->DestroyShareRender(pShareRender);
        pShareRender = nullptr;
    }
    if (pCustomUIMgr) {
        DestroyCustomizedUIMgr(pCustomUIMgr);
        pCustomUIMgr = nullptr;
    }
    if (hMyWindow) {
        DestroyWindow(hMyWindow);
        hMyWindow = nullptr;
    }
}
```

## Complete Event Listener Implementations

See [Interface Methods Reference](../references/interface-methods.md) for the full list of required virtual methods for:
- `ICustomizedUIMgrEvent` (3 methods)
- `ICustomizedVideoContainerEvent` (6 methods)
- `ICustomizedShareRenderEvent` (3 methods)

## Required SDK Headers

```cpp
#include <windows.h>
#include <cstdint>
#include <zoom_sdk.h>
#include <customized_ui/zoom_customized_ui.h>          // CreateCustomizedUIMgr()
#include <customized_ui/customized_ui_mgr.h>           // ICustomizedUIMgr, ICustomizedUIMgrEvent
#include <customized_ui/customized_video_container.h>   // ICustomizedVideoContainer, elements
#include <customized_ui/customized_share_render.h>      // ICustomizedShareRender
#include <meeting_service_interface.h>
#include <meeting_service_components/meeting_audio_interface.h>          // Before participants!
#include <meeting_service_components/meeting_participants_ctrl_interface.h>
```

## Key Gotchas

1. **Create Custom UI on CONNECTING, not IN_MEETING** — the SDK needs the video container ready before it starts rendering
2. **Active element needs `Start()`** — `Show()` alone is not enough, you must call `Start()` to begin active speaker tracking
3. **Normal elements need `Subscribe(userId)`** — without this they show nothing
4. **`SetPos()` coordinates are relative to container**, not screen or parent window
5. **`Resize()` the container when window resizes** — or the D3D surface won't match the window
6. **Destroy order matters** — elements first, then container, then manager

---

**See also:**
- [Custom UI Architecture](../concepts/custom-ui-architecture.md) — How rendering works internally
- [Two Approaches: SDK-Rendered vs Self-Rendered](../concepts/custom-ui-vs-raw-data.md)
- [Raw Video Capture](raw-video-capture.md) — For self-rendered approach
