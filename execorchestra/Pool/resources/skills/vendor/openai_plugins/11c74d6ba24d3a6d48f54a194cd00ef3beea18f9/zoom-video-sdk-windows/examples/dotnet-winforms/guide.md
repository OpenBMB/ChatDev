# UI Integration Guide for Zoom Video SDK Windows

This guide covers three different UI approaches for integrating the Zoom Video SDK:

1. **Win32 (Native C++)** - Direct SDK usage, no wrapper
2. **WinForms (C# .NET)** - Requires C++/CLI wrapper
3. **WPF (C# .NET)** - Requires C++/CLI wrapper + BitmapSource conversion

## Quick Comparison

| Aspect | Win32 | WinForms | WPF |
|--------|-------|----------|-----|
| **Language** | C++ | C# | C# |
| **Wrapper Required** | No | Yes (C++/CLI) | Yes (C++/CLI) |
| **Video Rendering** | Canvas API (SDK renders) | Raw Data Pipe (you render) | Raw Data Pipe + BitmapSource |
| **Performance** | Best | Good | Good (extra conversion) |
| **Complexity** | Medium | Medium | Higher |
| **UI Threading** | Win32 message loop | `InvokeRequired` | `Dispatcher` |

---

## Option 1: Win32 (Native C++) - Direct SDK

**No wrapper needed.** The SDK is native C++, so Win32 apps use it directly.

### Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Win32 Dialog  │────►│  Native C++ SDK │
│   (main.cpp)    │◄────│  (videosdk.dll) │
└─────────────────┘     └─────────────────┘
       HWND              Canvas API
```

### Key Patterns

#### 1. SDK Manager Class (Native C++)

```cpp
// ZoomSDKManager.h
class ZoomSDKManager {
private:
    IZoomVideoSDK* m_pZoomSDK;
    IZoomVideoSDKSession* m_pSession;
    CustomZoomDelegate* m_pDelegate;

public:
    bool Initialize();
    bool JoinSession(const std::string& name, const std::string& token, ...);
    bool StartVideo();
    bool StartVideoPreview(HWND hwnd);  // Canvas API!
    bool SubscribeRemoteVideo(HWND hwnd, const std::string& userId);
};
```

#### 2. Delegate Implementation (All 80+ Callbacks)

```cpp
class CustomZoomDelegate : public IZoomVideoSDKDelegate {
private:
    ZoomSDKManager* m_pManager;

public:
    void onSessionJoin() override {
        m_pManager->OnSessionStatusChanged(SessionStatus::InSession, "Joined");
    }

    void onUserVideoStatusChanged(IZoomVideoSDKVideoHelper* helper,
                                  IVideoSDKVector<IZoomVideoSDKUser*>* userList) override {
        // Handle video status changes
    }

    // ... implement all 80+ callbacks
};
```

#### 3. Video Rendering with Canvas API (SDK-Rendered)

```cpp
// Start video preview - SDK renders directly to HWND
bool ZoomSDKManager::StartVideoPreview(HWND hwnd) {
    IZoomVideoSDKVideoHelper* videoHelper = m_pZoomSDK->getVideoHelper();

    // SDK renders directly to the window handle
    ZoomVideoSDKErrors ret = videoHelper->startVideoCanvasPreview(hwnd);
    return ret == ZoomVideoSDKErrors_Success;
}

// Subscribe to remote user's video
bool ZoomSDKManager::SubscribeRemoteVideo(HWND hwnd, const std::string& userId) {
    IZoomVideoSDKSession* session = m_pZoomSDK->getSessionInfo();
    IVideoSDKVector<IZoomVideoSDKUser*>* userList = session->getRemoteUsers();

    for (int i = 0; i < userList->GetCount(); i++) {
        IZoomVideoSDKUser* user = userList->GetItem(i);
        IZoomVideoSDKCanvas* canvas = user->GetVideoCanvas();

        // SDK renders remote video directly to HWND
        canvas->subscribeWithView(hwnd, ZoomVideoSDKVideoAspect_Original, ZoomVideoSDKResolution_Auto);
    }
    return true;
}
```

#### 4. Win32 Dialog with Video Panels

```cpp
// main.cpp - Dialog procedure
INT_PTR CALLBACK MainDialogProc(HWND hDlg, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
    case WM_INITDIALOG:
        InitializeZoomSDK();
        PopulateDeviceLists(hDlg);
        return TRUE;

    case WM_COMMAND:
        switch (LOWORD(wParam)) {
        case IDC_START_VIDEO:
            g_pSDKManager->StartVideo();

            // Get HWND of video panel control
            HWND selfVideoHwnd = GetDlgItem(hDlg, IDC_SELF_VIDEO);
            g_pSDKManager->StartVideoPreview(selfVideoHwnd);

            HWND remoteVideoHwnd = GetDlgItem(hDlg, IDC_REMOTE_VIDEO);
            g_pSDKManager->SubscribeRemoteVideo(remoteVideoHwnd, "");
            break;
        }
    }
    return FALSE;
}
```

### Win32 Flow Summary

```
1. CreateZoomVideoSDKObj()
2. Initialize SDK with params
3. Create & register CustomZoomDelegate
4. Join session
5. On IDC_START_VIDEO click:
   - startVideo() → transmit your camera
   - startVideoCanvasPreview(selfHwnd) → see yourself
   - subscribeWithView(remoteHwnd) → see others
6. SDK renders directly to HWNDs
```

### Sample Location
```
C:\tempsdk\videosdk-windows-dotnet-desktop-framework-quickstart\
  └── ZoomVideoSDK.Win32\
      ├── main.cpp              # Win32 dialog + event handlers
      ├── ZoomSDKManager.cpp    # SDK wrapper class
      ├── ZoomSDKManager.h      # Header with delegate
      └── main.rc               # Dialog resources
```

---

## Option 2: WinForms (C# + C++/CLI Wrapper)

**Requires C++/CLI bridge** because Zoom SDK is native C++.

### Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   C# WinForms   │────►│  C++/CLI Wrapper│────►│  Native C++ SDK │
│   (MainForm.cs) │◄────│  (ZoomSDKManager)│◄────│  (videosdk.dll) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
     Events              gcroot<T^>               Callbacks
     Bitmap^             YUV→RGB                  YUVRawDataI420
```

### Key Patterns

#### 1. C++/CLI Wrapper Class

```cpp
// ZoomSDKManager.h (C++/CLI)
public ref class ZoomSDKManager {
private:
    void* m_pVideoSDK;              // Hide native types
    void* m_pSessionHandler;        // Native callback handler

public:
    // Managed events for C# consumption
    event EventHandler<SessionStatusEventArgs^>^ SessionStatusChanged;
    event EventHandler<VideoFrameEventArgs^>^ PreviewVideoReceived;
    event EventHandler<VideoFrameEventArgs^>^ RemoteVideoReceived;

    bool Initialize();
    bool JoinSession(String^ name, String^ token, String^ user, String^ pw);
    bool StartVideo();
};
```

#### 2. Native Callback → Managed Event (gcroot pattern)

```cpp
// Native handler stores managed reference via gcroot
class VideoPreviewHandler : public IZoomVideoSDKRawDataPipeDelegate {
private:
    gcroot<ZoomSDKManager^> m_managedHandler;  // Prevents GC

public:
    VideoPreviewHandler(ZoomSDKManager^ handler) : m_managedHandler(handler) {}

    void onRawDataFrameReceived(YUVRawDataI420* data) override {
        ZoomSDKManager^ handler = static_cast<ZoomSDKManager^>(m_managedHandler);
        if (handler && data) {
            // Convert YUV to Bitmap
            Bitmap^ bitmap = handler->ConvertYUVToBitmap(
                data->GetYBuffer(), data->GetUBuffer(), data->GetVBuffer(),
                data->GetStreamWidth(), data->GetStreamHeight(), ...);

            // Fire managed event
            handler->OnPreviewVideoReceived(bitmap);
        }
    }
};
```

#### 3. YUV→RGB Conversion (LockBits for Performance)

```cpp
Bitmap^ ZoomSDKManager::ConvertYUVToBitmap(char* yBuffer, char* uBuffer, char* vBuffer,
                                           int width, int height, ...) {
    Bitmap^ bitmap = gcnew Bitmap(width, height, PixelFormat::Format24bppRgb);

    // Lock for direct memory access (100x faster than SetPixel)
    BitmapData^ data = bitmap->LockBits(rect, ImageLockMode::WriteOnly, ...);
    unsigned char* rgbPtr = (unsigned char*)data->Scan0.ToPointer();

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            // YUV420 → RGB (ITU-R BT.601)
            int Y = yBuffer[y * yStride + x];
            int U = uBuffer[(y/2) * uStride + (x/2)];
            int V = vBuffer[(y/2) * vStride + (x/2)];

            int R = (298 * (Y-16) + 409 * (V-128) + 128) >> 8;
            int G = (298 * (Y-16) - 100 * (U-128) - 208 * (V-128) + 128) >> 8;
            int B = (298 * (Y-16) + 516 * (U-128) + 128) >> 8;

            // Write BGR (bitmap format)
            rgbPtr[y * stride + x * 3 + 0] = (byte)B;
            rgbPtr[y * stride + x * 3 + 1] = (byte)G;
            rgbPtr[y * stride + x * 3 + 2] = (byte)R;
        }
    }

    bitmap->UnlockBits(data);
    return bitmap;
}
```

#### 4. C# Consumer (WinForms)

```csharp
// MainForm.cs
public partial class MainForm : Form {
    private ZoomSDKInterop _zoomSDK;

    public MainForm() {
        InitializeComponent();
        InitializeZoomSDK();
    }

    private void InitializeZoomSDK() {
        _zoomSDK = new ZoomSDKInterop();

        // Subscribe to events
        _zoomSDK.SessionJoined += OnSessionJoined;
        _zoomSDK.PreviewVideoReceived += OnPreviewVideo;
        _zoomSDK.RemoteVideoReceived += OnRemoteVideo;

        _zoomSDK.Initialize();
    }

    private void OnPreviewVideo(object sender, VideoFrameEventArgs e) {
        // Must marshal to UI thread
        if (InvokeRequired) {
            BeginInvoke(new Action(() => OnPreviewVideo(sender, e)));
            return;
        }

        // Display bitmap in PictureBox
        _selfVideoPanel.Image?.Dispose();
        _selfVideoPanel.Image = e.Frame;
    }
}
```

### WinForms Flow Summary

```
C# Layer:
1. new ZoomSDKInterop() → creates C++/CLI ZoomSDKManager
2. Subscribe to events (SessionJoined, PreviewVideoReceived, etc.)
3. _zoomSDK.Initialize() → SDK init
4. _zoomSDK.JoinSession(...) → join
5. _zoomSDK.StartVideo() → start camera + preview

C++/CLI Layer:
1. Creates native SDK via CreateZoomVideoSDKObj()
2. Creates VideoPreviewHandler with gcroot<ZoomSDKManager^>
3. Starts Raw Data Pipe subscription
4. onRawDataFrameReceived → YUV→RGB → fires PreviewVideoReceived event

C# Layer (UI Thread):
1. OnPreviewVideo receives Bitmap
2. Checks InvokeRequired for thread safety
3. Sets PictureBox.Image = bitmap
```

### Sample Location
```
C:\tempsdk\videosdk-windows-dotnet-desktop-framework-quickstart\
  ├── ZoomVideoSDK.Wrapper\         # C++/CLI Bridge
  │   ├── ZoomSDKManager.h          # Managed class definition
  │   └── ZoomSDKManager.cpp        # Native ↔ Managed bridge
  │
  └── ZoomVideoSDK.WinForms\        # C# WinForms App
      ├── ZoomSDKInterop.cs         # High-level C# wrapper
      ├── MainForm.cs               # UI + event handlers
      └── Program.cs                # Entry point
```

---

## Option 3: WPF (C# + C++/CLI Wrapper)

**Same C++/CLI wrapper as WinForms**, but with additional WPF-specific handling.

### Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    C# WPF       │────►│  C# Interop     │────►│  C++/CLI Wrapper│────►│  Native C++ SDK │
│  (MainWindow)   │◄────│  (ZoomSDKInterop)│◄────│  (ZoomSDKManager)│◄────│  (videosdk.dll) │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
     BitmapSource        Bitmap→BitmapSource     gcroot<T^>              Callbacks
     Dispatcher          Conversion              YUV→RGB                 YUVRawDataI420
```

### Key Differences from WinForms

| Aspect | WinForms | WPF |
|--------|----------|-----|
| **Video Type** | `System.Drawing.Bitmap` | `System.Windows.Media.Imaging.BitmapSource` |
| **UI Thread** | `InvokeRequired` + `BeginInvoke` | `Dispatcher.CheckAccess()` + `Dispatcher.BeginInvoke` |
| **Image Control** | `PictureBox.Image` | `Image.Source` |
| **Extra Step** | None | Bitmap → BitmapSource conversion |

### Key Patterns

#### 1. WPF-Specific Event Args

```csharp
// WPF uses BitmapSource instead of Bitmap
public class VideoFrameEventArgs : EventArgs {
    public BitmapSource Frame { get; set; }  // WPF type
    public string UserId { get; set; }
}
```

#### 2. Bitmap → BitmapSource Conversion

```csharp
// ZoomSDKInterop.cs (WPF version)
private BitmapSource ConvertBitmapToBitmapSource(Bitmap bitmap) {
    if (bitmap == null) return null;

    using (var memory = new MemoryStream()) {
        bitmap.Save(memory, System.Drawing.Imaging.ImageFormat.Png);
        memory.Position = 0;

        var bitmapImage = new BitmapImage();
        bitmapImage.BeginInit();
        bitmapImage.StreamSource = memory;
        bitmapImage.CacheOption = BitmapCacheOption.OnLoad;
        bitmapImage.EndInit();
        bitmapImage.Freeze();  // Make thread-safe for WPF

        return bitmapImage;
    }
}

// Event handler bridges C++/CLI Bitmap to WPF BitmapSource
_sdkManager.PreviewVideoReceived += (sender, e) => {
    var wpfFrame = ConvertBitmapToBitmapSource(e.Frame);
    PreviewVideoReceived?.Invoke(this, new VideoFrameEventArgs(wpfFrame, "self"));
};
```

#### 3. WPF Dispatcher for UI Thread

```csharp
// MainWindow.xaml.cs
private void OnPreviewVideoReceived(object sender, VideoFrameEventArgs e) {
    // WPF uses Dispatcher instead of InvokeRequired
    if (!Dispatcher.CheckAccess()) {
        Dispatcher.BeginInvoke(new Action<object, VideoFrameEventArgs>(OnPreviewVideoReceived), sender, e);
        return;
    }

    // Frame throttling (~30fps)
    if (DateTime.Now - _lastPreviewVideoUpdate < _videoUpdateInterval) return;
    _lastPreviewVideoUpdate = DateTime.Now;

    if (e.Frame != null) {
        SelfVideoImage.Source = e.Frame;  // WPF Image control
    }
}
```

#### 4. Alternative: WriteableBitmap (Higher Performance)

For better performance, you can write directly to WriteableBitmap:

```csharp
private BitmapSource CreateErrorBitmapSource(int width, int height, string message) {
    var writeableBitmap = new WriteableBitmap(width, height, 96, 96, PixelFormats.Bgr24, null);
    writeableBitmap.Lock();

    unsafe {
        byte* backBuffer = (byte*)writeableBitmap.BackBuffer;
        int stride = writeableBitmap.BackBufferStride;

        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                byte* pixel = backBuffer + y * stride + x * 3;
                pixel[0] = 0;    // Blue
                pixel[1] = 0;    // Green
                pixel[2] = 255;  // Red
            }
        }
    }

    writeableBitmap.AddDirtyRect(new Int32Rect(0, 0, width, height));
    writeableBitmap.Unlock();
    writeableBitmap.Freeze();  // Thread-safe

    return writeableBitmap;
}
```

### WPF Flow Summary

```
Same as WinForms, with these differences:

