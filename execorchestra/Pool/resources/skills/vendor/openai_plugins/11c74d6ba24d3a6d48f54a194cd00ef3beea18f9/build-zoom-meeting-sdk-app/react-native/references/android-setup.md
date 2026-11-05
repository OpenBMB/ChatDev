# Android Setup Notes

Representative dependency from SDK package example:

```gradle
implementation('us.zoom.meetingsdk:zoomsdk:6.7.2')
```

Other observed setup details:

- Java/Kotlin target 17 in sample.
- Wrapper maps many `JoinMeetingOptions` / `StartMeetingOptions` flags.
- `language` setting is consumed by native bridge during `updateMeetingSetting`.

Always verify against your app's RN/Gradle/Kotlin compatibility matrix.
