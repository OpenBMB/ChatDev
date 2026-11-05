# RTMS Data Types

Complete reference for all RTMS enums and constants.

## Message Types (RTMS_MESSAGE_TYPE)

| Value | Name | Direction | Description |
|-------|------|-----------|-------------|
| 0 | UNDEFINED | - | Default |
| 1 | SIGNALING_HAND_SHAKE_REQ | Client -> Server | Signaling handshake request |
| 2 | SIGNALING_HAND_SHAKE_RESP | Server -> Client | Signaling handshake response |
| 3 | DATA_HAND_SHAKE_REQ | Client -> Server | Media handshake request |
| 4 | DATA_HAND_SHAKE_RESP | Server -> Client | Media handshake response |
| 5 | EVENT_SUBSCRIPTION | Client -> Server | Subscribe/unsubscribe events |
| 6 | EVENT_UPDATE | Server -> Client | Event notification |
| 7 | CLIENT_READY_ACK | Client -> Server | Ready to receive media |
| 8 | STREAM_STATE_UPDATE | Server -> Client | Stream state changed |
| 9 | SESSION_STATE_UPDATE | Server -> Client | Session state changed |
| 10 | SESSION_STATE_REQ | Client -> Server | Request session state |
| 11 | SESSION_STATE_RESP | Server -> Client | Session state response |
| 12 | KEEP_ALIVE_REQ | Server -> Client | Heartbeat ping |
| 13 | KEEP_ALIVE_RESP | Client -> Server | Heartbeat pong |
| 14 | MEDIA_DATA_AUDIO | Server -> Client | Audio data |
| 15 | MEDIA_DATA_VIDEO | Server -> Client | Video data |
| 16 | MEDIA_DATA_SHARE | Server -> Client | Screen share data |
| 17 | MEDIA_DATA_TRANSCRIPT | Server -> Client | Transcript data |
| 18 | MEDIA_DATA_CHAT | Server -> Client | Chat data |
| 19 | STREAM_STATE_REQ | Client -> Server | Request stream state |
| 20 | STREAM_STATE_RESP | Server -> Client | Stream state response |
| 21 | STREAM_CLOSE_REQ | Client -> Server | Request graceful stream shutdown |
| 22 | STREAM_CLOSE_RESP | Server -> Client | Response to close stream request |
| 23 | META_DATA_AUDIO | Server -> Client | Audio metadata |
| 24 | META_DATA_VIDEO | Server -> Client | Reserved video metadata |
| 25 | META_DATA_SHARE | Server -> Client | Reserved share metadata |
| 26 | META_DATA_TRANSCRIPT | Server -> Client | Reserved transcript metadata |
| 27 | META_DATA_CHAT | Server -> Client | Reserved chat metadata |
| 28 | VIDEO_SUBSCRIPTION_REQ | Client -> Server | Subscribe or unsubscribe one participant video stream |
| 29 | VIDEO_SUBSCRIPTION_RESP | Server -> Client | Response to participant video subscription |

## Event Types (RTMS_EVENT_TYPE)

| Value | Name | Description |
|-------|------|-------------|
| 0 | UNDEFINED | Default |
| 1 | FIRST_PACKET_TIMESTAMP | First packet received |
| 2 | ACTIVE_SPEAKER_CHANGE | Active speaker changed |
| 3 | PARTICIPANT_JOIN | Participant joined |
| 4 | PARTICIPANT_LEAVE | Participant left |
| 5 | SHARING_START | Screen sharing started |
| 6 | SHARING_STOP | Screen sharing stopped |
| 7 | MEDIA_CONNECTION_INTERRUPTED | Connection interrupted |
| 8 | PARTICIPANT_VIDEO_ON | Participant camera turned on |
| 9 | PARTICIPANT_VIDEO_OFF | Participant camera turned off |

## Zoom Contact Center Voice Event Types (RTMS_ZCC_VOICE_EVENT_TYPE)