C# WPF Interop Layer:
1. Receives Bitmap from C++/CLI wrapper
2. Converts Bitmap → BitmapSource (PNG stream or WriteableBitmap)
3. Calls Freeze() to make cross-thread safe
4. Fires WPF-compatible event

MainWindow (UI Thread):
1. OnPreviewVideoReceived receives BitmapSource
2. Checks Dispatcher.CheckAccess() for thread safety
3. Sets Image.Source = bitmapSource
```

### Sample Location
```
C:\tempsdk\videosdk-windows-dotnet-desktop-framework-quickstart\
  ├── ZoomVideoSDK.Wrapper\         # C++/CLI Bridge (shared with WinForms)
  │   ├── ZoomSDKManager.h
  │   └── ZoomSDKManager.cpp
  │
  └── ZoomVideoSDK.WPF\             # C# WPF App
      ├── ZoomSDKInterop.cs         # WPF-specific interop (BitmapSource)
      ├── MainWindow.xaml           # XAML layout
      ├── MainWindow.xaml.cs        # Code-behind with Dispatcher
      └── App.xaml                  # Application entry
```

---

## Decision Matrix

| If you need... | Use | Why |
|----------------|-----|-----|
| **Best performance** | Win32 | Canvas API, SDK renders directly |
| **C++ codebase** | Win32 | No interop overhead |
| **Existing WinForms app** | WinForms + C++/CLI | Natural integration |
| **Modern .NET UI** | WPF + C++/CLI | XAML, data binding |
| **Cross-platform .NET** | Consider Avalonia | WPF-like but cross-platform |

## C++/CLI Wrapper Patterns (For .NET Integration)

This section teaches **general C++/CLI wrapping patterns** applicable to ANY native C++ library.

### When to Use C++/CLI

| Scenario | Solution |
|----------|----------|
| Native C++ library → C# app | C++/CLI wrapper (this guide) |
| C library → C# app | P/Invoke (simpler, no wrapper needed) |
| COM library → C# app | COM Interop |
| .NET library → C++ app | Reverse P/Invoke or COM |

### Project Setup

1. **Create C++/CLI Class Library**:
   - Visual Studio → New Project → "CLR Class Library (.NET Framework)"
   - Or add `/clr` to existing C++ project

2. **Project Properties**:
   ```
   Configuration Properties → General:
   - Common Language Runtime Support: /clr
   - .NET Target Framework: v4.8

   C/C++ → General:
   - Additional Include Directories: path\to\native\sdk\include

   Linker → General:
   - Additional Library Directories: path\to\native\sdk\lib

   Linker → Input:
   - Additional Dependencies: native_sdk.lib
   ```

3. **File Structure**:
   ```
   MyWrapper/
   ├── MyWrapper.h         # Managed ref class definition
   ├── MyWrapper.cpp       # Implementation
   ├── NativeCallbacks.h   # Native callback classes with gcroot
   └── Stdafx.h            # Precompiled header
   ```

---

### Pattern 1: Basic Wrapper Structure

**Goal**: Expose native C++ class to C#

```cpp
// MyWrapper.h (C++/CLI)
#pragma once
#include <msclr\marshal_cppstd.h>  // For string conversion

