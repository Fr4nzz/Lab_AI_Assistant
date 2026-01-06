#!/usr/bin/env python3
"""
Test script for YOLO-World automatic object detection.

YOLO-World detects 80 COCO classes automatically WITHOUT requiring text prompts.
Use this to see what objects are detected in your image.

Usage:
    python test_yolo_world.py <input_image> [--output output.jpg]

Examples:
    python test_yolo_world.py photo.jpg
    python test_yolo_world.py photo.jpg --output annotated.jpg

This will show all detected objects with their class names and confidence scores.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def test_yolo_world(input_path: str, output_path: str = None):
    """Test YOLO-World detection on an image (no prompts required)."""

    # Check input file exists
    input_file = Path(input_path)
    if not input_file.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print(f"Input: {input_path}")
    print(f"Mode: Automatic detection (no prompts)")
    print("-" * 60)

    # Try to import YOLOWorld
    try:
        from ultralytics import YOLOWorld
        print("✓ YOLOWorld imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import YOLOWorld: {e}")
        print("\nMake sure ultralytics>=8.1.0 is installed:")
        print("  pip install -U ultralytics")
        sys.exit(1)

    # Load model (will auto-download if not present)
    model_name = "yolov8l-world.pt"  # Large model for better accuracy
    print(f"\nLoading model: {model_name}")
    print("  (Will auto-download on first use)")

    try:
        model = YOLOWorld(model_name)
        print(f"✓ Model loaded: {model_name}")
    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Show available classes
    print(f"\n{'='*60}")
    print("DEFAULT COCO CLASSES (auto-detected):")
    print(f"{'='*60}")
    if hasattr(model, 'names') and model.names:
        for idx, name in model.names.items():
            print(f"  {idx:2d}: {name}")
    else:
        print("  (Classes will be shown in results)")

    # Run inference
    print(f"\n{'='*60}")
    print("RUNNING INFERENCE...")
    print(f"{'='*60}")

    try:
        results = model.predict(input_path, verbose=False)
        result = results[0]
        print("✓ Inference complete")
    except Exception as e:
        print(f"✗ Inference failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Get class names
    names = result.names if hasattr(result, 'names') else {}

    # Print detected objects
    print(f"\n{'='*60}")
    print("DETECTED OBJECTS:")
    print(f"{'='*60}")

    if result.boxes is not None and len(result.boxes) > 0:
        boxes = result.boxes
        print(f"  Total detections: {len(boxes)}")

        # Group by class
        detections_by_class = {}
        for i, (box, conf, cls) in enumerate(zip(
            boxes.xyxy.cpu().numpy(),
            boxes.conf.cpu().numpy(),
            boxes.cls.cpu().numpy()
        )):
            class_idx = int(cls)
            class_name = names.get(class_idx, f"class_{class_idx}")

            if class_name not in detections_by_class:
                detections_by_class[class_name] = []

            x1, y1, x2, y2 = box
            detections_by_class[class_name].append({
                'conf': conf,
                'box': (x1, y1, x2, y2),
                'size': (x2 - x1) * (y2 - y1)
            })

        # Print grouped by class
        print(f"\n  DETECTIONS BY CLASS:")
        print(f"  {'-'*56}")

        for class_name, detections in sorted(detections_by_class.items(),
                                              key=lambda x: -max(d['conf'] for d in x[1])):
            best_conf = max(d['conf'] for d in detections)
            total_area = sum(d['size'] for d in detections)
            print(f"\n  {class_name}:")
            print(f"    Count: {len(detections)}")
            print(f"    Best confidence: {best_conf:.2%}")
            print(f"    Total area: {total_area:.0f} pixels")

            for j, det in enumerate(sorted(detections, key=lambda x: -x['conf'])):
                x1, y1, x2, y2 = det['box']
                print(f"    [{j+1}] conf={det['conf']:.2%}, box=({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})")

        # Summary of potentially useful classes for documents
        print(f"\n{'='*60}")
        print("DOCUMENT-RELATED DETECTIONS:")
        print(f"{'='*60}")

        doc_related = ['book', 'laptop', 'cell phone', 'tv', 'keyboard', 'mouse',
                      'paper', 'document', 'notebook', 'card']
        found_doc_related = []

        for class_name in detections_by_class:
            if any(doc in class_name.lower() for doc in doc_related):
                found_doc_related.append(class_name)

        if found_doc_related:
            print(f"  Found: {', '.join(found_doc_related)}")
        else:
            print("  None of the standard document-related classes detected.")
            print("  Note: YOLO-World uses COCO classes which don't include 'document' or 'paper'")
            print("  For document detection, use YOLOE with text prompt 'document'")

    else:
        print("  No objects detected!")

    # Save annotated image
    if output_path is None:
        output_path = input_file.stem + "_world_annotated" + input_file.suffix

    annotated = result.plot()
    annotated_rgb = annotated[:, :, ::-1]  # BGR to RGB
    Image.fromarray(annotated_rgb).save(output_path)
    print(f"\n✓ Saved annotated image to: {output_path}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    if result.boxes is not None and len(result.boxes) > 0:
        unique_classes = set(names.get(int(c), f"class_{int(c)}")
                            for c in result.boxes.cls.cpu().numpy())
        print(f"  Detected {len(result.boxes)} object(s) across {len(unique_classes)} classes")
        print(f"  Classes: {', '.join(sorted(unique_classes))}")
    else:
        print("  No objects detected")

    print(f"\n{'='*60}")
    print("COMPARISON:")
    print(f"{'='*60}")
    print("  YOLO-World: Detects 80 COCO classes automatically (no 'document' class)")
    print("  YOLOE:      Detects ANY object via text prompts (can detect 'document')")
    print("\n  For document detection, run:")
    print("    python test_yoloe.py photo.jpg --prompt \"document\"")

    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Test YOLO-World automatic detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("input", help="Path to input image")
    parser.add_argument("--output", "-o", default=None,
                        help="Save annotated image to this path")

    args = parser.parse_args()
    test_yolo_world(args.input, args.output)


if __name__ == "__main__":
    main()