| Value | Name | Description |
|-------|------|-------------|
| 0 | UNDEFINED | Default |
| 8 | CONSUMER_ANSWERED | Consumer answered the call |
| 9 | CONSUMER_END | Consumer ended the call |
| 10 | USER_ANSWERED | User or agent answered the call |
| 11 | USER_END | User or agent ended the call |
| 12 | USER_HOLD | User placed the call on hold |
| 13 | USER_UNHOLD | User resumed the call |
| 14 | MONITOR_STARTED | Monitoring started |
| 15 | MONITOR_TRANSITIONED | Monitoring transitioned |
| 16 | MONITOR_ENDED | Monitoring ended |
| 17 | TAKEOVER_STARTED | Takeover started |
| 18 | TRANSFER_INITIATED | Transfer initiated |
| 19 | TRANSFER_CANCELED | Transfer canceled |
| 20 | TRANSFER_ACCEPTED | Transfer accepted |
| 21 | TRANSFER_COMPLETED | Transfer completed |
| 22 | TRANSFER_REJECTED | Transfer rejected |
| 23 | TRANSFER_TIMEOUT | Transfer timed out |
| 24 | CONFERENCE_CANCELED | Conference canceled |
| 25 | CONFERENCE_PARTICIPANT_CANCELED | Conference participant canceled |
| 26 | CONFERENCE_PARTICIPANT_INVITED | Conference participant invited |
| 27 | CONFERENCE_PARTICIPANT_REJECTED | Conference participant rejected |
| 28 | CONFERENCE_PARTICIPANT_TIMEOUT | Conference participant timed out |

## Status Codes (RTMS_STATUS_CODE)

| Value | Name | Description |
|-------|------|-------------|
| 0 | STATUS_OK | Success |
| 1 | STATUS_INVALID_MESSAGE_TYPE | Invalid message type |
| 2 | STATUS_INVALID_RTMS_STREAM_ID | Invalid RTMS stream ID |
| 3 | STATUS_INVALID_SIGNATURE | Invalid signature |
| 4 | STATUS_INVALID_PAYLOAD | Invalid payload |
| 5 | STATUS_INVALID_EVENTS | Invalid event list |
| 6 | STATUS_INVALID_EVENT_TYPE | Invalid event type |
| 7 | STATUS_INVALID_MEDIA_TYPE | Invalid media type |
| 8 | STATUS_DUPLICATE_SIGNAL_REQUEST | Duplicate signaling connection |
| 9 | STATUS_MEDIA_TYPE_AUDIO_NOT_SUPPORT | Audio stream not supported |
| 10 | STATUS_MEDIA_TYPE_VIDEO_NOT_SUPPORT | Video stream not supported |
| 11 | STATUS_MEDIA_TYPE_DESKSHARE_NOT_SUPPORT | Screen share stream not supported |
| 12 | STATUS_MEDIA_TYPE_TRANSCRIPT_NOT_SUPPORT | Transcript stream not supported |
| 13 | STATUS_MEDIA_TYPE_CHAT_NOT_SUPPORT | Chat stream not supported |
| 14 | STATUS_MEDIA_TYPE_INVALID_VALUE | Invalid media type value |
| 15 | STATUS_MEDIA_DATA_ALL_CONNECTION_EXIST | All media data connections already exist |
| 16 | STATUS_DUPLICATE_MEDIA_DATA_CONNECTION | Duplicate media data connection |
| 17 | STATUS_INVALID_MEDIA_PARAMS | Invalid media params |
| 18 | STATUS_INVALID_MEDIA_AUDIO_PARAMS | Invalid audio params |
| 19 | STATUS_INVALID_MEDIA_AUDIO_CONTENT_TYPE | Invalid audio content type |
| 20 | STATUS_INVALID_MEDIA_AUDIO_SAMPLE_RATE | Invalid audio sample rate |
| 21 | STATUS_INVALID_MEDIA_AUDIO_CHANNEL | Invalid audio channel count |
| 22 | STATUS_INVALID_MEDIA_AUDIO_CODEC | Invalid audio codec |
| 23 | STATUS_INVALID_MEDIA_AUDIO_DATA_OPT | Invalid audio data option |
| 24 | STATUS_INVALID_MEDIA_AUDIO_SEND_RATE | Invalid audio send rate |
| 25 | STATUS_INVALID_MEDIA_VIDEO_PARAMS | Invalid video params |
| 26 | STATUS_INVALID_MEDIA_VIDEO_CONTENT_TYPE | Invalid video content type |
| 27 | STATUS_INVALID_MEDIA_VIDEO_CODEC | Invalid video codec |
| 28 | STATUS_INVALID_MEDIA_VIDEO_RESOLUTION | Invalid video resolution |
| 29 | STATUS_INVALID_MEDIA_VIDEO_DATA_OPT | Invalid video data option |
| 30 | STATUS_INVALID_MEDIA_VIDEO_FPS | Invalid video FPS |
| 31 | STATUS_INVALID_MEDIA_DESKSHARE_PARAMS | Invalid deskshare params |
| 32 | STATUS_INVALID_MEDIA_DESKSHARE_CONTENT_TYPE | Invalid deskshare content type |
| 33 | STATUS_INVALID_MEDIA_DESKSHARE_CODEC | Invalid deskshare codec |
| 34 | STATUS_INVALID_MEDIA_DESKSHARE_RESOLUTION | Invalid deskshare resolution |
| 35 | STATUS_INVALID_MEDIA_DESKSHARE_FPS | Invalid deskshare FPS |
| 36 | STATUS_INVALID_MEDIA_TRANSCRIPT_PARAMS | Invalid transcript params |
| 37 | STATUS_INVALID_MEDIA_TRANSCRIPT_CONTENT_TYPE | Invalid transcript content type |
| 38 | STATUS_INVALID_MEDIA_CHAT_PARAMS | Invalid chat params |
| 39 | STATUS_INVALID_MEDIA_CHAT_CONTENT_TYPE | Invalid chat content type |
| 40 | STATUS_INVALID_RTMS_SESSION_ID | Invalid RTMS session ID |
| 41 | STATUS_INVALID_CLIENT_READY_ACK | Invalid client ready ack |
| 42 | STATUS_INVALID_EVENT_SUBSCRIBE | Invalid event subscription payload |
| 43 | STATUS_INVALID_MEDIA_TRANSCRIPT_SROUCE_LANGUAGE | Invalid transcript source language |

