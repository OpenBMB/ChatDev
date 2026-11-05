# AI Integration Patterns

Patterns for integrating RTMS with AI services for transcription, analysis, and meeting assistants. These examples work with meetings, webinars, and Video SDK sessions.

## Audio Transcription with External Services

### Deepgram Integration

```javascript
import rtms from "@zoom/rtms";
import { createClient } from "@deepgram/sdk";

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];
const deepgram = createClient(process.env.DEEPGRAM_API_KEY);

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  // Configure for Deepgram-compatible audio
  client.setAudioParams({
    codec: 1,          // L16 (PCM)
    sampleRate: 1,     // 16kHz
    channel: 1,        // Mono
    dataOpt: 1         // Mixed stream
  });

  // Create live transcription connection
  const connection = deepgram.listen.live({
    model: "nova-2",
    language: "en",
    smart_format: true,
    punctuate: true,
  });

  connection.on("Results", (data) => {
    const transcript = data.channel.alternatives[0].transcript;
    if (transcript) {
      console.log(`[Deepgram]: ${transcript}`);
    }
  });

  client.onAudioData((buffer, timestamp, metadata) => {
    // Send audio to Deepgram
    connection.send(buffer);
  });

  client.onLeave(() => {
    connection.finish();
  });

  client.join(payload);
});
```

### AssemblyAI Integration

```javascript
import rtms from "@zoom/rtms";
import { AssemblyAI } from "assemblyai";

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];
const aai = new AssemblyAI({ apiKey: process.env.ASSEMBLYAI_API_KEY });

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  client.setAudioParams({
    codec: 1,          // L16 (PCM)
    sampleRate: 1,     // 16kHz
    channel: 1         // Mono
  });

  const transcriber = aai.realtime.createService({
    sampleRate: 16000,
  });

  transcriber.connect();

  transcriber.on("transcript", (transcript) => {
    if (transcript.text) {
      console.log(`[AssemblyAI]: ${transcript.text}`);
    }
  });

  client.onAudioData((buffer, timestamp, metadata) => {
    transcriber.sendAudio(buffer);
  });

  client.onLeave(() => {
    transcriber.close();
  });

  client.join(payload);
});
```

### Whisper (Local) Integration

```javascript
import rtms from "@zoom/rtms";
import { Whisper } from "whisper-node";

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];
const whisper = new Whisper("base.en");

let audioBuffer = Buffer.alloc(0);
const BUFFER_SIZE = 16000 * 10; // 10 seconds at 16kHz

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  client.setAudioParams({
    codec: 1,          // L16 (PCM)
    sampleRate: 1,     // 16kHz
    channel: 1         // Mono
  });

  client.onAudioData(async (buffer, timestamp, metadata) => {
    // Accumulate audio
    audioBuffer = Buffer.concat([audioBuffer, buffer]);

    // Transcribe when buffer is full
    if (audioBuffer.length >= BUFFER_SIZE) {
      const transcript = await whisper.transcribe(audioBuffer);
      console.log(`[Whisper]: ${transcript}`);
      audioBuffer = Buffer.alloc(0);
    }
  });

  client.join(payload);
});
```

## Meeting Summarization

### OpenAI/GPT Integration

```javascript
import rtms from "@zoom/rtms";
import OpenAI from "openai";

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const transcripts = [];
let summaryInterval;

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();

  client.onTranscriptData((buffer, timestamp, metadata) => {
    const text = buffer.toString('utf8');
    transcripts.push({
      speaker: metadata.userName,
      text: text,
      time: new Date(timestamp)
    });
  });

  // Generate summary every 5 minutes
  summaryInterval = setInterval(async () => {
    if (transcripts.length === 0) return;

    const fullTranscript = transcripts
      .map(t => `${t.speaker}: ${t.text}`)
      .join('\n');

    const summary = await openai.chat.completions.create({
      model: "gpt-4",
      messages: [
        {
          role: "system",
          content: "Summarize this meeting transcript. Include key points, decisions, and action items."
        },
        {
          role: "user",
          content: fullTranscript
        }
      ]
    });

    console.log("Meeting Summary:", summary.choices[0].message.content);
  }, 5 * 60 * 1000);

  client.onLeave(async () => {
    clearInterval(summaryInterval);

    // Generate final summary
    const fullTranscript = transcripts
      .map(t => `${t.speaker}: ${t.text}`)
      .join('\n');

    const summary = await openai.chat.completions.create({
      model: "gpt-4",
      messages: [
        {
          role: "system",
          content: `Create a comprehensive meeting summary with:
- Key topics discussed
- Decisions made
- Action items with owners
- Follow-up items`
        },
        {
          role: "user",
          content: fullTranscript
        }
      ]
    });

    console.log("Final Summary:", summary.choices[0].message.content);
  });

  client.join(payload);
});
```

## Real-Time Sentiment Analysis

```javascript
import rtms from "@zoom/rtms";

async function analyzeSentiment(text) {
  // Use any sentiment API (OpenAI, HuggingFace, etc.)
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.OPENAI_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'gpt-3.5-turbo',
      messages: [{
        role: 'user',
        content: `Analyze sentiment (positive/neutral/negative): "${text}"`
      }]
    })
  });

  const data = await response.json();
  return data.choices[0].message.content;
}

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();
  let recentTranscripts = [];

  client.onTranscriptData(async (buffer, timestamp, metadata) => {
    const text = buffer.toString('utf8');
    recentTranscripts.push(text);

    // Analyze every 10 segments
    if (recentTranscripts.length >= 10) {
      const combinedText = recentTranscripts.join(' ');
      const sentiment = await analyzeSentiment(combinedText);
      console.log(`Sentiment: ${sentiment}`);
      recentTranscripts = [];
    }
  });

  client.join(payload);
});
```

