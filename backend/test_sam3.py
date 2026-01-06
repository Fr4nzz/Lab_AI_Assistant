#!/usr/bin/env python3
"""
Test script for SAM3 document segmentation.

Usage:
    python test_sam3.py <input_image> [--prompt "document"] [--output output.jpg]

Examples:
    python test_sam3.py photo.jpg
    python test_sam3.py photo.jpg --prompt "notebook"
    python test_sam3.py photo.jpg --prompt "document" --output cropped.jpg

Environment:
    HF_TOKEN: Hugging Face token for downloading SAM3 model (in .env file)
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv(Path(__file__).parent.parent / ".env")


def download_sam3_model(target_path: Path) -> bool:
    """Download SAM3 model from Hugging Face."""
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")

    if not hf_token:
        print("✗ No Hugging Face token found!")
        print("\nTo enable auto-download, add to your .env file:")
        print("  HF_TOKEN=hf_your_token_here")
        print("\nGet your token at: https://huggingface.co/settings/tokens")
        return False

    try:
        from huggingface_hub import hf_hub_download
        print("✓ huggingface_hub available")
    except ImportError:
        print("✗ huggingface_hub not installed")
        print("\nInstall it with:")
        print("  pip install huggingface_hub")
        return False

    print(f"\nDownloading SAM3 model from Hugging Face...")
    print("  Repository: facebook/sam3")
    print("  This may take a few minutes...")

    try:
        # Create target directory if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Download the model
        downloaded_path = hf_hub_download(
            repo_id="facebook/sam3",
            filename="sam3.pt",
            token=hf_token,
            local_dir=target_path.parent,
            local_dir_use_symlinks=False
        )

        print(f"✓ Model downloaded to: {downloaded_path}")
        return True

    except Exception as e:
        print(f"✗ Download failed: {e}")
        print("\nMake sure you have:")
        print("  1. Accepted the license at: https://huggingface.co/facebook/sam3")
        print("  2. A valid HF_TOKEN in your .env file")
        return False


def get_model_path() -> Path:
    """Find or download SAM3 model weights."""
    # Check for model weights in order of preference
    model_paths = [
        Path(__file__).parent / "models" / "sam3.pt",
        Path("sam3.pt"),
        Path.home() / ".ultralytics" / "sam3.pt",
    ]

    for path in model_paths:
        if path.exists():
            return path

    # Model not found, try to download
    print("SAM3 model not found locally.")
    print("\nSearched in:")
    for path in model_paths:
        print(f"  - {path}")

    # Try to download to the first location (backend/models/)
    target_path = model_paths[0]
    print(f"\nAttempting to download to: {target_path}")

    if download_sam3_model(target_path):
        return target_path

    return None


def test_sam3(input_path: str, prompt: str = "document", output_path: str = None):
    """Test SAM3 segmentation with a text prompt."""

    # Check input file exists
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    # Default output path
    if output_path is None:
        output_path = input_file.stem + "_cropped" + input_file.suffix

    print(f"Input: {input_path}")
    print(f"Prompt: '{prompt}'")
    print(f"Output: {output_path}")
    print("-" * 50)

    # Try to import SAM3
    try:
        from ultralytics.models.sam import SAM3SemanticPredictor
        print("✓ SAM3SemanticPredictor imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import SAM3: {e}")
        print("\nMake sure ultralytics>=8.3.237 is installed:")
        print("  pip install -U ultralytics")
        sys.exit(1)

    # Get model path (downloads if needed)
    model_path = get_model_path()

    if model_path is None:
        print("\n✗ Could not find or download SAM3 model")
        print("\nManual download:")
        print("  1. Request access at: https://huggingface.co/facebook/sam3")
        print("  2. Download sam3.pt")
        print("  3. Place it in: backend/models/sam3.pt")
        sys.exit(1)

    print(f"✓ Model found: {model_path}")

    # Load image
    print("\nLoading image...")
    image = Image.open(input_path)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    image_np = np.array(image)
    print(f"✓ Image loaded: {image.size[0]}x{image.size[1]}")

    # Initialize predictor
    print("\nInitializing SAM3 predictor...")
    try:
        overrides = dict(
            conf=0.25,
            task="segment",
            mode="predict",
            model=str(model_path),
            half=True,
        )
        predictor = SAM3SemanticPredictor(overrides=overrides)
        print("✓ Predictor initialized")
    except Exception as e:
        print(f"✗ Failed to initialize predictor: {e}")
        sys.exit(1)

    # Set image and run segmentation
    print(f"\nRunning segmentation with prompt: '{prompt}'...")
    try:
        predictor.set_image(image_np)
        results = predictor(text=[prompt])
        print(f"✓ Segmentation complete")
    except Exception as e:
        print(f"✗ Segmentation failed: {e}")
        sys.exit(1)

    # Process results
    if not results or len(results) == 0:
        print(f"\n⚠ No '{prompt}' detected in the image")
        sys.exit(0)

    result = results[0]

    # Check for bounding boxes
    if result.boxes is None or len(result.boxes) == 0:
        print(f"\n⚠ No bounding boxes found for '{prompt}'")
        sys.exit(0)

    # Get the largest bounding box
    boxes = result.boxes.xyxy.cpu().numpy()
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    best_idx = np.argmax(areas)
    x1, y1, x2, y2 = boxes[best_idx].astype(int)

    print(f"\n✓ Found {len(boxes)} '{prompt}' region(s)")
    print(f"  Best match bounding box: ({x1}, {y1}) to ({x2}, {y2})")
    print(f"  Size: {x2-x1}x{y2-y1} pixels")

    # Add padding
    padding = 10
    h, w = image_np.shape[:2]
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)

    # Crop image
    cropped = image.crop((x1, y1, x2, y2))

    # Save cropped image
    cropped.save(output_path, quality=95)
    print(f"\n✓ Cropped image saved to: {output_path}")
    print(f"  Original size: {image.size[0]}x{image.size[1]}")
    print(f"  Cropped size: {cropped.size[0]}x{cropped.size[1]}")

    # Also show masks info if available
    if result.masks is not None:
        print(f"\n  Masks available: {len(result.masks)} mask(s)")

    print("\n" + "=" * 50)
    print("SAM3 test completed successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Test SAM3 document segmentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("--prompt", "-p", default="document",
                        help="Text prompt for segmentation (default: 'document')")
    parser.add_argument("--output", "-o", default=None,
                        help="Path to output cropped image")

    args = parser.parse_args()
    test_sam3(args.input, args.prompt, args.output)


if __name__ == "__main__":
    main()
