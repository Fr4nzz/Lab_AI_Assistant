# Image Preprocessing Pipeline Redesign Plan (v2)

## Overview
Redesign the image preprocessing pipeline to:
1. Use YOLOE for document detection/cropping (instead of SAM3)
2. Generate 4 rotation variants (0°, 90°, 180°, 270°) + cropped version (if detected)
3. Send all variants as **separate images** (not composite) - Gemini supports multi-image
4. Add text labels on each image so AI can reference them
5. Use configurable model (default: `gemini-flash-lite-latest`)
6. Add thinking level dropdown (default: low)
7. Synchronize settings between Frontend and Telegram

## Current Flow (to be replaced)
```
Image → Gemini 3 Flash (detect rotation) → Apply rotation → SAM3/Gemini (segment) → Result
```

## New Flow
```
Image → YOLOE (crop) → Generate labeled variants → Send as separate images → AI chooses → Apply
```

---

## Phase 1: Cleanup - Delete Unused Test Scripts

**Files to delete:**
- `backend/test_sam2.py`
- `backend/test_sam3.py`
- `backend/test_fastsam.py`
- `backend/test_yolo12.py`
- `backend/test_yolo_world.py`

**File to keep:**
- `backend/test_yoloe.py` (for testing/debugging)

---

## Phase 2: Settings Storage & Synchronization

### 2.1 Database Schema Update

**File:** `frontend-nuxt/server/db/schema.ts`

Add user settings table:
```typescript
export const userSettings = sqliteTable('user_settings', {
  id: text('id').primaryKey().$defaultFn(() => createId()),
  visitorId: text('visitor_id').unique(),  // For anonymous users
  userId: text('user_id').references(() => users.id, { onDelete: 'cascade' }),

  // Preprocessing settings
  preprocessingModel: text('preprocessing_model').default('gemini-flash-lite-latest'),
  thinkingLevel: text('thinking_level').default('low'),

  // Main chat model (existing setting, now persisted)
  chatModel: text('chat_model').default('gemini-3-flash-preview'),

  ...timestamps
})
```

### 2.2 Settings API Endpoints

**New file:** `frontend-nuxt/server/api/settings.get.ts`
```typescript
// GET /api/settings - Get current user settings
// Returns: { preprocessingModel, thinkingLevel, chatModel }
```

**New file:** `frontend-nuxt/server/api/settings.post.ts`
```typescript
// POST /api/settings - Update user settings
// Body: { preprocessingModel?, thinkingLevel?, chatModel? }
// Saves to database, returns updated settings
```

### 2.3 Frontend Settings UI

**Modified file:** `frontend-nuxt/app/components/ModelSelect.vue`

Add dropdowns for:
1. **Main Model** (existing, but now synced to DB)
2. **Preprocessing Model**: `gemini-flash-lite-latest`, `gemini-flash-latest`, `gemini-3-flash-preview`
3. **Thinking Level**: `none`, `low` (default), `medium`, `high`

```typescript
const PREPROCESSING_MODELS = [
  { id: 'gemini-flash-lite-latest', name: 'Gemini 2.5 Flash Lite (fastest)' },
  { id: 'gemini-flash-latest', name: 'Gemini 2.5 Flash' },
  { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash (best)' },
]

const THINKING_LEVELS = [
  { id: 'none', name: 'None (fastest)' },
  { id: 'low', name: 'Low (default)' },
  { id: 'medium', name: 'Medium' },
  { id: 'high', name: 'High (most thorough)' },
]
```

### 2.4 Frontend Settings Composable

**New file:** `frontend-nuxt/app/composables/useSettings.ts`

```typescript
export function useSettings() {
  const settings = useState('userSettings', () => ({
    preprocessingModel: 'gemini-flash-lite-latest',
    thinkingLevel: 'low',
    chatModel: 'gemini-3-flash-preview'
  }))

  // Load settings from API on init
  async function loadSettings() {
    const data = await $fetch('/api/settings')
    settings.value = data
  }

  // Save settings to API
  async function saveSettings(updates: Partial<Settings>) {
    const data = await $fetch('/api/settings', {
      method: 'POST',
      body: updates
    })
    settings.value = data
  }

  return { settings, loadSettings, saveSettings }
}
```

### 2.5 Telegram Settings Integration

**Modified file:** `telegram_bot/keyboards/inline.py`

Add new keyboard builders:
```python
PREPROCESSING_MODELS = {
    "gemini-flash-lite-latest": "Gemini 2.5 Flash Lite ⚡",
    "gemini-flash-latest": "Gemini 2.5 Flash",
    "gemini-3-flash-preview": "Gemini 3 Flash 🧠",
}

THINKING_LEVELS = {
    "none": "None ⚡",
    "low": "Low (default)",
    "medium": "Medium",
    "high": "High 🧠",
}

def build_preprocessing_model_keyboard(current: str) -> InlineKeyboardMarkup:
    # Similar to build_model_selection_keyboard()

def build_thinking_level_keyboard(current: str) -> InlineKeyboardMarkup:
    # Similar structure
```

