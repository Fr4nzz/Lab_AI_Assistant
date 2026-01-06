#!/usr/bin/env python3
"""
Test script for YOLO12 object detection and segmentation.

YOLO12 uses predefined COCO classes (80 categories), NOT text prompts.
This script helps explore what objects YOLO12 can detect in your images.

Usage:
    python test_yolo12.py <input_image> [--seg] [--output output.jpg]

Examples:
    python test_yolo12.py photo.jpg                    # Detection only
    python test_yolo12.py photo.jpg --seg              # With segmentation
    python test_yolo12.py photo.jpg --seg --output out.jpg  # Save annotated image

COCO classes that might be useful for documents:
    - book (id: 73)
    - cell phone (id: 67)
    - laptop (id: 63)
    - keyboard (id: 66)
    - mouse (id: 64)
    - remote (id: 65)
    - tv (id: 62)
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image


# COCO class names (80 classes)
COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
    'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
    'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
    'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]


def test_yolo12(input_path: str, use_seg: bool = False, output_path: str = None):
    """Test YOLO12 detection/segmentation on an image."""

    # Check input file exists
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"Input: {input_path}")
    print(f"Mode: {'Segmentation' if use_seg else 'Detection'}")
    print("-" * 60)

    # Try to import ultralytics
    try:
        from ultralytics import YOLO
        print("✓ ultralytics imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import ultralytics: {e}")
        print("\nInstall with: pip install ultralytics")
        sys.exit(1)

    # Load model (will auto-download if not present)
    model_name = "yolo12n-seg.pt" if use_seg else "yolo12n.pt"
    print(f"\nLoading model: {model_name}")
    print("  (Will auto-download on first use)")

    try:
        model = YOLO(model_name)
        print(f"✓ Model loaded: {model_name}")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        sys.exit(1)

    # Print available class names
    print(f"\n{'='*60}")
    print("COCO CLASSES (what YOLO12 can detect):")
    print(f"{'='*60}")
    for i, name in enumerate(COCO_CLASSES):
        print(f"  {i:2d}: {name}")

    # Highlight document-related classes
    print(f"\n{'='*60}")
    print("POTENTIALLY USEFUL FOR DOCUMENTS:")
    print(f"{'='*60}")
    doc_related = ['book', 'laptop', 'tv', 'cell phone', 'keyboard', 'mouse', 'remote']
    for name in doc_related:
        if name in COCO_CLASSES:
            idx = COCO_CLASSES.index(name)
            print(f"  {idx:2d}: {name}")

    # Run inference
    print(f"\n{'='*60}")
    print("RUNNING INFERENCE...")
    print(f"{'='*60}")

    try:
        results = model(input_path, verbose=False)
        result = results[0]
        print("✓ Inference complete")
    except Exception as e:
        print(f"✗ Inference failed: {e}")
        sys.exit(1)

    # Print raw result info
    print(f"\n{'='*60}")
    print("RAW RESULT OBJECT:")
    print(f"{'='*60}")
    print(f"  Type: {type(result)}")
    print(f"  Attributes: {[a for a in dir(result) if not a.startswith('_')]}")

    # Print boxes info
    print(f"\n{'='*60}")
    print("DETECTED OBJECTS (boxes):")
    print(f"{'='*60}")

    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes
        print(f"  Number of detections: {len(boxes)}")
        print(f"  Boxes shape (xyxy): {boxes.xyxy.shape}")
        print(f"  Confidence scores: {boxes.conf.cpu().numpy()}")
        print(f"  Class indices: {boxes.cls.cpu().numpy()}")

        print(f"\n  DETAILED DETECTIONS:")
        print(f"  {'-'*56}")

        for i, (box, conf, cls) in enumerate(zip(
            boxes.xyxy.cpu().numpy(),
            boxes.conf.cpu().numpy(),
            boxes.cls.cpu().numpy()
        )):
            class_name = COCO_CLASSES[int(cls)]
            x1, y1, x2, y2 = box
            width = x2 - x1
            height = y2 - y1
            area = width * height

            print(f"\n  Detection {i + 1}:")
            print(f"    Class: {class_name} (id: {int(cls)})")
            print(f"    Confidence: {conf:.2%}")
            print(f"    Bounding box: ({x1:.0f}, {y1:.0f}) to ({x2:.0f}, {y2:.0f})")
            print(f"    Size: {width:.0f}x{height:.0f} pixels (area: {area:.0f})")
    else:
        print("  No objects detected!")

    # Print masks info (if segmentation)
    if use_seg:
        print(f"\n{'='*60}")
        print("SEGMENTATION MASKS:")
        print(f"{'='*60}")

        if result.masks is not None:
            masks = result.masks
            print(f"  Number of masks: {len(masks)}")
            print(f"  Mask data shape: {masks.data.shape}")
            print(f"  Original image shape: {masks.orig_shape}")

            # Show mask info for each detection
            for i, mask in enumerate(masks.data.cpu().numpy()):
                mask_area = np.sum(mask > 0.5)
                print(f"  Mask {i + 1}: {mask_area} pixels")
        else:
            print("  No masks available")

    # Save annotated image if requested
    if output_path:
        print(f"\n{'='*60}")
        print("SAVING ANNOTATED IMAGE:")
        print(f"{'='*60}")

        # Get annotated image
        annotated = result.plot()

        # Convert BGR to RGB and save
        annotated_rgb = annotated[:, :, ::-1]
        Image.fromarray(annotated_rgb).save(output_path)
        print(f"✓ Saved to: {output_path}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    if result.boxes is not None and len(result.boxes) > 0:
        detected_classes = set()
        for cls in result.boxes.cls.cpu().numpy():
            detected_classes.add(COCO_CLASSES[int(cls)])
        print(f"  Detected {len(result.boxes)} object(s)")
        print(f"  Classes found: {', '.join(sorted(detected_classes))}")

        # Check for document-related objects
        doc_found = detected_classes.intersection(set(doc_related))
        if doc_found:
            print(f"  Document-related: {', '.join(doc_found)}")
        else:
            print(f"  No document-related objects (book, laptop, etc.) detected")
            print(f"\n  NOTE: YOLO12 cannot detect 'document' or 'paper' directly!")
            print(f"        It only knows the 80 COCO classes listed above.")
            print(f"        For document detection, SAM3 with text prompts is better.")
    else:
        print("  No objects detected in image")

    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Test YOLO12 detection/segmentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("--seg", "-s", action="store_true",
                        help="Use segmentation model (yolo12n-seg.pt)")
    parser.add_argument("--output", "-o", default=None,
                        help="Save annotated image to this path")

    args = parser.parse_args()
    test_yolo12(args.input, args.seg, args.output)


if __name__ == "__main__":
    main()