using namespace System;
using namespace System::Runtime::InteropServices;

namespace MyLibraryWrapper {

    // Forward declare native types (hide from C#)
    class NativeClass;  // Don't #include native headers here!

    public ref class ManagedWrapper {
    private:
        NativeClass* m_pNative;  // Raw pointer to native object
        bool m_disposed;

    public:
        ManagedWrapper();
        ~ManagedWrapper();       // Destructor (IDisposable.Dispose)
        !ManagedWrapper();       // Finalizer (destructor fallback)

        // Managed methods that wrap native calls
        bool Initialize();
        void DoSomething(String^ param);
        String^ GetResult();
    };
}
```

```cpp
// MyWrapper.cpp
#include "stdafx.h"
#include "MyWrapper.h"
#include "native_sdk.h"  // Include native headers in .cpp only!

namespace MyLibraryWrapper {

    ManagedWrapper::ManagedWrapper() : m_pNative(nullptr), m_disposed(false) {
        m_pNative = new NativeClass();
    }

    ManagedWrapper::~ManagedWrapper() {
        this->!ManagedWrapper();  // Call finalizer
        m_disposed = true;
    }

    ManagedWrapper::!ManagedWrapper() {
        if (m_pNative) {
            delete m_pNative;
            m_pNative = nullptr;
        }
    }

