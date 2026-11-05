# Streaming Chat with AIChatAgent

Fetch `docs/resumable-streaming.md` and `docs/client-sdk.md` from `https://github.com/cloudflare/agents/tree/main/docs` for complete documentation.

`AIChatAgent` provides streaming chat with automatic message persistence and resumable streams.

## Basic Chat Agent

```typescript
import { AIChatAgent } from "@cloudflare/ai-chat";
import { streamText, convertToModelMessages } from "ai";
import { openai } from "@ai-sdk/openai";

export class Chat extends AIChatAgent<Env> {
  async onChatMessage(onFinish) {
    const result = streamText({
      model: openai("gpt-4o"),
      messages: await convertToModelMessages(this.messages),
      onFinish
    });
    return result.toUIMessageStreamResponse();
  }
}
```

## With Custom System Prompt

```typescript
export class Chat extends AIChatAgent<Env> {
  async onChatMessage(onFinish) {
    const result = streamText({
      model: openai("gpt-4o"),
      system: "You are a helpful assistant specializing in...",
      messages: await convertToModelMessages(this.messages),
      onFinish
    });
    return result.toUIMessageStreamResponse();
  }
}
```

## With Tools

```typescript
import { tool } from "ai";
import { z } from "zod";

const tools = {
  getWeather: tool({
    description: "Get weather for a location",
    parameters: z.object({ location: z.string() }),
    execute: async ({ location }) => `Weather in ${location}: 72°F, sunny`
  })
};

export class Chat extends AIChatAgent<Env> {
  async onChatMessage(onFinish) {
    const result = streamText({
      model: openai("gpt-4o"),
      messages: await convertToModelMessages(this.messages),
      tools,
      onFinish
    });
    return result.toUIMessageStreamResponse();
  }
}
```

## Custom UI Message Stream

For more control, use `createUIMessageStream`:

```typescript
import { createUIMessageStream, createUIMessageStreamResponse } from "ai";

export class Chat extends AIChatAgent<Env> {
  async onChatMessage(onFinish) {
    const stream = createUIMessageStream({
      execute: async ({ writer }) => {
        const result = streamText({
          model: openai("gpt-4o"),
          messages: await convertToModelMessages(this.messages),
          onFinish
        });
        writer.merge(result.toUIMessageStream());
      }
    });
    return createUIMessageStreamResponse({ stream });
  }
}
```

## Resumable Streaming

Streams automatically resume if client disconnects and reconnects:

1. Chunks buffered to SQLite during streaming
2. On reconnect, buffered chunks sent immediately
3. Live streaming continues from where it left off

**Enabled by default.** To disable:

```tsx
const { messages } = useAgentChat({ agent, resume: false });
```

## React Client

```tsx
import { useAgent } from "agents/react";
import { useAgentChat } from "@cloudflare/ai-chat/react";

function ChatUI() {
  const agent = useAgent({
    agent: "Chat",
    name: "my-chat-session"
  });

  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    status
  } = useAgentChat({ agent });

  return (
    <div>
      {messages.map((m) => (
        <div key={m.id}>
          <strong>{m.role}:</strong> {m.content}
        </div>
      ))}

      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={handleInputChange}
          disabled={status === "streaming"}
        />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
```

## Streaming RPC Methods

For non-chat streaming, use `@callable({ streaming: true })`:

```typescript
import { Agent, callable, StreamingResponse } from "agents";

export class MyAgent extends Agent<Env> {
  @callable({ streaming: true })
  async streamData(stream: StreamingResponse, query: string) {
    for (let i = 0; i < 10; i++) {
      stream.send(`Result ${i}: ${query}`);
      await sleep(100);
    }
    stream.close();
  }
}
```

Client receives streamed messages via WebSocket RPC.

## Status Values

`useAgentChat` status:

| Status | Meaning |
|--------|---------|
| `ready` | Idle, ready for input |
| `streaming` | Response streaming |
| `submitted` | Request sent, waiting |
| `error` | Error occurred |
