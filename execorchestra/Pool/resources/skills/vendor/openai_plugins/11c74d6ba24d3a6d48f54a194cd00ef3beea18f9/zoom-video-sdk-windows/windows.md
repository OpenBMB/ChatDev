---
name: video-sdk/windows
description: "Zoom Video SDK for Windows - C++ integration for video sessions, raw audio/video capture, screen sharing, recording, and real-time communication"
---

# Zoom Video SDK (Windows)

Windows platform support for Zoom Video SDK. Build custom video applications with C++ or C#/.NET integration.

For complete documentation, see **[SKILL.md](SKILL.md)**

## Quick Links

- **[Windows SDK Guide](SKILL.md)** - Complete Windows development guide
- **[API Reference](references/windows-reference.md)** - Complete API documentation
- **Official Docs**: https://developers.zoom.us/docs/video-sdk/windows/

## Features

- Full video session control
- Raw audio/video capture (PCM, YUV I420)
- Raw media injection (virtual audio/video)
- Cloud recording & live streaming
- Multi-platform support (x64, x86, ARM64)

## UI Framework Integration

| Framework | Approach | Guide |
|-----------|----------|-------|
| **Win32** | Direct SDK + Canvas API | [Win32 Guide](examples/dotnet-winforms/guide.md#option-1-win32-native-c---direct-sdk) |
| **WinForms** | C++/CLI wrapper + Raw Data | [WinForms Guide](examples/dotnet-winforms/guide.md#option-2-winforms-c--ccli-wrapper) |
| **WPF** | C++/CLI wrapper + BitmapSource | [WPF Guide](examples/dotnet-winforms/guide.md#option-3-wpf-c--ccli-wrapper) |

## C++/CLI Wrapper Patterns (Any Native Library → .NET)

Complete 8-pattern guide for wrapping native C++ libraries:
- [Full Guide](examples/dotnet-winforms/guide.md#ccli-wrapper-patterns-for-net-integration)
- Patterns: void*, gcroot<T^>, Finalizer, Strings, Arrays, Threading, LockBits

## Sample Repositories

- **GitHub**: https://github.com/zoom/videosdk-windows-rawdata-sample
- **Local Samples**:
  - `C:\tempsdk\Zoom_VideoSDK_Windows_RawDataDemos\` - C++ demos
  - `C:\tempsdk\videosdk-windows-dotnet-desktop-framework-quickstart\` - C# demos
  - `C:\tempsdk\sdksamples\zoom-video-sdk-windows-2.4.12\` - Official SDK samples