**Modified file:** `telegram_bot/handlers/callbacks.py`

Add handlers:
```python
elif data.startswith("preprocess:"):
    await handle_preprocessing_model_selection(query, context, data[10:])
elif data.startswith("thinking:"):
    await handle_thinking_level_selection(query, context, data[9:])
```

**Key change:** Instead of storing in `context.user_data`, call the frontend settings API:
```python
async def handle_preprocessing_model_selection(query, context, model_id):
    visitor_id = get_visitor_id(context)  # Use telegram user_id as visitor_id
    await save_setting(visitor_id, "preprocessingModel", model_id)
    # This syncs with frontend!
```

### 2.6 Telegram Commands

**Modified file:** `telegram_bot/bot.py`

Add commands:
- `/preprocess` - Show preprocessing model selection
- `/thinking` - Show thinking level selection

Or combine into `/settings` command that shows all options.

---

## Phase 3: Backend Preprocessing Service

### 3.1 YOLOE Service Module

**New file:** `backend/services/yoloe_service.py`

```python
from typing import Optional, List, Tuple
from PIL import Image
import io

class YOLOEService:
    _instance = None

    def __init__(self):
        self.model = None
        self.prompts = ["document", "paper", "notebook", "book"]

    @classmethod
    def get_instance(cls) -> 'YOLOEService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self):
        """Lazy load YOLOE model (singleton)"""
        if self.model is None:
            from ultralytics import YOLOE
            self.model = YOLOE("yoloe-11l-seg.pt")
            text_pe = self.model.get_text_pe(self.prompts)
            self.model.set_classes(self.prompts, text_pe)
        return self.model

    def detect_document(
        self,
        image_bytes: bytes,
        confidence_threshold: float = 0.3
    ) -> Optional[dict]:
        """
        Detect document and return crop info.
        Returns: {boundingBox: {x1,y1,x2,y2}, confidence, className} or None
        """
        model = self.load_model()
        # ... implementation

    def crop_image(
        self,
        image: Image.Image,
        bbox: dict,
        padding: int = 10
    ) -> Image.Image:
        """Crop image to bounding box with padding"""
        # ... implementation
```

### 3.2 Image Labeling Service

**New file:** `backend/services/image_labeling.py`

```python
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict
import io

class ImageLabelingService:
    def __init__(self):
        self.font_size_ratio = 0.05  # 5% of image height
        self.label_bg_color = (255, 255, 255)  # White
        self.label_text_color = (0, 0, 0)  # Black

    def add_label(
        self,
        image: Image.Image,
        label: str
    ) -> Image.Image:
        """
        Add text label to TOP of image.
        Returns new image with label bar added.
        """
        width, height = image.size
        font_size = max(20, int(height * self.font_size_ratio))
        label_height = font_size + 10

        # Create new image with label space
        new_image = Image.new('RGB', (width, height + label_height), self.label_bg_color)

        # Draw label text
        draw = ImageDraw.Draw(new_image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_x = (width - (text_bbox[2] - text_bbox[0])) // 2
        draw.text((text_x, 5), label, fill=self.label_text_color, font=font)

        # Paste original image below label
        new_image.paste(image, (0, label_height))

        return new_image

    def create_rotations(self, image: Image.Image) -> Dict[int, Image.Image]:
        """Create all 4 rotations: 0°, 90°, 180°, 270°"""
        return {
            0: image.copy(),
            90: image.rotate(-90, expand=True),
            180: image.rotate(180, expand=True),
            270: image.rotate(-270, expand=True),
        }

    def resize_if_needed(self, image: Image.Image, max_size: int = 1080) -> Image.Image:
        """Resize image to max 1080p if larger, preserving aspect ratio"""
        width, height = image.size
        if width <= max_size and height <= max_size:
            return image

        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
```

### 3.3 Preprocessing Endpoint

**Modified file:** `backend/server.py`

**New endpoint:** `POST /api/preprocess-images`

