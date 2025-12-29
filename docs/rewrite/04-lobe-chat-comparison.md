# Lobe Chat Comparison & Learnings

## Overview

This document compares the Lab AI Assistant implementation with [Lobe Chat](https://github.com/lobehub/lobe-chat) to identify better patterns we can adopt.

---

## 1. Topic/Title Generation

### Lobe Chat Approach

**Location:** `src/store/chat/slices/topic/action.ts`

**Key Features:**
1. **Streaming title generation** - Title updates in real-time as it's generated
2. **Uses dedicated prompt** - `chainSummaryTitle` from `@lobechat/prompts`
3. **Supports loading state** - Shows "..." while generating
4. **Configurable system agent** - Users can customize the title generation model

**Prompt (from `packages/prompts/src/chains/summaryTitle.ts`):**
```typescript
{
  content: `You are a professional conversation summarizer. Generate a concise title that captures the essence of the conversation.

Rules:
- Output ONLY the title text, no explanations or additional context
- Maximum 10 words
- Maximum 50 characters
- No punctuation marks
- Use the language specified by the locale code: ${locale}
- The title should accurately reflect the main topic of the conversation
- Keep it short and to the point`,
  role: 'system',
}
```

**Flow:**
```
1. saveToTopic() called after messages
   └── Creates topic with default title
   └── Calls summaryTopicTitle() async (fire-and-forget)

2. summaryTopicTitle(topicId, messages)
   └── Shows LOADING_FLAT ("...") in UI
   └── Streams title generation
   └── Updates title in real-time via onMessageHandle
   └── Saves final title to DB
```

### Our Current Approach

```typescript
// Fire-and-forget title generation after saving message
if (needsTitle) {
  generateTitle(chatId, textContent).catch(...)
}
```

### What We Should Copy

1. **Better prompt** - Their prompt is more specific with clear rules
2. **Locale awareness** - They pass the user's language
3. **Streaming updates** - Show title generating in real-time
4. **Loading indicator** - Show "..." while generating

### Recommended Changes

```typescript
// New title generation prompt
const TITLE_PROMPT = `You are a professional conversation summarizer. Generate a concise title.

Rules:
- Output ONLY the title text, no explanations
- Maximum 10 words, 50 characters
- No punctuation marks
- Use language: ${locale}
- Accurately reflect the main topic`;
```

---

## 2. Image Thumbnails in Chat

### Lobe Chat Approach

**Location:** `src/features/ChatList/Messages/User/ImageFileListViewer.tsx`

**Components:**
- `ImageFileListViewer` - Renders image grid
- `GalleyGrid` - Grid layout component
- `ImageItem` - Individual image thumbnail
- `PreviewGroup` - Lightbox/preview functionality

**Features:**
1. Grid layout for multiple images
2. Click to open lightbox preview
3. Loading states for images
4. Remove button on images

### Our Current Approach

We have `FileAvatar` component that shows thumbnails, but:
- No grid layout for multiple images
- Basic lightbox via `ImageLightbox`
- No loading indicator on images

### What We Should Copy

1. **Grid layout** - Display multiple images in a nice grid
2. **Unified preview group** - Click any image to preview, navigate between them

### Recommended Component Pattern

```vue
<ImageGallery :images="imageFiles">
  <template #item="{ image }">
    <ImageThumbnail
      :src="image.url"
      :loading="image.loading"
      @click="openPreview(image)"
    />
  </template>
</ImageGallery>
```

---

## 3. Regenerate Message

### Lobe Chat Approach

**Location:** `src/features/ChatList/Messages/Assistant/Actions/index.tsx`

**Actions available on assistant messages:**
- `regenerate` - Regenerate this response
- `delAndRegenerate` - Delete and regenerate
- `edit` - Edit the message
- `copy` - Copy to clipboard
- `tts` - Text-to-speech
- `translate` - Translate to another language
- `branching` - Create thread/branch from message
- `share` - Share message
- `collapse/expand` - Collapse long messages

**Store methods:**
```typescript
regenerateAssistantMessage(id)
delAndRegenerateMessage(id)
```

### Our Current Approach

We have `chat.regenerate()` but:
- Only regenerates the last message
- No per-message regeneration
- No delete-and-regenerate option

### What We Should Copy

1. **Per-message regeneration** - Regenerate any message, not just the last
2. **Delete and regenerate** - Combined action
3. **Action menu** - Clean dropdown menu for all actions

### Recommended Implementation

```typescript
// In chat store or composable
function regenerateMessage(messageId: string) {
  // Find message index
  // Remove all messages after it
  // Resend to get new response
}

function deleteAndRegenerateMessage(messageId: string) {
  // Delete the message
  // Regenerate from the previous user message
}
```

---

## 4. Branching/Threading

### Lobe Chat Approach

**Concept:** Create a "thread" or "branch" from any assistant message to explore alternative responses.

**Location:** `src/store/chat/slices/thread/action.ts`

**Features:**
- Create thread from any message
- Threads have their own title (auto-generated)
- Navigate between main chat and threads
- Threads preserve context up to branch point

### Our Current Approach

We don't have this feature.

### Should We Implement?

**Recommendation:** Nice-to-have but not critical. Can be added later.

---

## 5. Text-to-Speech (TTS)

### Lobe Chat Approach

**Location:** `src/hooks/useTTS.ts`

**Supports multiple TTS services:**
- OpenAI TTS
- Microsoft Speech
- Edge Speech (free, runs in browser)

**Features:**
- Per-message TTS button
- Configurable voice
- Caches audio files to avoid re-generation
- Voice preview in settings

**Components:**
- `TTS/index.tsx` - Main component
- `TTS/Player.tsx` - Audio player UI
- `TTS/FilePlayer.tsx` - Plays cached audio
- `TTS/InitPlayer.tsx` - Generates and plays new audio

### Our Current Approach

We don't have TTS.

### What We Should Implement

1. **Basic TTS** - Use browser's built-in `SpeechSynthesis` API (free)
2. **Per-message button** - Add "Read aloud" to message actions
3. **Stop button** - Ability to stop reading

**Simple Implementation:**

```typescript
function speakMessage(text: string) {
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'es-ES'; // Spanish
  speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  speechSynthesis.cancel();
}
```

---

## 6. Message Actions Pattern

### Lobe Chat Pattern

Uses `ActionIconGroup` from `@lobehub/ui`:

```tsx
<ActionIconGroup
  items={[edit, copy, branching]}
  menu={{
    items: [tts, translate, divider, regenerate, del]
  }}
  onActionClick={handleAction}
/>
```

**Pattern:**
- Primary actions shown as icons
- Secondary actions in dropdown menu
- Consistent across all message types

### Our Current Approach

We have limited actions via `UChatMessages` assistant prop.

### What We Should Copy

Create a consistent message actions component:

```vue
<MessageActions
  :message="message"
  :primary-actions="['copy', 'regenerate']"
  :menu-actions="['edit', 'tts', 'delete']"
/>
```

---

## 7. Key Differences Summary

| Feature | Lobe Chat | Lab AI Assistant | Recommendation |
|---------|-----------|------------------|----------------|
| Title Generation | Streaming, locale-aware | Fire-and-forget | **Copy their approach** |
| Title Prompt | Detailed rules | Simple | **Copy their prompt** |
| Image Gallery | Grid + preview group | Single thumbnails | **Implement grid** |
| Regenerate | Per-message | Last message only | **Add per-message** |
| TTS | Multiple providers | None | **Add browser TTS** |
| Branching | Full support | None | Nice-to-have |
| Message Actions | Rich dropdown menu | Limited | **Add action menu** |
| Loading States | Granular per-item | Basic | Improve |

---

## 8. Priority Implementation Order

### High Priority (Fix broken features first)
1. Fix title generation with better prompt
2. Fix rotation tool display

### Medium Priority (Nice improvements)
3. Add per-message regenerate
4. Add browser TTS (Read aloud)
5. Improve image gallery with grid layout

### Low Priority (Future enhancements)
6. Message action dropdown menu
7. Branching/threading
8. Multiple TTS providers

---

## 9. Code Patterns to Adopt

### Pattern 1: Streaming Updates

Lobe Chat shows loading/streaming states everywhere:

```typescript
// Set loading
internal_updateTopicTitleInSummary(topicId, LOADING_FLAT);

// Stream updates
onMessageHandle: (chunk) => {
  output += chunk.text;
  internal_updateTopicTitleInSummary(topicId, output);
}

// Final update
onFinish: async (text) => {
  await internal_updateTopic(topicId, { title: text });
}
```

### Pattern 2: Action Hooks

They use hooks to define consistent actions:

```typescript
const useChatListActionsBar = () => ({
  regenerate: {
    icon: RotateCcw,
    key: 'regenerate',
    label: t('regenerate'),
    disabled: isRegenerating,
    spin: isRegenerating
  },
  // ...
});
```

### Pattern 3: Locale-Aware Prompts

Always pass user's language to AI prompts:

```typescript
chainSummaryTitle(messages, globalHelpers.getCurrentLanguage())
```

---

## 10. Next Steps

1. Update `03-coding-plan.md` with these learnings
2. Add title streaming with better prompt
3. Add message actions (regenerate, TTS)
4. Improve image display