    bool ManagedWrapper::Initialize() {
        if (!m_pNative) return false;
        return m_pNative->init() == 0;  // Native returns 0 for success
    }

    void ManagedWrapper::DoSomething(String^ param) {
        if (!m_pNative) return;

        // Convert managed String^ to native std::wstring
        std::wstring nativeParam = msclr::interop::marshal_as<std::wstring>(param);
        m_pNative->doSomething(nativeParam.c_str());
    }

    String^ ManagedWrapper::GetResult() {
        if (!m_pNative) return nullptr;

        // Convert native wchar_t* to managed String^
        const wchar_t* result = m_pNative->getResult();
        return result ? gcnew String(result) : nullptr;
    }
}
```

---

### Pattern 2: Opaque void* Pointers

**Goal**: Hide native types from managed headers (prevents header dependency leaks)

```cpp
// In .h file - use void* to hide native types
private:
    void* m_pNativeSDK;     // Actually INativeSDK*
    void* m_pNativeSession; // Actually INativeSession*

// In .cpp file - cast back to real types
bool ManagedWrapper::JoinSession() {
    INativeSDK* sdk = static_cast<INativeSDK*>(m_pNativeSDK);
    INativeSession* session = sdk->joinSession(...);
    m_pNativeSession = static_cast<void*>(session);
    return session != nullptr;
}
```

**Why**: Native SDK headers often have complex dependencies. Using `void*` means you only need to `#include` native headers in the `.cpp` file, not the `.h` file. This prevents compile errors in consuming C# projects.

