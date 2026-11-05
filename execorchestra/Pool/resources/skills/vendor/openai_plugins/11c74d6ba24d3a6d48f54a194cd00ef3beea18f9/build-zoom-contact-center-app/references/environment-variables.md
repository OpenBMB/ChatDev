# Zoom Contact Center Environment Variables

## Standard `.env` keys

| Variable | Required | Used for | Where to find |
| --- | --- | --- | --- |
| `ZOOM_CLIENT_ID` | Yes (API/OAuth integrations) | OAuth app identity for Contact Center APIs | Zoom Marketplace -> OAuth app -> App Credentials |
| `ZOOM_CLIENT_SECRET` | Yes (API/OAuth integrations) | OAuth token exchange | Zoom Marketplace -> OAuth app -> App Credentials |
| `ZOOM_REDIRECT_URI` | User OAuth flow | OAuth callback URL | Zoom Marketplace -> OAuth redirect/allow list |
| `ZCC_CHAT_ENTRY_ID` | Web/chat entry flows | Contact Center chat entry point routing | Contact Center Admin -> Flows -> Entry Points |
| `ZCC_VIDEO_ENTRY_ID` | Video engagement flows | Contact Center video entry point routing | Contact Center Admin -> Flows -> Entry Points |
| `ZCC_ZVA_ENTRY_ID` | Optional (Virtual Agent) | Virtual agent entry routing | Contact Center Admin -> Flows -> Entry Points |
| `ZCC_CAMPAIGN_API_KEY` | Campaign/web embed mode | Campaign authorization for web embed | Contact Center Admin -> Campaign Management -> Web and In-App -> Embed Web Tag |
| `ZCC_WEB_API_KEY` | Web SDK/embed mode | Client-side Contact Center embed initialization | Contact Center Admin -> Campaign Management -> Web and In-App -> Embed Web Tag |
| `ZCC_SCHEDULED_CALLBACK_API_KEY` | Scheduled callback flows | Callback scheduling authorization | Contact Center campaign/flow callback configuration |

## Runtime-only values

- `ZOOM_ACCESS_TOKEN`
- Contact/session IDs issued by Contact Center runtime APIs

## Notes

- Contact Center implementations often mix OAuth credentials with flow/campaign keys.
- Keep OAuth secrets and campaign keys out of client-side source control.
