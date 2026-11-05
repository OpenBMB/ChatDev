# Custom UI Architecture — How It Actually Works

> **Skill**: Zoom Meeting SDK (Windows)
> **Category**: Concepts
> **Prerequisite**: [SDK Architecture Pattern](sdk-architecture-pattern.md)

## Overview

Custom UI mode lets you create your OWN meeting window instead of the SDK's default meeting UI. The SDK renders video into your window using Direct3D, but you control all layout, window management, and UI elements.

**This is NOT "HWND hijacking."** The SDK creates child windows inside your parent window and renders into those using its own D3D pipeline. Your window and WndProc remain untouched.

## Enabling Custom UI Mode

Set `ENABLE_CUSTOMIZED_UI_FLAG` during SDK initialization:

```cpp
InitParam initParam;
initParam.strWebDomain = L"https://zoom.us";
initParam.emLanguageID = LANGUAGE_English;

// CRITICAL: Enable Custom UI mode
initParam.obConfigOpts.optionalFeatures = ENABLE_CUSTOMIZED_UI_FLAG;

SDKError err = InitSDK(initParam);
```

Without this flag, the SDK creates its own default meeting window. With it, the SDK creates NO UI — you must provide everything.

## Internal Architecture

```
Your Window (WS_OVERLAPPEDWINDOW) — you own this, your WndProc
  |
  +-- [SDK Child HWND] — created internally by CreateVideoContainer()
       |   - SDK owns the WndProc
       |   - D3D11 swap chain bound to this child HWND
       |   - Composites all video onto one surface
       |
       +-- VideoElement: Active   (logical RECT region, NOT a window)
       +-- VideoElement: Normal0  (logical RECT region, NOT a window)
       +-- VideoElement: Normal1  (logical RECT region, NOT a window)
       +-- ...
  |
  +-- [SDK Child HWND for Share] — created by CreateShareRender()
       |   - Separate D3D surface for screen share content
       |   - Requires HandleWindowsMoveMsg() for DWM resync
```

### Key architectural facts

1. **`CreateVideoContainer(hParentWnd, rc)`** — SDK creates a **child HWND** inside your parent. You never see or manage this child HWND directly.

2. **Video elements are NOT separate windows** — they are **logical render regions** within a single D3D surface. `SetPos(RECT)` tells the SDK's compositor where to place each video texture within the container.

3. **Your app does ZERO rendering** — no `WM_PAINT`, no GDI calls, no `BitBlt`. The SDK handles 100% of video drawing internally.

## Rendering Technology

The SDK supports multiple rendering backends, configurable via `InitParam.renderOpts.videoRenderMode`:

```cpp
enum ZoomSDKVideoRenderMode {
    ZoomSDKVideoRenderMode_None = 0,       // Auto (default)
    ZoomSDKVideoRenderMode_Auto,
    ZoomSDKVideoRenderMode_D3D11EnableFLIP, // D3D11 with DXGI flip model (best)
    ZoomSDKVideoRenderMode_D3D11,           // D3D11 standard
    ZoomSDKVideoRenderMode_D3D9,            // D3D9 fallback
    ZoomSDKVideoRenderMode_GDI,             // GDI software fallback (VMs)
};
```

**Hierarchy**: D3D11 FLIP > D3D11 > D3D9 > GDI

The D3D11 FLIP model uses `DXGI_SWAP_EFFECT_FLIP_SEQUENTIAL` — this requires a dedicated child HWND (further confirming the child window architecture).

## Why onWindowMsgNotification Exists

The SDK's child HWND has its own WndProc that **intercepts input messages**. Your parent window's WndProc never sees mouse/keyboard events that land on the video area. The SDK forwards them back to you through callbacks:

```
Forwarded messages:
  WM_MOUSEMOVE, WM_MOUSEENTER, WM_MOUSELEAVE,
  WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONUP,
  WM_LBUTTONDBLCLK, WM_KEYDOWN
```

If you need to handle clicks on the video (e.g., click a participant to select them), you must handle them in `onWindowMsgNotification`, not in your parent WndProc.

## Why HandleWindowsMoveMsg() Exists (Share Render Only)

```cpp
// On ICustomizedShareRender only
virtual SDKError HandleWindowsMoveMsg() = 0;
```

When using Direct3D, the swap chain's presentation is tied to the window's screen position via DWM (Desktop Window Manager) composition. When the parent window moves:

1. Child HWND moves with it automatically
2. BUT the D3D swap chain may not update its DWM surface coordinates immediately
3. This causes "ghost frame" / "stale composition" artifacts

`HandleWindowsMoveMsg()` tells the SDK to force re-present at the new coordinates.

**This only exists on `ICustomizedShareRender`**, not on `ICustomizedVideoContainer` — the video container likely handles this internally or uses the FLIP model which doesn't have this issue.

## HasLicense() Check

The `ICustomizedUIMgr` interface has a `HasLicense()` method. The official SDK demo checks it as a hard gate:

```cpp
SDKError err = m_pCustomUIMgr->HasLicense();
if (err != SDKERR_SUCCESS) {
    // Demo aborts here
}
```

In practice, modern SDK licenses may include Custom UI by default. It's safe to log a warning but continue if it fails — the SDK will return errors on actual API calls if the license is truly missing.

## Custom UI Object Lifecycle

### Creation order (during meeting connect):
1. `CreateCustomizedUIMgr(&pMgr)` — global, creates the manager
2. `pMgr->SetEvent(&listener)` — register for destroy notifications
3. `pMgr->CreateVideoContainer(&pContainer, hParentWnd, rc)` — creates the rendering surface
4. `pContainer->SetEvent(&containerListener)` — register for layout/render events
5. `pContainer->Show()` / `SetBkColor()` — configure appearance
6. `pContainer->CreateVideoElement(&pElement, type)` — create render slots

### Destruction order (when meeting ends):
1. `pContainer->DestroyAllVideoElement()` — remove all render slots
2. `pMgr->DestroyVideoContainer(pContainer)` — destroy the rendering surface
3. `pMgr->DestroyShareRender(pShareRender)` — destroy share render if created
4. `DestroyCustomizedUIMgr(pMgr)` — global cleanup

### Important: The SDK may also destroy containers on its own (e.g., meeting ends). That's why `ICustomizedUIMgrEvent` has `onVideoContainerDestroyed` and `onShareRenderDestroyed` callbacks — so you can null out your pointers.

## Video Element Types

### Active Speaker Element (`VideoRenderElement_ACTIVE`)
- Auto-follows whoever is currently speaking
- No need to subscribe to a specific user
- Call `Start()` to begin, `Stop()` to pause

```cpp
IVideoRenderElement* pElement = nullptr;
pContainer->CreateVideoElement(&pElement, VideoRenderElement_ACTIVE);
IActiveVideoRenderElement* pActive = dynamic_cast<IActiveVideoRenderElement*>(pElement);
pActive->SetPos(rect);
pActive->Show();
pActive->Start();
```

### Normal Element (`VideoRenderElement_NORMAL`)
- Shows a specific participant's video
- Must call `Subscribe(userId)` to bind it to a user
- Set resolution with `SetResolution()`

```cpp
IVideoRenderElement* pElement = nullptr;
pContainer->CreateVideoElement(&pElement, VideoRenderElement_NORMAL);
INormalVideoRenderElement* pNormal = dynamic_cast<INormalVideoRenderElement*>(pElement);
pNormal->Subscribe(userId);
pNormal->SetResolution(VideoRenderResolution_360p);
pNormal->SetPos(rect);
pNormal->Show();
```

### Preview Element (`VideoRenderElement_PREVIEW`)
- Shows the local camera preview before joining
- Used for pre-meeting camera setup

## Layout Management

Video element positions are **RECTs relative to the container's client area**, not screen coordinates.

When the container receives `onLayoutNotification(RECT wnd_client_rect)`, you should recalculate and re-apply all element positions:

```cpp
void OnLayoutNotification(RECT clientRect) {
    int width = clientRect.right - clientRect.left;
    int height = clientRect.bottom - clientRect.top;

    // Active speaker: top 70%
    RECT activeRect = { 0, 0, width, (int)(height * 0.7) };
    pActiveElement->SetPos(activeRect);

    // Gallery: bottom 30%, evenly split horizontally
    int galleryTop = (int)(height * 0.7);
    int elemWidth = width / galleryCount;
    for (int i = 0; i < galleryCount; i++) {
        RECT r = { i * elemWidth, galleryTop, (i+1) * elemWidth, height };
        normalElements[i]->SetPos(r);
    }
}
```

## Share Render

The share render is a **separate SDK child window** for displaying screen shares:

```cpp
pMgr->CreateShareRender(&pShareRender, hParentWnd, rc);
pShareRender->SetEvent(&shareListener);
pShareRender->Hide(); // Hidden until someone shares

// When sharing starts (via onSharingSourceNotification):
pShareRender->SetShareSourceID(shareSourceID);
pShareRender->Show();
pShareRender->SetViewMode(CSM_FULLFILL); // or CSM_LETTER_BOX
```

## Relevant SDK DLLs

- `zVideoUI.dll`, `zVideoApp.dll`, `zVideoAppFrame.dll` — core video rendering
- `avcodec_zm-59.dll`, `avutil_zm-57.dll`, `swscale_zm-6.dll` — FFmpeg decoders
- `clDNN64.dll`, `mkldnn.dll` — Intel DNN for AI features (background blur, etc.)

---

**See also:**
- [Custom UI Working Code Example](../examples/custom-ui-video-rendering.md)
- [Two Approaches: SDK-Rendered vs Self-Rendered](custom-ui-vs-raw-data.md)
- [Custom UI Interface Methods](../references/interface-methods.md)