```python
class ImagePreprocessRequest(BaseModel):
    images: List[ImageData]  # [{data: base64, mimeType: str, name: str}]
    preprocessingModel: str = "gemini-flash-lite-latest"
    thinkingLevel: str = "low"

class ImagePreprocessResponse(BaseModel):
    variants: List[ImageVariant]  # All labeled image variants
    labels: List[LabelInfo]       # Label metadata for AI
    crops: List[CropInfo]         # Crop info per input image
    timing: TimingInfo

@app.post("/api/preprocess-images")
async def preprocess_images(request: ImagePreprocessRequest):
    """
    Generate labeled rotation variants + crop for each input image.
    Returns separate images (not composite) for Gemini multi-image support.
    """
    yoloe = YOLOEService.get_instance()
    labeler = ImageLabelingService()

    variants = []
    labels = []
    crops = []

    for idx, img_data in enumerate(request.images):
        image_num = idx + 1
        image = decode_image(img_data.data)
        image = labeler.resize_if_needed(image, max_size=1080)

        # Create 4 rotations
        rotations = labeler.create_rotations(image)
        for rotation, rotated_img in rotations.items():
            label = f"{image_num}: {rotation}°"
            labeled = labeler.add_label(rotated_img, label)
            variants.append(encode_image(labeled))
            labels.append({"imageIndex": image_num, "label": label, "type": "rotation", "rotation": rotation})

        # Try to detect and crop document
        crop_result = yoloe.detect_document(img_data.data)
        if crop_result and crop_result["confidence"] >= 0.3:
            cropped = yoloe.crop_image(image, crop_result["boundingBox"])
            label = f"{image_num}: cropped"
            labeled = labeler.add_label(cropped, label)
            variants.append(encode_image(labeled))
            labels.append({"imageIndex": image_num, "label": label, "type": "crop"})
            crops.append({"imageIndex": image_num, "hasCrop": True, **crop_result})
        else:
            crops.append({"imageIndex": image_num, "hasCrop": False})

    return ImagePreprocessResponse(variants=variants, labels=labels, crops=crops, timing=...)
```

### 3.4 AI Selection Endpoint

**New endpoint:** `POST /api/select-preprocessing`

```python
@app.post("/api/select-preprocessing")
async def select_preprocessing(request: SelectPreprocessingRequest):
    """
    Send all variants to AI, get rotation + crop choices.
    Uses configurable model and thinking level.
    """
    model = get_preprocessing_model(
        model_name=request.preprocessingModel,
        thinking_level=request.thinkingLevel
    )

    # Build multi-image message for Gemini
    content = []
    for variant in request.variants:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{variant}"}
        })

    content.append({
        "type": "text",
        "text": PREPROCESSING_SYSTEM_PROMPT + "\n\n" + format_labels(request.labels)
    })

    response = await model.ainvoke([HumanMessage(content=content)])
    choices = parse_ai_choices(response.content)

    return {"choices": choices}
```

### 3.5 Apply Choices Endpoint

**New endpoint:** `POST /api/apply-preprocessing`

```python
@app.post("/api/apply-preprocessing")
async def apply_preprocessing(request: ApplyPreprocessingRequest):
    """Apply AI's rotation/crop choices to original images"""
    processed = []

    for choice in request.choices:
        original = request.images[choice.imageIndex - 1]
        image = decode_image(original.data)

        # Apply rotation
        if choice.rotation != 0:
            image = image.rotate(-choice.rotation, expand=True)

        # Apply crop if chosen
        if choice.useCrop:
            crop_info = request.crops[choice.imageIndex - 1]
            if crop_info.hasCrop:
                image = crop_to_bbox(image, crop_info.boundingBox)

        processed.append(encode_image(image))

    return {"processedImages": processed}
```

---

## Phase 4: Frontend Integration

### 4.1 Update Chat API

**Modified file:** `frontend-nuxt/server/api/chats/[id].post.ts`

Replace current rotation/segmentation flow (lines 313-418) with:

```typescript
// Step 1: Get user settings
const settings = await getUserSettings(visitorId)

// Step 2: Preprocess images (YOLOE + rotations + labels)
const preprocessResult = await $fetch('/api/preprocess-images', {
  method: 'POST',
  body: {
    images: imageParts,
    preprocessingModel: settings.preprocessingModel,
    thinkingLevel: settings.thinkingLevel
  }
})

// Step 3: Send variants to AI for selection
const aiSelection = await $fetch('/api/select-preprocessing', {
  method: 'POST',
  body: {
    variants: preprocessResult.variants,
    labels: preprocessResult.labels,
    preprocessingModel: settings.preprocessingModel,
    thinkingLevel: settings.thinkingLevel
  }
})

// Step 4: Apply AI choices
const processedImages = await $fetch('/api/apply-preprocessing', {
  method: 'POST',
  body: {
    images: imageParts,
    choices: aiSelection.choices,
    crops: preprocessResult.crops
  }
})

// Step 5: Replace images in message with processed versions
// Continue with chat...
```

### 4.2 Emit Tool Events for UI Feedback

