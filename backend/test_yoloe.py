#!/usr/bin/env python3
"""
Test script for YOLOE text-prompted detection/segmentation.

YOLOE supports TEXT PROMPTS like SAM3, allowing detection of any object by name.
No tokens required - models auto-download on first use.

Usage:
    python test_yoloe.py <input_image> [--prompt "document"] [--cpu]

Examples:
    python test_yoloe.py photo.jpg --prompt "document"
    python test_yoloe.py photo.jpg --prompt "document,paper,notebook" --cpu
    python test_yoloe.py photo.jpg --prompt "document" --output cropped.jpg

How multiple prompts work:
    - All prompts are processed in a SINGLE inference pass
    - Each detected object is assigned the BEST matching class from your prompts
    - You won't get duplicate detections - each object is labeled once
    - Example: "document,paper" might label some as "document" and others as "paper"
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def test_yoloe(input_path: str, prompt: str = "document", output_path: str = None,
               save_crop: bool = True, force_cpu: bool = False):
    """Test YOLOE segmentation with text prompts."""

    # Check input file exists
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    # Parse prompts (can be comma-separated)
    prompts = [p.strip() for p in prompt.split(",")]

    # Device selection
    device = "cpu" if force_cpu else "0"  # "0" = first GPU

    print(f"Input: {input_path}")
    print(f"Prompts: {prompts}")
    print(f"Device: {'CPU (forced)' if force_cpu else 'Auto (GPU if available)'}")
    print("-" * 60)

    # Try to import YOLOE
    try:
        from ultralytics import YOLOE
        print("✓ YOLOE imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import YOLOE: {e}")
        print("\nMake sure ultralytics>=8.3.0 is installed:")
        print("  pip install -U ultralytics")
        sys.exit(1)

    # Load model (will auto-download if not present)
    model_name = "yoloe-11l-seg.pt"  # L = Large model for better accuracy
    print(f"\nLoading model: {model_name}")
    print("  (Will auto-download on first use - no token required)")

    try:
        load_start = time.time()
        model = YOLOE(model_name)
        load_time = time.time() - load_start
        print(f"✓ Model loaded: {model_name} ({load_time:.2f}s)")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Set text prompts
    print(f"\nSetting text prompts: {prompts}")
    try:
        text_pe = model.get_text_pe(prompts)
        model.set_classes(prompts, text_pe)
        print(f"✓ Text prompts configured")
    except Exception as e:
        print(f"✗ Failed to set prompts: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Run inference
    print(f"\n{'='*60}")
    print("RUNNING INFERENCE...")
    print(f"{'='*60}")

    try:
        inference_start = time.time()
        results = model.predict(input_path, device=device, verbose=False)
        inference_time = time.time() - inference_start
        result = results[0]
        print(f"✓ Inference complete ({inference_time:.2f}s)")
    except Exception as e:
        print(f"✗ Inference failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Print raw result info
    print(f"\n{'='*60}")
    print("RAW RESULT OBJECT:")
    print(f"{'='*60}")
    print(f"  Type: {type(result)}")
    print(f"  Image shape: {result.orig_shape}")

    # Print boxes info
    print(f"\n{'='*60}")
    print("DETECTED OBJECTS:")
    print(f"{'='*60}")

    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes
        print(f"  Number of detections: {len(boxes)}")

        # Get class names from model
        names = result.names if hasattr(result, 'names') else {i: p for i, p in enumerate(prompts)}

        print(f"\n  DETAILED DETECTIONS:")
        print(f"  {'-'*56}")

        best_detection = None
        best_area = 0

        for i, (box, conf, cls) in enumerate(zip(
            boxes.xyxy.cpu().numpy(),
            boxes.conf.cpu().numpy(),
            boxes.cls.cpu().numpy()
        )):
            class_idx = int(cls)
            class_name = names.get(class_idx, f"class_{class_idx}")
            x1, y1, x2, y2 = box
            width = x2 - x1
            height = y2 - y1
            area = width * height

            print(f"\n  Detection {i + 1}:")
            print(f"    Class: {class_name} (id: {class_idx})")
            print(f"    Confidence: {conf:.2%}")
            print(f"    Bounding box: ({x1:.0f}, {y1:.0f}) to ({x2:.0f}, {y2:.0f})")
            print(f"    Size: {width:.0f}x{height:.0f} pixels (area: {area:.0f})")

            # Track best (largest) detection
            if area > best_area:
                best_area = area
                best_detection = {
                    'box': box,
                    'conf': conf,
                    'class': class_name,
                    'index': i
                }

        # Show masks info if available
        if result.masks is not None:
            print(f"\n  SEGMENTATION MASKS:")
            print(f"  {'-'*56}")
            print(f"  Number of masks: {len(result.masks)}")
            print(f"  Mask data shape: {result.masks.data.shape}")

        # Crop to best detection if requested
        if save_crop and best_detection is not None:
            print(f"\n{'='*60}")
            print("CROPPING TO BEST DETECTION:")
            print(f"{'='*60}")

            x1, y1, x2, y2 = best_detection['box']

            # Add padding
            padding = 10
            img = Image.open(input_path)
            # Apply EXIF rotation to fix orientation issues
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            x1 = max(0, int(x1) - padding)
            y1 = max(0, int(y1) - padding)
            x2 = min(w, int(x2) + padding)
            y2 = min(h, int(y2) + padding)

            cropped = img.crop((x1, y1, x2, y2))

            # Determine output path
            if output_path is None:
                output_path = input_file.stem + "_cropped" + input_file.suffix

            cropped.save(output_path, quality=95)
            print(f"  Best detection: {best_detection['class']} ({best_detection['conf']:.2%})")
            print(f"  Cropped region: ({x1}, {y1}) to ({x2}, {y2})")
            print(f"  Original size: {w}x{h}")
            print(f"  Cropped size: {x2-x1}x{y2-y1}")
            print(f"✓ Saved cropped image to: {output_path}")

        # Also save annotated image
        annotated_path = input_file.stem + "_annotated" + input_file.suffix
        annotated = result.plot()
        annotated_rgb = annotated[:, :, ::-1]  # BGR to RGB
        Image.fromarray(annotated_rgb).save(annotated_path)
        print(f"✓ Saved annotated image to: {annotated_path}")

    else:
        print(f"  No '{prompt}' detected in the image!")
        print(f"\n  Try different prompts like:")
        print(f"    - document")
        print(f"    - paper")
        print(f"    - notebook")
        print(f"    - sheet")
        print(f"    - form")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    if result.boxes is not None and len(result.boxes) > 0:
        print(f"  ✓ Detected {len(result.boxes)} object(s) matching prompts: {prompts}")
        print(f"  ✓ YOLOE works with text prompts - no predefined classes!")

        # Show class distribution if multiple prompts
        if len(prompts) > 1:
            names = result.names if hasattr(result, 'names') else {i: p for i, p in enumerate(prompts)}
            class_counts = {}
            for cls in result.boxes.cls.cpu().numpy():
                class_name = names.get(int(cls), f"class_{int(cls)}")
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
            print(f"\n  Class distribution:")
            for class_name, count in sorted(class_counts.items(), key=lambda x: -x[1]):
                print(f"    - {class_name}: {count} detection(s)")
    else:
        print(f"  ✗ No objects detected for prompts: {prompts}")

    # Timing summary
    total_time = load_time + inference_time
    print(f"\n{'='*60}")
    print("TIMING SUMMARY:")
    print(f"{'='*60}")
    print(f"  Model load:  {load_time:.2f}s")
    print(f"  Inference:   {inference_time:.2f}s")
    print(f"  Total:       {total_time:.2f}s")

    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Test YOLOE text-prompted segmentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("--prompt", "-p", default="document",
                        help="Text prompt(s) for detection, comma-separated (default: 'document')")
    parser.add_argument("--output", "-o", default=None,
                        help="Save cropped image to this path")
    parser.add_argument("--no-crop", action="store_true",
                        help="Don't save cropped image")
    parser.add_argument("--cpu", action="store_true",
                        help="Force CPU usage (no GPU)")

    args = parser.parse_args()
    test_yoloe(args.input, args.prompt, args.output,
               save_crop=not args.no_crop, force_cpu=args.cpu)


if __name__ == "__main__":
    main()