---

### Pattern 3: gcroot<T^> for Native→Managed Callbacks

**Goal**: Native code needs to call back into managed code

```cpp
// NativeCallbacks.h
#pragma once
#include <vcclr.h>  // For gcroot

// Forward declare the managed class
namespace MyLibraryWrapper { ref class ManagedWrapper; }

// Native class that implements SDK callback interface
class NativeEventHandler : public INativeEventListener {
private:
    gcroot<MyLibraryWrapper::ManagedWrapper^> m_managed;  // GC-safe ref

public:
    NativeEventHandler(MyLibraryWrapper::ManagedWrapper^ wrapper)
        : m_managed(wrapper) {}

    // Native callback (called by SDK on background thread)
    void onEvent(int eventCode, const wchar_t* message) override {
        // Get managed reference (prevents GC during callback)
        MyLibraryWrapper::ManagedWrapper^ wrapper = m_managed;
        if (wrapper) {
            wrapper->FireManagedEvent(eventCode, gcnew String(message));
        }
    }

    void onDataReceived(const unsigned char* data, int length) override {
        MyLibraryWrapper::ManagedWrapper^ wrapper = m_managed;
        if (wrapper) {
            // Copy native data to managed array
            array<Byte>^ managedData = gcnew array<Byte>(length);
            Marshal::Copy(IntPtr((void*)data), managedData, 0, length);
            wrapper->FireDataEvent(managedData);
        }
    }
};
```

```cpp
// In ManagedWrapper.h - add events
public ref class ManagedWrapper {
public:
    // Managed events for C# consumption
    event EventHandler<EventArgs^>^ SomethingHappened;
    event EventHandler<DataEventArgs^>^ DataReceived;

internal:
    // Called by native callback handler
    void FireManagedEvent(int code, String^ message);
    void FireDataEvent(array<Byte>^ data);
};
```

**Critical**: `gcroot<T^>` prevents the .NET garbage collector from moving/collecting the managed object while native code holds a reference. Without it, callbacks will crash.

---

### Pattern 4: Destructor + Finalizer (IDisposable)

**Goal**: Guarantee native resource cleanup

```cpp
public ref class ManagedWrapper {
private:
    NativeClass* m_pNative;
    NativeEventHandler* m_pHandler;  // Must also be cleaned up
    bool m_disposed;

public:
    // Destructor - called by Dispose() or 'using' statement
    ~ManagedWrapper() {
        if (!m_disposed) {
            this->!ManagedWrapper();  // Call finalizer logic
            m_disposed = true;
            GC::SuppressFinalize(this);  // No need for finalizer now
        }
    }

    // Finalizer - called by GC if Dispose wasn't called
    !ManagedWrapper() {
        // Clean up in reverse order of creation
        if (m_pHandler) {
            delete m_pHandler;
            m_pHandler = nullptr;
        }
        if (m_pNative) {
            m_pNative->shutdown();  // SDK cleanup
            delete m_pNative;
            m_pNative = nullptr;
        }
    }
};
```

**C# Usage**:
```csharp
// Option 1: Explicit dispose
var wrapper = new ManagedWrapper();
try {
    wrapper.Initialize();
    // use wrapper...
} finally {
    wrapper.Dispose();  // Calls ~ManagedWrapper()
}

// Option 2: using statement (preferred)
using (var wrapper = new ManagedWrapper()) {
    wrapper.Initialize();
    // use wrapper...
}  // Dispose() called automatically
```

---

### Pattern 5: String Conversion

**Goal**: Convert between managed String^ and native strings