## Audio Recording with Gap Filling

For continuous playback, fill audio gaps with silence:

```javascript
import rtms from "@zoom/rtms";
import fs from 'fs';

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];
const SAMPLE_RATE = 16000;
const BYTES_PER_SAMPLE = 2; // 16-bit
const MS_PER_FRAME = 20;
const BYTES_PER_FRAME = SAMPLE_RATE * BYTES_PER_SAMPLE * MS_PER_FRAME / 1000;

function generateSilentFrame(durationMs) {
  const samples = SAMPLE_RATE * durationMs / 1000;
  return Buffer.alloc(samples * BYTES_PER_SAMPLE);
}

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();
  const streamId = payload.rtms_stream_id;

  const audioStream = fs.createWriteStream(`recordings/${streamId}.pcm`);
  let lastTimestamp = null;

  client.setAudioParams({
    codec: 1,          // L16 (PCM)
    sampleRate: 1,     // 16kHz
    channel: 1,        // Mono
    dataOpt: 1,        // Mixed stream
    duration: 20       // 20ms chunks
  });

  client.onAudioData((buffer, timestamp, metadata) => {
    if (lastTimestamp !== null) {
      const gap = timestamp - lastTimestamp;

      // Fill gaps >= 500ms with silence
      if (gap >= 500) {
        const silentFrames = Math.floor(gap / MS_PER_FRAME);
        console.log(`Gap detected: ${gap}ms, filling ${silentFrames} frames`);

        for (let i = 0; i < silentFrames; i++) {
          audioStream.write(generateSilentFrame(MS_PER_FRAME));
        }
      }
    }

    lastTimestamp = timestamp;
    audioStream.write(buffer);
  });

  client.onLeave(() => {
    audioStream.end();
    console.log(`Recording saved: recordings/${streamId}.pcm`);
  });

  client.join(payload);
});
```

## Multi-Format Transcript Output

Generate VTT, SRT, and TXT simultaneously:

```javascript
import rtms from "@zoom/rtms";
import fs from 'fs';

const RTMS_EVENTS = ["meeting.rtms_started", "webinar.rtms_started", "session.rtms_started"];

function formatVttTimestamp(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const msec = ms % 1000;
  return `${String(h).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}.${String(msec).padStart(3, '0')}`;
}

function formatSrtTimestamp(ms) {
  return formatVttTimestamp(ms).replace('.', ',');
}

rtms.onWebhookEvent(({ event, payload }) => {
  if (!RTMS_EVENTS.includes(event)) return;

  const client = new rtms.Client();
  const streamId = payload.rtms_stream_id;

  const baseDir = `recordings/${streamId}`;
  fs.mkdirSync(baseDir, { recursive: true });

  fs.writeFileSync(`${baseDir}/transcript.vtt`, 'WEBVTT\n\n');
  let srtIndex = 1;
  let startTimestamp = null;

  client.onTranscriptData((buffer, timestamp, metadata) => {
    const text = buffer.toString('utf8');
    const userName = metadata.userName;

    if (startTimestamp === null) {
      startTimestamp = timestamp;
    }

    const relative = timestamp - startTimestamp;
    const endTime = relative + 2000; // 2 second duration

    // VTT format
    const vttLine = `${formatVttTimestamp(relative)} --> ${formatVttTimestamp(endTime)}\n${userName}: ${text}\n\n`;
    fs.appendFileSync(`${baseDir}/transcript.vtt`, vttLine);

    // SRT format
    const srtLine = `${srtIndex++}\n${formatSrtTimestamp(relative)} --> ${formatSrtTimestamp(endTime)}\n${userName}: ${text}\n\n`;
    fs.appendFileSync(`${baseDir}/transcript.srt`, srtLine);

    // Plain text
    const txtLine = `[${new Date(timestamp).toISOString()}] ${userName}: ${text}\n`;
    fs.appendFileSync(`${baseDir}/transcript.txt`, txtLine);
  });

  client.join(payload);
});
```

## Environment Variables

```bash
# Zoom RTMS
ZM_RTMS_CLIENT=your_client_id
ZM_RTMS_SECRET=your_client_secret

# AI Services
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
ASSEMBLYAI_API_KEY=...

# OpenRouter (free models)
OPENROUTER_API_KEY=sk-or-...
```

## Free AI Model Considerations

When using free models (Gemma, Qwen, DeepSeek via OpenRouter):

| Limitation | Impact | Solution |
|------------|--------|----------|
| No image support | Can't analyze screen shares | Use paid model or skip image analysis |
| Context limits | Long transcripts may fail | Chunk transcripts, summarize incrementally |
| Rate limiting | May get 429 errors | Implement retry with backoff, stagger requests |

**Recommended for production**: OpenRouter with `google/gemini-2.5-pro` - supports vision + XML tagging.

## Next Steps

- **[SDK Quickstart](sdk-quickstart.md)** - Basic RTMS setup
- **[Manual WebSocket](manual-websocket.md)** - Protocol details
- **[Media Types](../references/media-types.md)** - Audio/video configuration
