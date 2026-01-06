# Image Preprocessing Pipeline Redesign Plan

## Overview
Redesign the image preprocessing pipeline to:
1. Use YOLOE for document detection/cropping (instead of SAM3)
2. Generate labeled rotation variants (0°, 90°, 180°, 270°)
3. Use a simpler AI model (Gemini 2.5 Flash Lite) with visual labels
4. Let AI choose correct rotation AND whether cropped image should replace original

## Current Flow (to be replaced)
```
Image → Gemini 3 Flash (detect rotation) → Apply rotation → SAM3/Gemini (segment) → Result
```

## New Flow
```
Image → YOLOE (crop document) → Generate 5 labeled images → Gemini 2.5 Flash Lite (choose) → Apply choices
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

## Phase 2: Backend Changes

### 2.1 New Endpoint: `/api/preprocess-images`

**File:** `backend/server.py`

**Request:**
```python
class ImagePreprocessRequest(BaseModel):
    images: List[ImageData]  # List of {data: base64, mimeType: str, name: str}
    prompts: List[str] = ["document", "paper", "notebook", "book"]
    confidence_threshold: float = 0.3
```

**Response:**
```python
{
    "compositeImage": str,  # Base64 of composite image with all labeled variants
    "imageCount": int,      # Number of input images
    "variantsPerImage": int,  # 5 (4 rotations + 1 cropped) or 4 if no crop
    "labels": [             # Labels for AI reference
        {"imageIndex": 1, "label": "1: 0°", "type": "rotation", "rotation": 0},
        {"imageIndex": 1, "label": "1: 90°", "type": "rotation", "rotation": 90},
        {"imageIndex": 1, "label": "1: 180°", "type": "rotation", "rotation": 180},
        {"imageIndex": 1, "label": "1: 270°", "type": "rotation", "rotation": 270},
        {"imageIndex": 1, "label": "1: cropped", "type": "crop", "confidence": 0.43},
        {"imageIndex": 2, "label": "2: 0°", ...},
        ...
    ],
    "crops": [              # Crop info for each image
        {"imageIndex": 1, "hasCrop": true, "confidence": 0.43, "boundingBox": {...}},
        {"imageIndex": 2, "hasCrop": false, "reason": "no document detected"},
        ...
    ],
    "timing": {
        "yoloe_ms": 150,
        "rotation_ms": 50,
        "labeling_ms": 30,
        "total_ms": 230
    }
}
```

### 2.2 New Endpoint: `/api/apply-preprocessing`

**Purpose:** Apply the AI's rotation/crop choices to original images

**Request:**
```python
class ApplyPreprocessingRequest(BaseModel):
    images: List[ImageData]  # Original images
    choices: List[ImageChoice]  # AI's choices

class ImageChoice(BaseModel):
    imageIndex: int
    rotation: int  # 0, 90, 180, 270
    useCrop: bool  # Whether to use cropped version
```

**Response:**
```python
{
    "processedImages": [
        {"data": base64, "mimeType": str, "name": str, "rotation": int, "cropped": bool},
        ...
    ],
    "timing_ms": int
}
```

### 2.3 YOLOE Integration Module

**New file:** `backend/services/yoloe_service.py`

```python
class YOLOEService:
    def __init__(self):
        self.model = None
        self.prompts = ["document", "paper", "notebook", "book"]

    def load_model(self):
        """Lazy load YOLOE model"""
        if self.model is None:
            from ultralytics import YOLOE
            self.model = YOLOE("yoloe-11l-seg.pt")
            text_pe = self.model.get_text_pe(self.prompts)
            self.model.set_classes(self.prompts, text_pe)
        return self.model

    def detect_document(self, image_bytes: bytes, confidence_threshold: float = 0.3) -> Optional[CropResult]:
        """Detect document and return crop coordinates"""
        # Returns: {boundingBox, confidence, className} or None

    def crop_image(self, image_bytes: bytes, bbox: dict, padding: int = 10) -> bytes:
        """Crop image to bounding box with padding"""
```

### 2.4 Image Labeling Module

**New file:** `backend/services/image_labeling.py`

```python
class ImageLabelingService:
    def add_label(self, image_bytes: bytes, label: str, position: str = "top") -> bytes:
        """Add text label to top of image"""
        # Uses PIL to draw text on image
        # White background strip with black text
        # Font size proportional to image width

    def create_rotations(self, image_bytes: bytes) -> Dict[int, bytes]:
        """Create all 4 rotations: 0°, 90°, 180°, 270°"""
        # Returns: {0: bytes, 90: bytes, 180: bytes, 270: bytes}

    def create_composite(self, labeled_images: List[bytes], columns: int = 5) -> bytes:
        """Combine multiple images into a single composite image"""
        # Grid layout: 5 columns per row (4 rotations + crop)
        # Each row = one input image
```

---

## Phase 3: Frontend Changes

### 3.1 Update Image Processing Pipeline

**File:** `frontend-nuxt/server/api/chats/[id].post.ts`

**Replace current flow (lines 313-418) with:**

```typescript
// Step 1: Call backend to generate labeled composite
const preprocessResponse = await $fetch('/api/preprocess-images', {
    method: 'POST',
    body: { images: imagePartsArray }
});

// Step 2: Send composite to AI for choices
const aiChoices = await callPreprocessingAI(preprocessResponse.compositeImage, preprocessResponse.labels);

