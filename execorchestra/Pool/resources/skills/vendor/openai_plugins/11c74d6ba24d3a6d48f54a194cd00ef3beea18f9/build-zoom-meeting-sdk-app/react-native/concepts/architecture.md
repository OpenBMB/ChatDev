# Architecture

The React Native package is a wrapper around native Meeting SDKs.

## Layers

- JS API layer: `@zoom/meetingsdk-react-native`
- Context/hook layer: `ZoomSDKProvider`, `useZoom`
- Native module layer: `RNZoomSDK` (iOS Obj-C, Android Java)
- Zoom native SDK layer: MobileRTC (iOS) and ZoomSDK (Android)

## Why this matters

- Wrapper updates can change JS signatures while native SDK versions evolve independently.
- Some options are platform-specific (`logSize` Android, `bundleResPath` iOS).
- Numeric error codes from native must be interpreted by platform docs.