```typescript
// Emit preprocessing status for user visibility
emitToolCall(writer, {
  type: 'tool-call',
  toolCallId: 'preprocessing-1',
  toolName: 'image-preprocessing',
  args: { imageCount: imageParts.length }
})

// After completion
emitToolResult(writer, {
  type: 'tool-result',
  toolCallId: 'preprocessing-1',
  result: {
    rotations: aiSelection.choices.map(c => c.rotation),
    cropsUsed: aiSelection.choices.filter(c => c.useCrop).length
  }
})
```

---

## Phase 5: System Prompt for Preprocessing AI

**New constant in:** `backend/server.py`

```python
PREPROCESSING_SYSTEM_PROMPT = """You are an image preprocessing assistant. Your job is to prepare images for another AI that will interpret them.

You are given multiple labeled images. For each input image, you see:
- "N: 0°" - Original orientation
- "N: 90°" - Rotated 90° clockwise
- "N: 180°" - Rotated 180°
- "N: 270°" - Rotated 270° clockwise
- "N: cropped" - Zoomed/cropped version (if available)

Where N is the image number (1, 2, 3...).

YOUR TASKS:
1. For each image, determine the CORRECT rotation (which shows text/content right-side up and readable)
2. For images with a cropped variant, decide if the crop IMPROVES readability:
   - Choose crop=true if it zooms in on relevant content WITHOUT cutting off important information
   - Choose crop=false if the crop cuts off relevant data, text, or context

RESPOND WITH ONLY THIS JSON FORMAT:
{
  "choices": [
    {"imageIndex": 1, "rotation": 0, "useCrop": false},
    {"imageIndex": 2, "rotation": 90, "useCrop": true}
  ]
}

IMPORTANT NOTES:
- The cropped variant is shown UNROTATED - your rotation choice will be applied to it
- Only recommend useCrop:true if it clearly helps focus on document content
- When in doubt about crop, choose useCrop:false (keep original framing)
- Rotation values must be exactly: 0, 90, 180, or 270"""
```

---

## Phase 6: Tool Registration & Translations

### 6.1 Update Tool Translations

**Modified file:** `telegram_bot/utils/tools.py`

```python
TOOL_TRANSLATIONS = {
    # ... existing ...
    "image-preprocessing": "🖼️ Preprocesando imágenes",
}
```

**Modified file:** `backend/graph/tools.py`

```python
TOOL_NAME_TRANSLATIONS = {
    # ... existing ...
    "image-preprocessing": "🖼️ Preprocesando imágenes",
}
```

---

## Implementation Order

1. **Phase 1:** Delete test scripts (5 min)
2. **Phase 2.1-2.2:** Database schema + settings API (30 min)
3. **Phase 2.3-2.4:** Frontend settings UI + composable (30 min)
4. **Phase 2.5-2.6:** Telegram settings integration (30 min)
5. **Phase 3.1-3.2:** YOLOE + labeling services (45 min)
6. **Phase 3.3-3.5:** Backend preprocessing endpoints (45 min)
7. **Phase 4:** Frontend chat API integration (30 min)
8. **Phase 5-6:** System prompt + translations (15 min)
9. **Testing & refinement** (30 min)

---

## Key Design Decisions

| Question | Answer |
|----------|--------|
| Composite vs separate images? | **Separate** - Gemini supports multi-image natively |
| Image resize limit? | **1080p max**, preserve aspect ratio |
| No document detected? | **Omit** cropped variant entirely |
| Multiple documents? | Use **largest** detection only |
| Telegram sync? | **Shared database** - same settings for both |
| Default preprocessing model? | `gemini-flash-lite-latest` |
| Default thinking level? | `low` |

---

## Files Summary

### New Files:
- `backend/services/yoloe_service.py`
- `backend/services/image_labeling.py`
- `frontend-nuxt/server/api/settings.get.ts`
- `frontend-nuxt/server/api/settings.post.ts`
- `frontend-nuxt/app/composables/useSettings.ts`

### Modified Files:
- `frontend-nuxt/server/db/schema.ts` (add userSettings table)
- `frontend-nuxt/server/api/chats/[id].post.ts` (new preprocessing flow)
- `frontend-nuxt/app/components/ModelSelect.vue` (add dropdowns)
- `backend/server.py` (add 3 new endpoints)
- `telegram_bot/keyboards/inline.py` (add settings keyboards)
- `telegram_bot/handlers/callbacks.py` (add settings handlers)
- `telegram_bot/bot.py` (add /settings command)
- `telegram_bot/utils/tools.py` (add translation)
- `backend/graph/tools.py` (add translation)

### Deleted Files:
- `backend/test_sam2.py`
- `backend/test_sam3.py`
- `backend/test_fastsam.py`
- `backend/test_yolo12.py`
- `backend/test_yolo_world.py`