```cpp
#include <msclr\marshal_cppstd.h>

// Managed String^ → Native std::wstring
void SetName(String^ name) {
    std::wstring nativeName = msclr::interop::marshal_as<std::wstring>(name);
    m_pNative->setName(nativeName.c_str());
}

// Managed String^ → Native std::string (UTF-8)
void SetNameUtf8(String^ name) {
    std::string nativeName = msclr::interop::marshal_as<std::string>(name);
    m_pNative->setNameUtf8(nativeName.c_str());
}

// Native wchar_t* → Managed String^
String^ GetName() {
    const wchar_t* name = m_pNative->getName();
    return name ? gcnew String(name) : nullptr;
}

// Native char* (UTF-8) → Managed String^
String^ GetNameUtf8() {
    const char* name = m_pNative->getNameUtf8();
    return name ? gcnew String(name, 0, strlen(name), System::Text::Encoding::UTF8) : nullptr;
}
```

---

### Pattern 6: Array/Buffer Conversion

**Goal**: Pass binary data between managed and native code

```cpp
// Managed array → Native buffer
void SendData(array<Byte>^ data) {
    if (data == nullptr || data->Length == 0) return;

    // Pin the managed array (prevents GC from moving it)
    pin_ptr<Byte> pinned = &data[0];
    unsigned char* nativePtr = pinned;

    m_pNative->sendData(nativePtr, data->Length);
}
// pinned automatically unpins when out of scope

// Native buffer → Managed array
array<Byte>^ ReceiveData() {
    unsigned char* buffer = nullptr;
    int length = 0;

    m_pNative->receiveData(&buffer, &length);

    if (!buffer || length <= 0) return nullptr;

    array<Byte>^ result = gcnew array<Byte>(length);
    Marshal::Copy(IntPtr(buffer), result, 0, length);

    m_pNative->freeBuffer(buffer);  // SDK may require this
    return result;
}
```

---

### Pattern 7: Thread Marshaling (Native Thread → UI Thread)

**Goal**: Fire events safely when native callbacks occur on background threads

```cpp
// In native callback handler
void NativeEventHandler::onVideoFrame(YUVData* frame) {
    ManagedWrapper^ wrapper = m_managed;
    if (wrapper) {
        // Convert frame to managed Bitmap (still on native thread)
        Bitmap^ bitmap = wrapper->ConvertYUVToBitmap(frame);

        // Fire event - consumer must marshal to UI thread
        wrapper->FireVideoFrameEvent(bitmap);
    }
}
```

**C# Consumer (WinForms)**:
```csharp
wrapper.VideoFrameReceived += (sender, e) => {
    if (InvokeRequired) {
        BeginInvoke(new Action(() => pictureBox.Image = e.Frame));
    } else {
        pictureBox.Image = e.Frame;
    }
};
```

**C# Consumer (WPF)**:
```csharp
wrapper.VideoFrameReceived += (sender, e) => {
    if (!Dispatcher.CheckAccess()) {
        Dispatcher.BeginInvoke(new Action(() => image.Source = e.Frame));
    } else {
        image.Source = e.Frame;
    }
};
```

---

### Pattern 8: LockBits for Fast Image Manipulation

**Goal**: Convert image formats efficiently (e.g., YUV→RGB)

```cpp
Bitmap^ ConvertYUVToBitmap(unsigned char* yuvData, int width, int height) {
    Bitmap^ bitmap = gcnew Bitmap(width, height, PixelFormat::Format24bppRgb);

    // Lock bitmap memory for direct access (100x faster than SetPixel)
    Rectangle rect(0, 0, width, height);
    BitmapData^ data = bitmap->LockBits(rect, ImageLockMode::WriteOnly,
                                         PixelFormat::Format24bppRgb);

    unsigned char* rgbPtr = (unsigned char*)data->Scan0.ToPointer();
    int stride = data->Stride;  // May include padding!

    // YUV420 to RGB conversion
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            int yIndex = y * width + x;
            int uvIndex = (y / 2) * (width / 2) + (x / 2);

            int Y = yuvData[yIndex];
            int U = yuvData[width * height + uvIndex];
            int V = yuvData[width * height + (width/2)*(height/2) + uvIndex];

            // BT.601 conversion
            int C = Y - 16, D = U - 128, E = V - 128;
            int R = (298*C + 409*E + 128) >> 8;
            int G = (298*C - 100*D - 208*E + 128) >> 8;
            int B = (298*C + 516*D + 128) >> 8;

            // Clamp and write BGR (bitmap format)
            unsigned char* pixel = rgbPtr + y * stride + x * 3;
            pixel[0] = (B < 0) ? 0 : (B > 255) ? 255 : B;
            pixel[1] = (G < 0) ? 0 : (G > 255) ? 255 : G;
            pixel[2] = (R < 0) ? 0 : (R > 255) ? 255 : R;
        }
    }

    bitmap->UnlockBits(data);
    return bitmap;
}
```

---

### Complete Wrapper Checklist

When wrapping ANY native C++ library:

```
[ ] Project: C++/CLI Class Library with /clr enabled
[ ] Headers: Native includes in .cpp only, void* in .h
[ ] Lifecycle: Destructor (~) + Finalizer (!) pattern
[ ] Callbacks: gcroot<T^> in native handler classes
[ ] Strings: marshal_as<std::wstring> or gcnew String()
[ ] Arrays: pin_ptr for managed→native, Marshal::Copy for native→managed
[ ] Threading: Document which thread callbacks fire on
[ ] Cleanup: Delete native objects in reverse order of creation
[ ] Events: C# events for callbacks, document threading requirements
```

