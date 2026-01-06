"""
YOLOE service for text-prompted document detection.

Uses YOLOE (YOLO with text prompts) to detect documents in images.
Supports prompts like: document, paper, notebook, book
"""

import io
import logging
from typing import Optional, Tuple
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class YOLOEService:
    """
    Singleton service for YOLOE text-prompted document detection.

    Uses lazy loading to avoid loading the model until needed.
    """

    _instance = None

    # Default prompts for document detection
    DEFAULT_PROMPTS = ["document", "paper", "notebook", "book"]

    # Model to use (L = Large for better accuracy)
    MODEL_NAME = "yoloe-11l-seg.pt"

    def __init__(self):
        self.model = None
        self.prompts = self.DEFAULT_PROMPTS
        self._initialized = False

    @classmethod
    def get_instance(cls) -> 'YOLOEService':
        """Get singleton instance of YOLOE service."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self, force_cpu: bool = False):
        """
        Lazy load YOLOE model (singleton).

        Args:
            force_cpu: Force CPU usage (no GPU)

        Returns:
            Loaded YOLOE model
        """
        if self.model is None:
            logger.info(f"Loading YOLOE model: {self.MODEL_NAME}")

            try:
                from ultralytics import YOLOE

                self.model = YOLOE(self.MODEL_NAME)
                self.device = "cpu" if force_cpu else "0"  # "0" = first GPU

                # Set text prompts
                text_pe = self.model.get_text_pe(self.prompts)
                self.model.set_classes(self.prompts, text_pe)

                self._initialized = True
                logger.info(f"YOLOE model loaded successfully with prompts: {self.prompts}")

            except ImportError as e:
                logger.error(f"Failed to import YOLOE: {e}")
                raise ImportError(
                    "YOLOE not available. Install with: pip install -U ultralytics>=8.3.0"
                )
            except Exception as e:
                logger.error(f"Failed to load YOLOE model: {e}")
                raise

        return self.model

    def detect_document(
        self,
        image: Image.Image,
        confidence_threshold: float = 0.3,
        force_cpu: bool = False
    ) -> Optional[dict]:
        """
        Detect document in image and return the largest detection.

        Args:
            image: PIL Image to analyze
            confidence_threshold: Minimum confidence (0-1) for detection
            force_cpu: Force CPU usage

        Returns:
            Detection dict with keys:
                - boundingBox: {x1, y1, x2, y2}
                - confidence: float (0-1)
                - className: str (e.g., "document", "paper")
            Or None if no document detected
        """
        model = self.load_model(force_cpu=force_cpu)

        # Apply EXIF rotation to fix orientation issues
        image = ImageOps.exif_transpose(image)

        # Run inference
        try:
            results = model.predict(image, device=self.device, verbose=False)
            result = results[0]
        except Exception as e:
            logger.error(f"YOLOE inference failed: {e}")
            return None

        # Check if any detections
        if result.boxes is None or len(result.boxes) == 0:
            logger.debug("No documents detected in image")
            return None

        # Get class names from model
        names = result.names if hasattr(result, 'names') else {
            i: p for i, p in enumerate(self.prompts)
        }

        # Find largest detection above threshold
        best_detection = None
        best_area = 0

        for box, conf, cls in zip(
            result.boxes.xyxy.cpu().numpy(),
            result.boxes.conf.cpu().numpy(),
            result.boxes.cls.cpu().numpy()
        ):
            # Skip low confidence
            if conf < confidence_threshold:
                continue

            x1, y1, x2, y2 = box
            area = (x2 - x1) * (y2 - y1)

            # Keep largest
            if area > best_area:
                best_area = area
                class_idx = int(cls)
                best_detection = {
                    'boundingBox': {
                        'x1': float(x1),
                        'y1': float(y1),
                        'x2': float(x2),
                        'y2': float(y2)
                    },
                    'confidence': float(conf),
                    'className': names.get(class_idx, f"class_{class_idx}")
                }

        if best_detection:
            logger.debug(
                f"Detected {best_detection['className']} "
                f"(conf: {best_detection['confidence']:.2%})"
            )

        return best_detection

    def crop_image(
        self,
        image: Image.Image,
        bbox: dict,
        padding: int = 10
    ) -> Image.Image:
        """
        Crop image to bounding box with padding.

        Args:
            image: PIL Image to crop
            bbox: Bounding box dict with x1, y1, x2, y2
            padding: Pixels to add around crop

        Returns:
            Cropped PIL Image
        """
        # Apply EXIF rotation first
        image = ImageOps.exif_transpose(image)

        w, h = image.size

        # Extract coordinates with padding
        x1 = max(0, int(bbox['x1']) - padding)
        y1 = max(0, int(bbox['y1']) - padding)
        x2 = min(w, int(bbox['x2']) + padding)
        y2 = min(h, int(bbox['y2']) + padding)

        return image.crop((x1, y1, x2, y2))

    def detect_and_crop(
        self,
        image: Image.Image,
        confidence_threshold: float = 0.3,
        padding: int = 10,
        force_cpu: bool = False
    ) -> Tuple[Optional[Image.Image], Optional[dict]]:
        """
        Detect document and crop in one call.

        Args:
            image: PIL Image to process
            confidence_threshold: Minimum confidence for detection
            padding: Pixels to add around crop
            force_cpu: Force CPU usage

        Returns:
            Tuple of (cropped_image, detection_info) or (None, None)
        """
        detection = self.detect_document(
            image,
            confidence_threshold=confidence_threshold,
            force_cpu=force_cpu
        )

        if detection is None:
            return None, None

        cropped = self.crop_image(image, detection['boundingBox'], padding=padding)

        return cropped, detection