## Media Data Types (MEDIA_DATA_TYPE)

Use bitwise OR to combine:

| Value | Name | Constant |
|-------|------|----------|
| 1 | AUDIO | 0x01 |
| 2 | VIDEO | 0x01 << 1 |
| 4 | DESKSHARE | 0x01 << 2 |
| 8 | TRANSCRIPT | 0x01 << 3 |
| 16 | CHAT | 0x01 << 4 |
| 32 | ALL | 0x01 << 5 |

**Common combinations**:
- Audio + Transcript: `1 | 8 = 9`
- Audio + Video: `1 | 2 = 3`
- All media: `32`

## Content Types (MEDIA_CONTENT_TYPE)

| Value | Name | Description |
|-------|------|-------------|
| 0 | UNDEFINED | Default |
| 1 | RTP | Real-time audio/video |
| 2 | RAW_AUDIO | Raw audio data |
| 3 | RAW_VIDEO | Raw video data |
| 4 | FILE_STREAM | File stream |
| 5 | TEXT | Text (transcript, chat) |

## Payload Types / Codecs (MEDIA_PAYLOAD_TYPE)

| Value | Name | Use |
|-------|------|-----|
| 0 | UNDEFINED | - |
| 1 | L16 | Audio - PCM uncompressed |
| 2 | G711 | Audio - compressed |
| 3 | G722 | Audio - compressed |
| 4 | OPUS | Audio - compressed |
| 5 | JPG | Video/Share - when fps <= 5 |
| 6 | PNG | Video/Share - when fps <= 5 |
| 7 | H264 | Video/Share - when fps > 5 |

## Media Data Options (MEDIA_DATA_OPTION)

