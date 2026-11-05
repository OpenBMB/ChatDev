# Wrapper API Reference (React Native package)

## Init config

- `jwtToken?: string`
- `domain?: string`
- `enableLog?: boolean`
- `logSize?: number` (Android)
- `bundleResPath?: string` (iOS)
- `appGroupId?: string` (iOS)
- `replaykitBundleIdentifier?: string` (iOS)

## Methods

- `initSDK(config): Promise<boolean>`
- `isInitialized(): Promise<boolean>`
- `joinMeeting(config): Promise<number>`
- `startMeeting(config): Promise<number>`
- `updateMeetingSetting(config): void`
- `cleanup(): void`

## Join config highlights

- Required: `userName`, `meetingNumber`
- Optional: `password`, `zoomAccessToken`, `vanityID`, `webinarToken`, `joinToken`, `appPrivilegeToken`

## Start config highlights

- Required: `userName`, `zoomAccessToken`
- Optional: `meetingNumber`, `vanityID`, `inviteContactId`
