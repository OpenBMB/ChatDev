# Probe SDK Reference Map

## Canonical Documentation

- Product docs: https://developers.zoom.us/docs/probe-sdk/
- Get started: https://developers.zoom.us/docs/probe-sdk/get-started/
- API reference: https://marketplacefront.zoom.us/sdk/probe/index.html

## Core Classes

- `Prober`
- `Reporter`

## Core Methods

From global/class reference surfaces:
- `requestMediaDevicePermission`
- `requestMediaDevices`
- `diagnoseAudio`
- `diagnoseVideo`
- `startToDiagnose`
- `stopToDiagnose`
- `stopToDiagnoseVideo`
- `releaseMediaStream`
- `reportBasicInfo`
- `reportFeatures`
- `cleanup`

## Key Enums/Constants

- `RENDERER_TYPE`
- `NETWORK_QUALITY_LEVEL`
- `BANDWIDTH_QUALITY_LEVEL`
- `PROTOCOL_TYPE`
- `ERR_CODE`
- `SUPPORTED_FEATURE_INDEX`
- `BASIC_INFO_ATTR_INDEX`

## Changelog and Package

- Changelog: https://developers.zoom.us/changelog/probe-sdk/
- npm package: https://www.npmjs.com/package/@zoom/probesdk
- sample source: https://github.com/zoom/probesdk-web
