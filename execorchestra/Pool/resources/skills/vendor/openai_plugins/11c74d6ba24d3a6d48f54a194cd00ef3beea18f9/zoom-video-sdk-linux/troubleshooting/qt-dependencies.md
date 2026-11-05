# Qt5 Dependencies Setup

## Critical: Use Bundled Qt5, NOT System Qt5

**IMPORTANT**: The Zoom SDK requires **specific Qt5 libraries bundled with the SDK**. Do NOT install system Qt5.

## Setup Steps

### 1. Extract SDK

```bash
tar -xf zoom-video-sdk-linux_x86_64.tar.xz
cd zoom-video-sdk-linux_x86_64
```

### 2. Copy Qt5 Libraries

```bash
# Qt5 libs are in SDK samples
cp -r samples/qt_libs/Qt/lib/* lib/zoom_video_sdk/
```

### 3. Create Symlinks

```bash
cd lib/zoom_video_sdk

# Create unversioned symlinks
for lib in libQt5*.so.5; do
    ln -sf $lib ${lib%.5}
done

# Verify
ls -la libQt5*.so
```

Should see:
```
libQt5Core.so -> libQt5Core.so.5
libQt5Core.so.5
libQt5Gui.so -> libQt5Gui.so.5
libQt5Gui.so.5
...
```

### 4. Set Library Path

```bash
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/path/to/lib/zoom_video_sdk
```

## CMakeLists.txt Configuration

```cmake
# Link SDK libraries
link_directories(${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk)

target_link_libraries(${PROJECT_NAME}
    videosdk
    Qt5Core Qt5Gui Qt5Network Qt5Qml Qt5Quick
)

# Set RPATH
set_target_properties(${PROJECT_NAME} PROPERTIES
    BUILD_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
    INSTALL_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
)
```

## Required Qt5 Libraries

- libQt5Core.so.5
- libQt5Gui.so.5
- libQt5Network.so.5
- libQt5Qml.so.5
- libQt5Quick.so.5

## Common Issues

### Issue: "libQt5Core.so.5: cannot open shared object file"

**Solution**:
```bash
# Check library path
echo $LD_LIBRARY_PATH

# Add SDK lib directory
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/path/to/lib/zoom_video_sdk

# Or set in CMake RPATH (recommended)
```

### Issue: "version `Qt_5.15' not found"

**Cause**: System Qt5 conflicting with SDK Qt5.

**Solution**:
1. Remove system Qt5 from path
2. Ensure SDK Qt5 libraries are found first
3. Set RPATH correctly in CMake

### Issue: Missing symlinks

**Solution**:
```bash
cd lib/zoom_video_sdk
for lib in libQt5*.so.5; do ln -sf $lib ${lib%.5}; done
```
