"""
Image labeling service for preprocessing pipeline.

Handles:
- Creating rotation variants (0°, 90°, 180°, 270°)
- Adding text labels to images
- Resizing images to max size
"""

import io
import logging
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger(__name__)


class ImageLabelingService:
    """
    Service for creating labeled image variants for AI preprocessing.
    """

    # Label styling
    FONT_SIZE_RATIO = 0.05  # 5% of image height
    MIN_FONT_SIZE = 16
    MAX_FONT_SIZE = 48
    LABEL_BG_COLOR = (255, 255, 255)  # White
    LABEL_TEXT_COLOR = (0, 0, 0)  # Black
    LABEL_PADDING = 10

    # Common font paths to try
    FONT_PATHS = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "C:/Windows/Fonts/arial.ttf",  # Windows
    ]

    def __init__(self):
        self._font_cache: Dict[int, ImageFont.FreeTypeFont] = {}

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font of specified size, with caching."""
        if size in self._font_cache:
            return self._font_cache[size]

        font = None
        for path in self.FONT_PATHS:
            try:
                font = ImageFont.truetype(path, size)
                break
            except (OSError, IOError):
                continue

        if font is None:
            logger.warning("No TrueType fonts found, using default font")
            font = ImageFont.load_default()

        self._font_cache[size] = font
        return font

    def _calculate_font_size(self, image_height: int) -> int:
        """Calculate appropriate font size based on image height."""
        size = int(image_height * self.FONT_SIZE_RATIO)
        return max(self.MIN_FONT_SIZE, min(size, self.MAX_FONT_SIZE))

    def add_label(self, image: Image.Image, label: str) -> Image.Image:
        """
        Add text label to TOP of image.

        Creates a white bar at top with centered black text.

        Args:
            image: PIL Image to label
            label: Text label to add

        Returns:
            New image with label bar added
        """
        width, height = image.size

        # Calculate font size and label height
        font_size = self._calculate_font_size(height)
        label_height = font_size + self.LABEL_PADDING * 2

        # Create new image with space for label
        new_height = height + label_height
        new_image = Image.new('RGB', (width, new_height), self.LABEL_BG_COLOR)

        # Draw label text
        draw = ImageDraw.Draw(new_image)
        font = self._get_font(font_size)

        # Get text bounding box for centering
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = (width - text_width) // 2
        text_y = self.LABEL_PADDING

        draw.text((text_x, text_y), label, fill=self.LABEL_TEXT_COLOR, font=font)

        # Paste original image below label
        new_image.paste(image, (0, label_height))

        return new_image

    def create_rotations(self, image: Image.Image) -> Dict[int, Image.Image]:
        """
        Create all 4 rotation variants.

        Args:
            image: PIL Image to rotate

        Returns:
            Dict mapping rotation angle to rotated image:
            {0: original, 90: rotated_90, 180: rotated_180, 270: rotated_270}
        """
        return {
            0: image.copy(),
            90: image.rotate(-90, expand=True),  # Negative = clockwise
            180: image.rotate(180, expand=True),
            270: image.rotate(-270, expand=True),  # Same as rotate(90)
        }

    def resize_if_needed(
        self,
        image: Image.Image,
        max_size: int = 1080
    ) -> Image.Image:
        """
        Resize image to max dimension if larger, preserving aspect ratio.

        Args:
            image: PIL Image to resize
            max_size: Maximum width or height (default: 1080)

        Returns:
            Resized image (or original if already small enough)
        """
        width, height = image.size

        # No resize needed
        if width <= max_size and height <= max_size:
            return image

        # Calculate new dimensions
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))

        logger.debug(f"Resizing image from {width}x{height} to {new_width}x{new_height}")

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def prepare_image(self, image: Image.Image, max_size: int = 1080) -> Image.Image:
        """
        Prepare image for processing: EXIF transpose and resize.

        Args:
            image: PIL Image to prepare
            max_size: Maximum width or height

        Returns:
            Prepared image (EXIF corrected, resized if needed)
        """
        # Apply EXIF rotation to fix orientation
        image = ImageOps.exif_transpose(image)

        # Resize if too large
        image = self.resize_if_needed(image, max_size)

        # Ensure RGB mode (no alpha channel)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        return image

    def create_labeled_variants(
        self,
        image: Image.Image,
        image_index: int,
        max_size: int = 1080
    ) -> List[Tuple[Image.Image, dict]]:
        """
        Create all labeled rotation variants for an image.

        Args:
            image: PIL Image to process
            image_index: 1-based index for labeling
            max_size: Maximum dimension for resize

        Returns:
            List of (labeled_image, metadata) tuples where metadata is:
            {
                "imageIndex": int,
                "label": str,
                "type": "rotation",
                "rotation": int
            }
        """
        # Prepare image (EXIF + resize)
        image = self.prepare_image(image, max_size)

        # Create rotations
        rotations = self.create_rotations(image)

        # Add labels to each rotation
        variants = []
        for rotation, rotated_img in rotations.items():
            label = f"{image_index}: {rotation}°"
            labeled = self.add_label(rotated_img, label)

            metadata = {
                "imageIndex": image_index,
                "label": label,
                "type": "rotation",
                "rotation": rotation
            }

            variants.append((labeled, metadata))

        return variants

    def create_crop_comparison(
        self,
        original_image: Image.Image,
        cropped_image: Image.Image,
        image_index: int,
        max_size: int = 1080
    ) -> Tuple[Image.Image, dict]:
        """
        Create side-by-side comparison of original vs cropped for AI decision.

        Left side: Original (Crop=False)
        Right side: Cropped (Crop=True)

        Args:
            original_image: Original PIL Image (already prepared)
            cropped_image: Cropped PIL Image
            image_index: 1-based index for labeling
            max_size: Maximum dimension for each side

        Returns:
            (comparison_image, metadata) tuple
        """
        # Resize both to fit in comparison
        half_max = max_size // 2
        original_resized = self.resize_if_needed(original_image.copy(), half_max)
        cropped_resized = self.resize_if_needed(cropped_image, half_max)

        # Ensure RGB
        if original_resized.mode != 'RGB':
            original_resized = original_resized.convert('RGB')
        if cropped_resized.mode != 'RGB':
            cropped_resized = cropped_resized.convert('RGB')

        # Make both same height for clean side-by-side
        max_height = max(original_resized.height, cropped_resized.height)

        # Create canvas for side-by-side
        gap = 10  # Gap between images
        total_width = original_resized.width + cropped_resized.width + gap

        # Add space for labels at top
        font_size = self._calculate_font_size(max_height)
        label_height = font_size + self.LABEL_PADDING * 2

        canvas = Image.new('RGB', (total_width, max_height + label_height), (255, 255, 255))

        # Draw labels
        draw = ImageDraw.Draw(canvas)
        font = self._get_font(font_size)

        # Left label: "N: Crop=False"
        left_label = f"{image_index}: Crop=False"
        left_bbox = draw.textbbox((0, 0), left_label, font=font)
        left_text_x = (original_resized.width - (left_bbox[2] - left_bbox[0])) // 2
        draw.text((left_text_x, self.LABEL_PADDING), left_label, fill=self.LABEL_TEXT_COLOR, font=font)

        # Right label: "N: Crop=True"
        right_label = f"{image_index}: Crop=True"
        right_bbox = draw.textbbox((0, 0), right_label, font=font)
        right_text_x = original_resized.width + gap + (cropped_resized.width - (right_bbox[2] - right_bbox[0])) // 2
        draw.text((right_text_x, self.LABEL_PADDING), right_label, fill=self.LABEL_TEXT_COLOR, font=font)

        # Paste images below labels
        y_offset = label_height
        canvas.paste(original_resized, (0, y_offset))
        canvas.paste(cropped_resized, (original_resized.width + gap, y_offset))

        metadata = {
            "imageIndex": image_index,
            "label": f"{image_index}: crop comparison",
            "type": "crop_comparison"
        }

        return canvas, metadata

    def create_cropped_variant(
        self,
        cropped_image: Image.Image,
        image_index: int,
        max_size: int = 1080
    ) -> Tuple[Image.Image, dict]:
        """
        Create labeled cropped variant.

        Args:
            cropped_image: Already cropped PIL Image
            image_index: 1-based index for labeling
            max_size: Maximum dimension for resize

        Returns:
            (labeled_image, metadata) tuple
        """
        # Resize if needed
        cropped_image = self.resize_if_needed(cropped_image, max_size)

        # Ensure RGB
        if cropped_image.mode != 'RGB':
            cropped_image = cropped_image.convert('RGB')

        # Add label
        label = f"{image_index}: cropped"
        labeled = self.add_label(cropped_image, label)

        metadata = {
            "imageIndex": image_index,
            "label": label,
            "type": "crop"
        }

        return labeled, metadata


def image_to_base64(image: Image.Image, format: str = 'JPEG', quality: int = 90) -> str:
    """
    Convert PIL Image to base64 string.

    Args:
        image: PIL Image
        format: Image format (JPEG, PNG, etc.)
        quality: JPEG quality (1-100)

    Returns:
        Base64 encoded string
    """
    import base64

    buffer = io.BytesIO()

    # Ensure RGB for JPEG
    if format.upper() == 'JPEG' and image.mode != 'RGB':
        image = image.convert('RGB')

    image.save(buffer, format=format, quality=quality)
    buffer.seek(0)

    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def base64_to_image(base64_str: str) -> Image.Image:
    """
    Convert base64 string to PIL Image.

    Args:
        base64_str: Base64 encoded image

    Returns:
        PIL Image
    """
    import base64

    # Handle data URL prefix if present
    if ',' in base64_str:
        base64_str = base64_str.split(',')[1]

    image_data = base64.b64decode(base64_str)
    return Image.open(io.BytesIO(image_data))
