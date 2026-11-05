# Fast Mode Node Example

Minimal backend proxy for synchronous transcription.

```js
import express from 'express';
import multer from 'multer';
import { KJUR } from 'jsrsasign';

const app = express();
const upload = multer({ storage: multer.memoryStorage() });
app.use(express.json());

function generateJWT() {
  const iat = Math.round(Date.now() / 1000) - 30;
  const exp = iat + 60 * 60;
  return KJUR.jws.JWS.sign(
    'HS256',
    JSON.stringify({ alg: 'HS256', typ: 'JWT' }),
    JSON.stringify({ iss: process.env.ZOOM_API_KEY, iat, exp }),
    process.env.ZOOM_API_SECRET,
  );
}

app.post('/transcribe', upload.single('file'), async (req, res) => {
  const token = generateJWT();
  const config = {
    language: req.body.language || 'en-US',
    word_time_offsets: true,
    channel_separation: false,
  };

  let response;
  if (req.file) {
    const form = new FormData();
    form.append('file', new Blob([new Uint8Array(req.file.buffer)]), req.file.originalname);
    form.append('config', JSON.stringify(config));
    response = await fetch('https://api.zoom.us/v2/aiservices/scribe/transcribe', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
  } else {
    response = await fetch('https://api.zoom.us/v2/aiservices/scribe/transcribe', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        file: req.body.file,
        config,
      }),
    });
  }

  const text = await response.text();
  res.status(response.status).type('application/json').send(text);
});
```

Use this pattern when:
- the caller uploads a file to your backend and you forward it as multipart
- or the caller already has a URL-accessible media file and you submit the JSON URL form
