# iOS Setup Notes

Observed in package sample project:

- Podfile includes React Native integration and required permissions pods.
- Wrapper supports optional init fields:
  - `bundleResPath`
  - `appGroupId`
  - `replaykitBundleIdentifier`

These are relevant for custom resource path and screen-share style setups.

Confirm iOS deployment target and Podfile settings against your RN version.
