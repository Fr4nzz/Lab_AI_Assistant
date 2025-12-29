# AI SDK Documentation Research

## Sources

- [AI SDK UI: Chatbot](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot)
- [AI SDK UI: Transport](https://ai-sdk.dev/docs/ai-sdk-ui/transport)
- [AI SDK UI: Stream Protocol](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
- [AI SDK UI: useChat Reference](https://ai-sdk.dev/docs/reference/ai-sdk-ui/use-chat)
- [AI SDK UI: Tool Usage](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage)
- [Getting Started: Nuxt](https://ai-sdk.dev/docs/getting-started/nuxt)

---

## 1. Chat Class (Vue/Nuxt)

### Basic Setup

```typescript
import { Chat } from "@ai-sdk/vue";
import { DefaultChatTransport } from "ai";

const chat = new Chat({
  id: chatId,
  messages: initialMessages,
  transport: new DefaultChatTransport({
    api: '/api/chat',
    body: () => ({ customData: 'value' })
  }),
  onFinish() { /* called when response completes */ },
  onError(error) { /* handle errors */ }
});
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `messages` | `UIMessage[]` | Current conversation history |
| `status` | `'ready' \| 'submitted' \| 'streaming' \| 'error'` | Current state |
| `error` | `Error \| undefined` | Error when status is 'error' |

### Methods

| Method | Description |
|--------|-------------|
| `sendMessage({ text, files? }, options?)` | Send a message to the API |
| `stop()` | Abort current streaming |
| `regenerate()` | Resend last message |

---

## 2. DefaultChatTransport

### Configuration Options

```typescript
new DefaultChatTransport({
  api: '/api/chat',                    // Endpoint path
  headers: () => ({ Auth: 'token' }),  // Static or function
  body: () => ({ extra: 'data' }),     // Static or function
  credentials: 'include',              // Fetch credentials mode
  prepareSendMessagesRequest: (ctx) => ({  // Transform request
    headers: {},
    body: {}
  })
})
```

### Body Function Timing

> "The body function executes immediately before sending each HTTP request, enabling dynamic data inclusion based on current application state."

**IMPORTANT**: The body function is called at request time, NOT when sendMessage is called. This means if you're setting state before sendMessage, it should be available when body() runs.

---

## 3. sendMessage Method

### Signature

```typescript
sendMessage(
  message: { text: string; files?: FileList | File[] },
  options?: { body?: object; headers?: object; metadata?: object }
)
```

### File Attachments

Two approaches:

**FileList from input:**
```typescript
sendMessage({
  text: input,
  files: fileInputRef.files  // FileList from <input type="file">
})
```

**File objects array:**
```typescript
sendMessage({
  text: input,
  files: [file1, file2]  // Array of File objects
})
```

The SDK automatically converts files to data URLs.

### Extra Body Data

Use the second parameter for per-request custom data:
```typescript
sendMessage(
  { text: input },
  { body: { customKey: 'value', rotationResults: [...] } }
)
```

Server receives: `{ messages, customKey, rotationResults }`

---

## 4. UIMessage Structure

```typescript
interface UIMessage {
  id: string;
  role: 'system' | 'user' | 'assistant';
  parts: MessagePart[];  // Content array
  status?: 'submitted' | 'streaming' | 'ready' | 'error';
  metadata?: object;
}
```

### Part Types

| Type | Description |
|------|-------------|
| `text` | Text content with `text` property |
| `file` | File attachment with `url`, `mediaType`, `filename` |
| `tool-{toolName}` | Tool invocation (e.g., `tool-getWeather`) |
| `reasoning` | AI reasoning/thinking content |

---

## 5. Tool Parts in Messages

### Tool Part Naming

Tools appear as parts with type `tool-{toolName}`:
- `tool-getWeatherInformation`
- `tool-detect_image_rotation`
- `tool-create_new_order`

### Tool States

```typescript
type ToolState =
  | 'input-streaming'    // Tool inputs being generated
  | 'input-available'    // Complete inputs ready
  | 'output-available'   // Execution finished with results
  | 'output-error';      // Execution failed
```

### Tool Part Structure

```typescript
interface ToolPart {
  type: `tool-${string}`;
  toolCallId: string;
  toolName: string;
  input?: object;        // Available after 'input-available'
  output?: object;       // Available after 'output-available'
  state: ToolState;
}
```

### Displaying Tools

```vue
<template v-for="part in message.parts">
  <div v-if="part.type.startsWith('tool-')">
    <div v-if="part.state === 'input-streaming'">Loading...</div>
    <div v-if="part.state === 'input-available'">Running: {{ part.input }}</div>
    <div v-if="part.state === 'output-available'">Result: {{ part.output }}</div>
  </div>
</template>
```

---

## 6. Stream Protocol (SSE Format)

### Required Headers

```
Content-Type: text/event-stream
x-vercel-ai-ui-message-stream: v1
```

### Event Types

#### Message Lifecycle
```json
{"type":"start","messageId":"msg_123"}
{"type":"finish"}
```
```
data: [DONE]
```

#### Text Streaming
```json
{"type":"text-start","id":"msg_123"}
{"type":"text-delta","id":"msg_123","delta":"Hello"}
{"type":"text-end","id":"msg_123"}
```

#### Tool Calling Sequence
```json
{"type":"tool-input-start","toolCallId":"call_123","toolName":"myTool"}
{"type":"tool-input-delta","toolCallId":"call_123","inputTextDelta":"..."}
{"type":"tool-input-available","toolCallId":"call_123","toolName":"myTool","input":{"key":"value"}}
{"type":"tool-output-available","toolCallId":"call_123","output":{"result":"data"}}
```

#### Step Management
```json
{"type":"start-step"}
{"type":"finish-step"}
```

---

## 7. Key Insights for Our Implementation

### Issue 1: handleSubmit Not Being Called

The current code uses `@submit="handleSubmit"` on UChatPrompt. Looking at the Nuxt guide, the proper pattern is:

```vue
<form @submit="handleSubmit">
  <input v-model="input" />
</form>

<script setup>
const handleSubmit = (e: Event) => {
  e.preventDefault();
  chat.sendMessage({ text: input.value });
  input.value = "";
};
</script>
```

UChatPrompt from Nuxt UI may have its own submission behavior that doesn't trigger `@submit` in the expected way.

### Issue 2: Passing Extra Data

**Current approach (may be problematic):**
```typescript
// Setting pendingRotationResults.value, then calling sendMessage
// Relying on transport body() to read it
```

**Recommended approach:**
```typescript
// Pass data directly with sendMessage
chat.sendMessage(
  { text: input, files: uploadedFiles },
  { body: { rotationResults: [...] } }  // Per-request body
)
```

### Issue 3: Streaming Custom Tools

To stream rotation as a tool call, backend must send:

```json
{"type":"tool-input-start","toolCallId":"rotation_123","toolName":"detect_image_rotation"}
{"type":"tool-input-available","toolCallId":"rotation_123","toolName":"detect_image_rotation","input":{"fileName":"image.jpg"}}
{"type":"tool-output-available","toolCallId":"rotation_123","output":{"rotation":180,"rotatedUrl":"..."}}
```

Frontend will then see a part with `type: 'tool-detect_image_rotation'`.

---

## 8. Recommended Pattern for Vue

```vue
<script setup lang="ts">
import { Chat } from '@ai-sdk/vue';
import { DefaultChatTransport } from 'ai';

const input = ref('');
const rotationData = ref([]);

const chat = new Chat({
  id: chatId,
  messages: initialMessages,
  transport: new DefaultChatTransport({
    api: `/api/chats/${chatId}`
  }),
  onFinish() {
    refreshSidebar();
  }
});

async function handleSubmit(e: Event) {
  e.preventDefault();

  // Wait for any pending async operations
  const rotations = await getCompletedRotations();

  // Send message with extra data in the OPTIONS parameter
  chat.sendMessage(
    { text: input.value, files: uploadedFiles.value },
    { body: { rotationResults: rotations } }
  );

  input.value = '';
  clearFiles();
}
</script>

<template>
  <form @submit="handleSubmit">
    <!-- Use native form for reliable submit handling -->
  </form>
</template>
```

---

## 9. Next Steps

Based on this research:

1. **Use sendMessage options.body** instead of transport body() for per-request data
2. **Use native form @submit** instead of UChatPrompt @submit for reliable handling
3. **Stream tools with proper format** - tool-input-start → tool-input-available → tool-output-available
4. **Check tool part type** - Use `tool-detect_image_rotation` not `tool-invocation`
