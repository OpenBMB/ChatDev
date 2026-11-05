# Environment Variables

## Required for JWT Auth

| Variable | Required | Description |
|----------|----------|-------------|
| `ZOOM_API_KEY` | Yes | Build-platform issuer key used in the JWT `iss` claim |
| `ZOOM_API_SECRET` | Yes | Build-platform signing secret for `HS256` JWT generation |

Do not treat shell placeholders such as `${ZOOM_API_KEY}` as valid configured values.

## Common App Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PORT` | No | Local server port |
| `LANGUAGE` | No | Default language code such as `en-US` |

## Batch / S3 Variables

| Variable | Required for batch | Description |
|----------|--------------------|-------------|
| `S3_INPUT_URI` | Usually | Input prefix or file URI |
| `S3_OUTPUT_URI` | Usually | Output transcript destination |
| `AWS_ACCESS_KEY_ID` | If not using pre-signed access | AWS credential |
| `AWS_SECRET_ACCESS_KEY` | If not using pre-signed access | AWS credential |
| `AWS_SESSION_TOKEN` | Often | Temporary credential token |

## Webhook Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WEBHOOK_URL` | Optional | Public HTTPS callback for batch notifications |
| `WEBHOOK_SECRET` | Optional but recommended | HMAC secret used to verify Zoom callback signatures |

## Where to Find These Values

- Build-platform credentials: Zoom developer portal / Build app credential page.
- S3 URIs: your cloud storage path design.
- AWS credentials: IAM or STS-issued temporary credentials.
- Webhook URL: public HTTPS endpoint you control.
