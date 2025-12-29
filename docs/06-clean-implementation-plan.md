# Clean Feature Implementation Plan

## Current State

We are at commit `bd0b133` - the last known stable state with working:
- Chat streaming
- Title generation (refreshNuxtData on finish)
- Basic file upload

## Analysis of Attempted Features

### Tier 1: Working Features (from f4aa1a5 and earlier)
These features worked correctly and should be restored:

| Feature | Commits | Status |
|---------|---------|--------|
| Dynamic free models with latency sorting | 702e29b, da70b54 | ✅ Works |
| Microphone recording | 0ba8e99 | ✅ Works |
| Camera capture | 0ba8e99 | ✅ Works |
| Stats toggle | 0ba8e99 | ✅ Works |
| Image lightbox | c7f4a3d | ✅ Works |
| Audio/video playback | c7f4a3d | ✅ Works |
| Image rotation detection | 03f10c9 | ✅ Works |
| Non-blocking upload (typing after paste) | f4aa1a5 | ✅ Works |
| Focus fix after paste | f4aa1a5 | ✅ Works |

### Tier 2: Features That Caused Issues
These were attempted but broke the app:

| Feature | Commits | Problem |
|---------|---------|---------|
| Rotation tool display in AI response | 25bee7a, 4c19de0 | Complex integration with AI SDK stream |
| Wait for rotation before send | 9b34164 | Blocked submission, reactivity issues |
| Move rotation to Python backend | b99b054 | Unnecessarily complex |

### Tier 3: New Features (from ee0f3d2)
These are new features that should work if added correctly:

| Feature | Status |
|---------|--------|
| Per-message regenerate | Can be added cleanly |
| TTS (Text-to-Speech) | Can be added cleanly |
| Improved message actions UI | Can be added cleanly |

---

## Implementation Plan

### Phase 1: Restore Working Features from f4aa1a5
**Goal:** Get back to the state where image rotation and typing after paste work.

#### Step 1.1: Add Dynamic Free Models Utility
Copy from da70b54:
- `frontend-nuxt/server/utils/openrouter-models.ts` - Free text models with latency sorting
- Update title generation to use dynamic models

#### Step 1.2: Add Microphone, Camera, Stats (0ba8e99)
Copy components and composables:
- `frontend-nuxt/app/components/CameraCapture.vue`
- `frontend-nuxt/app/composables/useShowStats.ts`
- Update layouts/default.vue for stats toggle
- Update pages for microphone/camera buttons

#### Step 1.3: Add Image Lightbox and Audio Playback (c7f4a3d)
- `frontend-nuxt/app/components/ImageLightbox.vue`
- Update FileAvatar.vue for audio/video playback

#### Step 1.4: Add Image Rotation Detection (03f10c9)
- `frontend-nuxt/server/api/detect-rotation.post.ts`
- `frontend-nuxt/server/utils/openrouter-vision-models.ts`
- `frontend-nuxt/app/utils/imageRotation.ts`
- `frontend-nuxt/app/composables/useImageRotation.ts`
- Update useFileUpload.ts for rotation integration
- Update FileAvatar.vue for rotation badge

#### Step 1.5: Apply f4aa1a5 Fixes
- Fix vision models API to use official endpoint
- Remove disabled state during upload (only disable during recording)
- Fix focus after paste with setTimeout delay

---

### Phase 2: Add Safe New Features
**Goal:** Add features that don't interfere with core message flow.

#### Step 2.1: TTS (Text-to-Speech)
Simple browser SpeechSynthesis API:
- Create `frontend-nuxt/app/composables/useTTS.ts`
- Add TTS button to message actions

#### Step 2.2: Per-Message Regenerate
- Add `regenerateMessage(messageId)` function
- Add regenerate button to message actions

#### Step 2.3: Improved Message Actions UI
- Add hover-revealed action buttons
- Group class for message containers

---

### Phase 3: Future Enhancements (Optional)
These could be added later if needed:

#### 3.1: Show Rotation as Tool Call
This is complex and may not be worth the effort:
- Would require modifying AI SDK stream
- The rotation already shows as a badge on the image
- Users can see the rotated preview

#### 3.2: Enhanced Title Generation
- Use Lobe Chat's prompt pattern (already in plan)
- Add streaming title updates

---

## File Changes Summary

### New Files to Create
```
frontend-nuxt/server/utils/openrouter-models.ts
frontend-nuxt/server/utils/openrouter-vision-models.ts
frontend-nuxt/server/api/detect-rotation.post.ts
frontend-nuxt/app/components/CameraCapture.vue
frontend-nuxt/app/components/ImageLightbox.vue
frontend-nuxt/app/composables/useShowStats.ts
frontend-nuxt/app/composables/useTTS.ts
frontend-nuxt/app/utils/imageRotation.ts
```

### Files to Modify
```
frontend-nuxt/app/components/FileAvatar.vue
frontend-nuxt/app/composables/useFileUpload.ts
frontend-nuxt/app/layouts/default.vue
frontend-nuxt/app/pages/chat/[id].vue
frontend-nuxt/app/pages/index.vue
frontend-nuxt/server/api/chats/[id].post.ts
frontend-nuxt/shared/utils/file.ts
```

---

## Testing Checklist

After each phase, verify:

### Phase 1 Tests
- [ ] Paste image → can immediately continue typing
- [ ] Image rotation detected and applied
- [ ] Rotation badge shows on rotated images
- [ ] Camera capture works
- [ ] Microphone recording works
- [ ] Audio files play in chat
- [ ] Image lightbox opens on click
- [ ] Chat title generates after first message
- [ ] Message streaming works without issues

### Phase 2 Tests
- [ ] TTS reads message aloud
- [ ] TTS stop button works
- [ ] Per-message regenerate works
- [ ] Message actions appear on hover

---

## Key Principles

1. **Don't block the user** - Never disable input while background processing
2. **Keep it in frontend** - Rotation detection in Nuxt server, not Python backend
3. **Simple over complex** - Rotation badge is simpler than tool call display
4. **Test incrementally** - Verify each phase works before moving on

---

## Approval Checklist

- [ ] Phase 1 plan approved
- [ ] Phase 2 plan approved
- [ ] Phase 3 deferred (optional)
- [ ] Ready to implement