---

### Common Wrapper Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `LNK2020: unresolved token` | Missing native .lib | Add to Linker → Input → Additional Dependencies |
| `C3767: candidate function not accessible` | Exposing native types in public API | Use void* or wrap in managed class |
| `AccessViolationException` in callback | GC moved managed object | Use gcroot<T^> in native handler |
| `ObjectDisposedException` | Using wrapper after Dispose | Check m_disposed flag |
| `BadImageFormatException` | x86/x64 mismatch | Match Platform Target to native SDK |

---

## Production Quality Review

This section provides a detailed assessment of each sample against production standards.

### Overall Assessment Summary

| Sample | Quality | Issues | Production Ready |
|--------|---------|--------|------------------|
| **Win32** | Good | 4 minor | Yes (with fixes) |
| **C++/CLI Wrapper** | Good | 4 minor | Yes (with fixes) |
| **WinForms** | Good | 3 minor | Yes (with fixes) |
| **WPF** | Good | 4 minor | Yes (with fixes) |

---

### Win32 Sample (ZoomVideoSDK.Win32)

#### What's Good

| Check | Status | Notes |
|-------|--------|-------|
| All 80+ delegate callbacks | ✅ | Lines 17-358 in ZoomSDKManager.cpp |
| Null checks on SDK pointers | ✅ | Consistent throughout |
| Exception handling | ✅ | try/catch blocks on all SDK calls |
| Cleanup sequence | ✅ | leave → removeListener → cleanup → destroy |
| Canvas API usage | ✅ | `startVideoCanvasPreview`, `subscribeWithView` |
| Device enumeration | ✅ | Proper SDK interfaces |
| UTF-8 string conversion | ✅ | WideCharToMultiByte used correctly |

#### Issues Found

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| ⚠️ Medium | `audioOption.connect = true` during join | Line 489 | Set to `false`, call `startAudio()` in `onSessionJoin` callback |
| ⚠️ Low | Global pointer without thread safety | Line 22 main.cpp | Use mutex or make thread-local |
| ⚠️ Low | Arbitrary `Sleep(100)` after init | Lines 366-367 | Use callback-based readiness check |
| ⚠️ Low | No WM_DESTROY handler | main.cpp | Add cleanup in WM_DESTROY |

#### Recommended Fix: Audio Connection

```cpp
// BEFORE (current - problematic)
sessionContext.audioOption.connect = true;  // May miss audio callbacks

// AFTER (recommended)
sessionContext.audioOption.connect = false;

// Then in onSessionJoin callback:
void CustomZoomDelegate::onSessionJoin() {
    if (m_pManager) {
        // Now safe to connect audio
        IZoomVideoSDKAudioHelper* audioHelper = m_pManager->GetSDK()->getAudioHelper();
        audioHelper->startAudio();
    }
}
```

---

### C++/CLI Wrapper (ZoomVideoSDK.Wrapper)

#### What's Good

| Check | Status | Notes |
|-------|--------|-------|
| gcroot<T^> usage | ✅ | Lines 25, 40-41, 57 - prevents GC collection |
| Finalizer + Destructor pattern | ✅ | Lines 245-254 - proper C++/CLI cleanup |
| LockBits for YUV conversion | ✅ | Lines 831-880 - 100x faster than SetPixel |
| All 80+ delegate callbacks | ✅ | SimpleNativeHandler implements all |
| Error handling | ✅ | Status messages for all operations |
| Video preview cleanup | ✅ | StopVideoPreview cleans up handler |

#### Issues Found

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| ⚠️ Medium | `audioOption.connect = true` | Line 343 | Same fix as Win32 |
| ⚠️ Medium | `unSubscribe(nullptr)` | Line 987 | Pass actual delegate used for subscription |
| ⚠️ Medium | RemoteVideoHandler memory leak | Line 947 | Store handler, delete in UnsubscribeFromUserVideo |
| ⚠️ Low | Simplified stride calculation | Lines 1162, 1212 | Use `data->GetYStride()`, `GetUStride()`, `GetVStride()` |

#### Recommended Fix: Handler Memory Leak

```cpp
// ZoomSDKManager.h - Add member to track handlers
private:
    std::map<String^, RemoteVideoHandler*> m_remoteHandlers;

// In SubscribeToUserVideo
RemoteVideoHandler* remoteHandler = new RemoteVideoHandler(this, userId);
m_remoteHandlers[userId] = remoteHandler;  // Store for later cleanup

// In UnsubscribeFromUserVideo
if (m_remoteHandlers.ContainsKey(userId)) {
    RemoteVideoHandler* handler = m_remoteHandlers[userId];
    videoPipe->unSubscribe(handler);  // Pass actual handler
    delete handler;
    m_remoteHandlers.Remove(userId);
}
```

---

### WinForms Sample (ZoomVideoSDK.WinForms)

#### What's Good