// Step 3: Apply AI choices to original images
const processedImages = await $fetch('/api/apply-preprocessing', {
    method: 'POST',
    body: {
        images: imagePartsArray,
        choices: aiChoices
    }
});

// Step 4: Replace original images with processed versions
// Continue with chat...
```

### 3.2 New Preprocessing AI Call

**File:** `frontend-nuxt/server/utils/imagePreprocessing.ts` (new)

```typescript
interface PreprocessingChoice {
    imageIndex: number;
    rotation: number;      // 0, 90, 180, 270
    useCrop: boolean;      // true if cropped version is better
    reasoning?: string;    // Optional explanation
}

async function callPreprocessingAI(
    compositeImage: string,
    labels: LabelInfo[]
): Promise<PreprocessingChoice[]> {
    // Call Gemini 2.5 Flash Lite
    // System prompt explains the task
    // Send composite image
    // Parse structured response
}
```

### 3.3 System Prompt for Preprocessing AI

```
You are an image preprocessing assistant. Your job is to help prepare images for another AI that will interpret them.

You are given a composite image containing labeled variants of input images:
- For each input image, you see 4-5 variants:
  - "N: 0°" - Original orientation
  - "N: 90°" - Rotated 90° clockwise
  - "N: 180°" - Rotated 180°
  - "N: 270°" - Rotated 270° clockwise
  - "N: cropped" - Zoomed/cropped version (if available)

Where N is the image number (1, 2, 3...).

Your tasks:
1. For each image, determine the CORRECT rotation (which variant shows text/content right-side up)
2. For each image with a cropped variant, decide if the crop IMPROVES readability:
   - Choose crop if it zooms in on relevant content without cutting off important information
   - Do NOT choose crop if it cuts off relevant data or text

Respond in this exact JSON format:
{
    "choices": [
        {"imageIndex": 1, "rotation": 0, "useCrop": false},
        {"imageIndex": 2, "rotation": 90, "useCrop": true},
        ...
    ]
}

IMPORTANT:
- The cropped variant is shown UNROTATED - your rotation choice will be applied to it
- Only recommend crop if it clearly helps focus on the document content
- When in doubt about crop, choose false (keep original)
```

---

## Phase 4: Tool Registration

### 4.1 New Tool: `use_cropped_images`

**File:** `backend/graph/tools.py`

```python
# This tool is called internally, not by the main AI
# It's used by the preprocessing AI to indicate crop choices

# Actually, this might not need to be a "tool" in the LangGraph sense
# It's more of a structured response from the preprocessing AI
```

**Decision:** The crop/rotation choices will be returned as structured JSON from the preprocessing AI, not as tool calls. This is simpler and more direct.

### 4.2 Update Tool Translations

**File:** `telegram_bot/utils/tools.py`

```python
"image-preprocessing": "🖼️ Preprocesando imágenes",
```

---

## Phase 5: Model Configuration

### 5.1 Update AI Model for Preprocessing

**Current:** `gemini-3-flash-preview` (overkill for this task)
**New:** `gemini-2.5-flash-lite` (sufficient with visual labels)

**File:** `backend/server.py` - new endpoint uses lighter model

```python
PREPROCESSING_MODEL = "gemini-2.5-flash-lite"
```

---

## Implementation Order

1. **Phase 1:** Delete test scripts (5 minutes)
2. **Phase 2.3:** Create YOLOE service module (30 minutes)
3. **Phase 2.4:** Create image labeling module (30 minutes)
4. **Phase 2.1-2.2:** Create new backend endpoints (45 minutes)
5. **Phase 3:** Update frontend pipeline (45 minutes)
6. **Phase 4-5:** Tool translations & model config (15 minutes)
7. **Testing & refinement** (30 minutes)

---

## Visual Example

For 2 input images, the composite would look like:

```
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│  1: 0°  │ 1: 90°  │ 1: 180° │ 1: 270° │1: cropped│
│  [img]  │  [img]  │  [img]  │  [img]  │  [img]  │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│  2: 0°  │ 2: 90°  │ 2: 180° │ 2: 270° │2: cropped│
│  [img]  │  [img]  │  [img]  │  [img]  │  [img]  │
└─────────┴─────────┴─────────┴─────────┴─────────┘
```

Each cell has:
- White header bar with black text label
- The image variant below

---

## Questions/Decisions Needed

1. **Composite image size:** Should we resize images to fit a max composite size? (e.g., max 4096x4096)
2. **Crop confidence threshold:** Default 0.3 - is this good?
3. **What if no document detected?** Still show "N: cropped" with original, or omit?
4. **Multiple documents in one image?** Use largest detection only?
5. **Telegram integration:** Does this flow work the same for Telegram?

---

## Files to Create/Modify

### New Files:
- `backend/services/yoloe_service.py`
- `backend/services/image_labeling.py`
- `frontend-nuxt/server/utils/imagePreprocessing.ts`

### Modified Files:
- `backend/server.py` (add 2 new endpoints)
- `frontend-nuxt/server/api/chats/[id].post.ts` (update pipeline)
- `telegram_bot/utils/tools.py` (add translation)

### Deleted Files:
- `backend/test_sam2.py`
- `backend/test_sam3.py`
- `backend/test_fastsam.py`
- `backend/test_yolo12.py`
- `backend/test_yolo_world.py`