| Value | Name | Description |
|-------|------|-------------|
| 0 | UNDEFINED | - |
| 1 | AUDIO_MIXED_STREAM | All audio combined |
| 2 | AUDIO_MULTI_STREAMS | Per-participant audio |
| 3 | VIDEO_SINGLE_ACTIVE_STREAM | Active speaker video |
| 4 | VIDEO_SINGLE_INDIVIDUAL_STREAM | One manually selected participant video stream |

## Media Resolution (MEDIA_RESOLUTION)

| Value | Name | Pixels |
|-------|------|--------|
| 1 | SD | 854x480 or 640x360 |
| 2 | HD | 1280x720 |
| 3 | FHD | 1920x1080 |
| 4 | QHD | 2560x1440 |

## Audio Sample Rate (AUDIO_SAMPLE_RATE)

| Value | Name | Rate |
|-------|------|------|
| 0 | SR_8K | 8000 Hz |
| 1 | SR_16K | 16000 Hz |
| 2 | SR_32K | 32000 Hz |
| 3 | SR_48K | 48000 Hz |

## Audio Channel (AUDIO_CHANNEL)

| Value | Name | Note |
|-------|------|------|
| 1 | MONO | Default |
| 2 | STEREO | Only with OPUS codec! |

## Session State (RTMS_SESSION_STATE)

| Value | Name | Description |
|-------|------|-------------|
| 0 | INACTIVE | Default |
| 1 | INITIALIZE | Session initializing |
| 2 | STARTED | Session started |
| 3 | PAUSED | Session paused |
| 4 | RESUMED | Session resumed |
| 5 | STOPPED | Session stopped |

## Stream State (RTMS_STREAM_STATE)

| Value | Name | Description |
|-------|------|-------------|
| 0 | INACTIVE | Default |
| 1 | ACTIVE | Streaming |
| 2 | INTERRUPTED | Connection problem |
| 3 | TERMINATING | Ending |
| 4 | TERMINATED | Ended |
| 5 | PAUSED | Paused |
| 6 | RESUMED | Resumed |

## Stop Reasons (RTMS_STOP_REASON)

| Value | Name | Description |
|-------|------|-------------|
| 0 | UNDEFINED | Default |
| 1 | STOP_BC_HOST_TRIGGERED | Host stopped |
| 2 | STOP_BC_USER_TRIGGERED | User stopped |
| 3 | STOP_BC_USER_LEFT | User left meeting |
| 4 | STOP_BC_USER_EJECTED | User ejected by host |
| 5 | STOP_BC_HOST_DISABLED_APP | Host disabled app |
| 6 | STOP_BC_MEETING_ENDED | Meeting ended |
| 7 | STOP_BC_STREAM_CANCELED | Stream canceled |
| 8 | STOP_BC_STREAM_REVOKED | Stream revoked (delete assets!) |
| 9 | STOP_BC_ALL_APPS_DISABLED | All apps disabled |
| 10 | STOP_BC_INTERNAL_EXCEPTION | Internal error |
| 11 | STOP_BC_CONNECTION_TIMEOUT | Connection timeout |
| 12 | STOP_BC_INSTANCE_CONNECTION_INTERRUPTED | Instance/media connection interrupted |
| 13 | STOP_BC_SIGNAL_CONNECTION_INTERRUPTED | Signaling issue |
| 14 | STOP_BC_DATA_CONNECTION_INTERRUPTED | Data connection issue |
| 15 | STOP_BC_SIGNAL_CONNECTION_CLOSED_ABNORMALLY | Abnormal close |
| 16 | STOP_BC_DATA_CONNECTION_CLOSED_ABNORMALLY | Abnormal close |
| 17 | STOP_BC_EXIT_SIGNAL | Exit signal received |
| 18 | STOP_BC_AUTHENTICATION_FAILURE | Auth failed |
| 19 | STOP_BC_AWAIT_RECONNECTION_TIMEOUT | Awaited reconnection timed out |
| 20 | STOP_BC_RECEIVER_REQUEST_CLOSE | Receiver requested stream close |
| 21 | STOP_BC_CUSTOMER_DISCONNECTED | Contact Center customer disconnected |
| 22 | STOP_BC_AGENT_DISCONNECTED | Contact Center agent disconnected |
| 23 | STOP_BC_ADMIN_DISABLED_APP | Admin disabled app |
| 24 | STOP_BC_KEEP_ALIVE_TIMEOUT | Three keep-alive requests missed |
| 25 | STOP_BC_MANUAL_API_TRIGGERED | ZCC Voice API triggered stop |
| 26 | STOP_BC_STREAMING_NOT_SUPPORTED | Queue does not support streaming |

