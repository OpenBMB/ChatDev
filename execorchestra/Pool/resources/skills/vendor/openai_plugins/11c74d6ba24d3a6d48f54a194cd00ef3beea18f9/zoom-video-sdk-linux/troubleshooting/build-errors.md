# Common Build Errors

## CMake Errors

### Error: "Could not find glib-2.0"

```bash
sudo apt install -y libglib2.0-dev
```

### Error: "CMake version too old"

```bash
# Install latest CMake
wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc | gpg --dearmor - | sudo tee /etc/apt/trusted.gpg.d/kitware.gpg
sudo apt-add-repository 'deb https://apt.kitware.com/ubuntu/ focal main'
sudo apt update
sudo apt install -y cmake
```

## Linker Errors

### Error: "undefined reference to `CreateZoomVideoSDKObj'"

**Cause**: Not linking libvideosdk.so

**Solution**:
```cmake
link_directories(${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk)
target_link_libraries(${PROJECT_NAME} videosdk)
```

### Error: Missing Qt symbols

**Solution**: Link Qt5 libraries:
```cmake
target_link_libraries(${PROJECT_NAME}
    videosdk
    Qt5Core Qt5Gui Qt5Network Qt5Qml Qt5Quick
)
```

## Header Include Errors

### Error: "zoom_video_sdk_api.h: No such file or directory"

**Solution**:
```cmake
include_directories(
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/include/zoom_video_sdk
)
```

### Error: "helpers/zoom_video_sdk_*.h: No such file"

**Solution**: Include both paths:
```cmake
include_directories(
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/include/zoom_video_sdk  # For helpers/ relative includes
)
```

## Runtime Errors

### Error: "libvideosdk.so: cannot open shared object file"

**Solution**:
```bash
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/path/to/lib/zoom_video_sdk
```

Or set RPATH:
```cmake
set_target_properties(${PROJECT_NAME} PROPERTIES
    BUILD_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
    INSTALL_RPATH "${CMAKE_SOURCE_DIR}/lib/zoom_video_sdk"
)
```

## Compiler Errors

### Error: "ISO C++17 does not allow dynamic exception specifications"

**Solution**: SDK requires C++17:
```cmake
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
```

### Error: "pure virtual method called"

**Cause**: Missing IZoomVideoSDKDelegate method implementations.

**Solution**: Implement ALL delegate methods (even empty stubs).