| Check | Status | Notes |
|-------|--------|-------|
| Thread marshaling | ✅ | InvokeRequired + BeginInvoke throughout |
| Frame rate throttling | ✅ | 30fps limit prevents UI overload |
| Bitmap disposal | ✅ | `.Image?.Dispose()` before assignment |
| Form closing cleanup | ✅ | LeaveSession + Cleanup in OnFormClosing |
| JWT token decoder | ✅ | Proper Base64 URL-safe handling |
| Exception handling | ✅ | All operations wrapped in try/catch |

#### Issues Found

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| ⚠️ Medium | Missing IDisposable pattern | ZoomSDKInterop.cs | Add `~ZoomSDKInterop()` destructor |
| ⚠️ Low | Null check after Cleanup | Line 468-469 | Add `_sdkManager != null` check before events |
| ⚠️ Info | Duplicate YUV conversion | Lines 369-443 | Remove - wrapper already handles this |

#### Recommended Fix: IDisposable

```csharp
// ZoomSDKInterop.cs
public class ZoomSDKInterop : IDisposable
{
    private bool _disposed = false;

    ~ZoomSDKInterop()
    {
        Dispose(false);
    }

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    protected virtual void Dispose(bool disposing)
    {
        if (!_disposed)
        {
            if (disposing)
            {
                Cleanup();
            }
            _disposed = true;
        }
    }
}
```

---

### WPF Sample (ZoomVideoSDK.WPF)

#### What's Good

| Check | Status | Notes |
|-------|--------|-------|
| Dispatcher thread safety | ✅ | CheckAccess() + BeginInvoke |
| BitmapImage.Freeze() | ✅ | Cross-thread safety for WPF |
| Frame rate throttling | ✅ | 30fps limit |
| Window close cleanup | ✅ | LeaveSession + Cleanup in OnClosed |
| BitmapCacheOption.OnLoad | ✅ | Proper stream handling |

#### Issues Found

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| ⚠️ Medium | MemoryStream PNG conversion | Lines 384-395 | Use Imaging.CreateBitmapSourceFromHBitmap for speed |
| ⚠️ Medium | Missing IDisposable | ZoomSDKInterop.cs | Same fix as WinForms |
| ⚠️ Low | Duplicate YUV conversion | Lines 406-480 | Remove - wrapper handles this |
| ⚠️ Info | WriteableBitmap error bitmap | Lines 493-527 | No text drawn - consider DrawingContext |

#### Recommended Fix: Faster Bitmap Conversion

```csharp
// Faster alternative to MemoryStream PNG encoding
[DllImport("gdi32.dll")]
private static extern bool DeleteObject(IntPtr hObject);

private BitmapSource ConvertBitmapToBitmapSource(Bitmap bitmap)
{
    if (bitmap == null) return null;

    IntPtr hBitmap = bitmap.GetHbitmap();
    try
    {
        var source = System.Windows.Interop.Imaging.CreateBitmapSourceFromHBitmap(
            hBitmap,
            IntPtr.Zero,
            Int32Rect.Empty,
            BitmapSizeOptions.FromEmptyOptions());
        source.Freeze();
        return source;
    }
    finally
    {
        DeleteObject(hBitmap);  // Prevent GDI handle leak
    }
}
```

---

### Cross-Sample Issues

These issues appear in multiple samples:

#### 1. Audio Connection Timing

**Affected:** Win32, C++/CLI Wrapper

```cpp
// Current (all samples)
sessionContext.audioOption.connect = true;

// Recommended per Zoom docs
sessionContext.audioOption.connect = false;
// Then call startAudio() in onSessionJoin callback
```

**Why:** Setting `connect = true` during join may cause audio to connect before the session is fully established, potentially missing early audio callbacks.

#### 2. Video Subscription Timing

**Pattern followed correctly:** All samples wait for `onUserJoin` or `onUserVideoStatusChanged` before subscribing to video.

#### 3. Resource Cleanup

**Pattern followed correctly:** All samples implement cleanup in form/window closing handlers.

---

### Production Checklist

Use this checklist before deploying:

```
[ ] Audio: Set audioOption.connect = false, start in onSessionJoin
[ ] Video: Subscribe only after onUserJoin/onUserVideoStatusChanged
[ ] Memory: Track and cleanup all native handlers
[ ] Threading: Marshal all UI updates to main thread
[ ] Disposal: Implement IDisposable with destructor/finalizer
[ ] Frame Rate: Throttle video at 30fps to prevent UI lock
[ ] Error Handling: Try/catch all SDK calls
[ ] Cleanup: LeaveSession before Cleanup on app close
```

---

## Related Documentation

- [SDK Architecture Pattern](../../concepts/sdk-architecture-pattern.md)
- [Video Rendering](../video-rendering.md)
- [Screen Share Subscription](../screen-share-subscription.md)
- [Delegate Methods](../../references/delegate-methods.md)

## Sample Locations

All samples are in:
```
C:\tempsdk\videosdk-windows-dotnet-desktop-framework-quickstart\
├── ZoomVideoSDK.Win32\      # Native Win32 + Canvas API
├── ZoomVideoSDK.Wrapper\    # C++/CLI Bridge (shared)
├── ZoomVideoSDK.WinForms\   # C# WinForms + Raw Data
└── ZoomVideoSDK.WPF\        # C# WPF + BitmapSource
```