## Transcript Languages (RTMS_TRANSCRIPT_LANGUAGE)

| Value | Name | Language |
|-------|------|----------|
| -1 | LANGUAGE_ID_NONE | None/Auto-detect |
| 0 | LANGUAGE_ID_ARABIC | Arabic |
| 1 | LANGUAGE_ID_BENGALI | Bengali |
| 2 | LANGUAGE_ID_CANTONESE | Cantonese |
| 3 | LANGUAGE_ID_CATALAN | Catalan |
| 4 | LANGUAGE_ID_CHINESE_SIMPLIFIED | Chinese (Simplified) |
| 5 | LANGUAGE_ID_CHINESE_TRADITIONAL | Chinese (Traditional) |
| 6 | LANGUAGE_ID_CZECH | Czech |
| 7 | LANGUAGE_ID_DANISH | Danish |
| 8 | LANGUAGE_ID_DUTCH | Dutch |
| **9** | **LANGUAGE_ID_ENGLISH** | **English (Default)** |
| 10 | LANGUAGE_ID_ESTONIAN | Estonian |
| 11 | LANGUAGE_ID_FINNISH | Finnish |
| 12 | LANGUAGE_ID_FRENCH_CANADA | French (Canada) |
| 13 | LANGUAGE_ID_FRENCH_FRANCE | French (France) |
| 14 | LANGUAGE_ID_GERMAN | German |
| 15 | LANGUAGE_ID_HEBREW | Hebrew |
| 16 | LANGUAGE_ID_HINDI | Hindi |
| 17 | LANGUAGE_ID_HUNGARIAN | Hungarian |
| 18 | LANGUAGE_ID_INDONESIAN | Indonesian |
| 19 | LANGUAGE_ID_ITALIAN | Italian |
| 20 | LANGUAGE_ID_JAPANESE | Japanese |
| 21 | LANGUAGE_ID_KOREAN | Korean |
| 22 | LANGUAGE_ID_MALAY | Malay |
| 23 | LANGUAGE_ID_PERSIAN | Persian |
| 24 | LANGUAGE_ID_POLISH | Polish |
| 25 | LANGUAGE_ID_PORTUGUESE | Portuguese |
| 26 | LANGUAGE_ID_ROMANIAN | Romanian |
| 27 | LANGUAGE_ID_RUSSIAN | Russian |
| 28 | LANGUAGE_ID_SPANISH | Spanish |
| 29 | LANGUAGE_ID_SWEDISH | Swedish |
| 30 | LANGUAGE_ID_TAGALOG | Tagalog |
| 31 | LANGUAGE_ID_TAMIL | Tamil |
| 32 | LANGUAGE_ID_TELUGU | Telugu |
| 33 | LANGUAGE_ID_THAI | Thai |
| 34 | LANGUAGE_ID_TURKISH | Turkish |
| 35 | LANGUAGE_ID_UKRAINIAN | Ukrainian |
| 36 | LANGUAGE_ID_VIETNAMESE | Vietnamese |

## Transcript Handshake Controls

Transcript media handshakes now use:

- `src_language`: fixed requested transcription language
- `enable_lid`: boolean switch for Language Identification

Behavior:

- `enable_lid: true` or omitted: RTMS can automatically switch languages during transcription
- `enable_lid: false`: RTMS stays on `src_language` and does not auto-switch

## Next Steps

- **[Media Types](media-types.md)** - Parameter configurations
- **[Connection](connection.md)** - Protocol details
- **[Manual WebSocket](../examples/manual-websocket.md)** - Implementation
