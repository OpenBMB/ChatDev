# Setup Guide

## 1. Install package

```bash
npm install @zoom/meetingsdk-react-native
```

## 2. Respect documented support boundaries

- React Native support currently documented up to `0.75.4`.
- Expo is currently not supported.
- Android baseline from docs: `minSdkVersion = 26`, `targetSdkVersion = 35`.

## 3. Align platform SDK versions

- This wrapper does not bundle native iOS/Android Meeting SDK artifacts for all workflows.
- Keep wrapper and native Meeting SDK versions aligned.
- For older wrapper versions (pre-`6.4.5`), docs note manual native SDK placement may be required.

## 4. Initialize provider

```tsx
import { ZoomSDKProvider } from '@zoom/meetingsdk-react-native';

<ZoomSDKProvider
  config={{
    jwtToken: '<MEETING_SDK_JWT>',
    domain: 'zoom.us',
    enableLog: true,
    logSize: 5,
  }}
>
  <App />
</ZoomSDKProvider>
```

## 5. Platform prerequisites

- Android: include Zoom Meeting SDK dependency in gradle and required permissions.
- iOS: ensure Podfile and framework setup are aligned with package expectations.

See [Android Setup](../references/android-setup.md) and [iOS Setup](../references/ios-setup.md).
