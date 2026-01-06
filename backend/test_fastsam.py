#!/usr/bin/env python3
"""
Test script for FastSAM (Fast Segment Anything Model) - Small variant
FastSAM is much faster than SAM2, uses YOLOv8-seg under the hood.

Usage:
    python test_fastsam.py <image_path>           # Auto-detect device
    python test_fastsam.py <image_path> --cpu     # Force CPU usage
    python test_fastsam.py pedidotest.jpg --cpu
"""

import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_fastsam(input_path: str, force_cpu: bool = False):
    """Test FastSAM automatic mask generation."""

    print("=" * 60)
    print("FastSAM-s - Fast Segment Anything Model Test")
    print("=" * 60)

    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return

    print(f"\n Input image: {input_path}")

    device = "cpu" if force_cpu else "0"  # "0" = first GPU, "cpu" = CPU
    print(f" Device: {'CPU (forced)' if force_cpu else 'Auto-detect (GPU if available)'}")

    try:
        from ultralytics import FastSAM
        from PIL import Image, ImageOps
        import numpy as np

        # Load image and fix rotation
        img = Image.open(input_path)
        img = ImageOps.exif_transpose(img)
        print(f" Image size: {img.size[0]}x{img.size[1]}")

        # Load FastSAM-s model
        model_name = "FastSAM-s.pt"
        print(f"\n Loading model: {model_name}")

        load_start = time.time()
        model = FastSAM(model_name)
        load_time = time.time() - load_start
        print(f" Model loaded ({load_time:.2f}s)")

        # Run inference - segment everything
        print("\n Running automatic segmentation...")
        inference_start = time.time()

        results = model(
            input_path,
            device=device,
            retina_masks=True,
            imgsz=1024,
            conf=0.4,
            iou=0.9,
            verbose=False
        )
        inference_time = time.time() - inference_start
        print(f" Inference time: {inference_time:.2f}s")

        if results and len(results) > 0:
            result = results[0]

            if result.masks is not None:
                num_masks = len(result.masks)
                print(f"\n Found {num_masks} segments/masks")

                masks = result.masks

                print("\n Segment Details:")
                print("-" * 40)

                # Sort masks by area (largest first)
                mask_areas = []
                for i, mask in enumerate(masks.data):
                    mask_np = mask.cpu().numpy()
                    area = mask_np.sum()
                    total_pixels = mask_np.size
                    percentage = (area / total_pixels) * 100
                    mask_areas.append((i, area, percentage))

                mask_areas.sort(key=lambda x: x[1], reverse=True)

                for idx, (i, area, percentage) in enumerate(mask_areas[:15]):
                    print(f"  Segment {idx+1}: {area:,} pixels ({percentage:.1f}% of image)")

                if len(mask_areas) > 15:
                    print(f"  ... and {len(mask_areas) - 15} more segments")

                # Save annotated image
                output_path = input_path.rsplit('.', 1)[0] + '_fastsam_segments.jpg'
                annotated = result.plot()

                if len(annotated.shape) == 3 and annotated.shape[2] == 3:
                    annotated_rgb = annotated[:, :, ::-1]
                else:
                    annotated_rgb = annotated

                output_img = Image.fromarray(annotated_rgb)
                output_img.save(output_path, quality=95)
                print(f"\n Saved annotated image: {output_path}")

                # Create colored overlay
                img_array = np.array(img.convert('RGB'))
                overlay = img_array.copy().astype(np.float32)

                colors = [
                    [255, 0, 0], [0, 255, 0], [0, 0, 255],
                    [255, 255, 0], [255, 0, 255], [0, 255, 255],
                    [255, 128, 0], [128, 0, 255], [0, 255, 128],
                    [255, 0, 128], [128, 255, 0], [0, 128, 255],
                ]

                for i, mask in enumerate(masks.data):
                    mask_np = mask.cpu().numpy()

                    if mask_np.shape != (img.size[1], img.size[0]):
                        mask_pil = Image.fromarray((mask_np * 255).astype(np.uint8))
                        mask_pil = mask_pil.resize((img.size[0], img.size[1]), Image.NEAREST)
                        mask_np = np.array(mask_pil) > 127

                    color = colors[i % len(colors)]
                    for c in range(3):
                        overlay[:, :, c] = np.where(
                            mask_np,
                            overlay[:, :, c] * 0.5 + color[c] * 0.5,
                            overlay[:, :, c]
                        )

                overlay_path = input_path.rsplit('.', 1)[0] + '_fastsam_colored.jpg'
                overlay_img = Image.fromarray(overlay.astype(np.uint8))
                overlay_img.save(overlay_path, quality=95)
                print(f" Saved colored overlay: {overlay_path}")

                # Timing summary
                total_time = load_time + inference_time
                print(f"\n TIMING SUMMARY:")
                print(f"    Model load:  {load_time:.2f}s")
                print(f"    Inference:   {inference_time:.2f}s")
                print(f"    Total:       {total_time:.2f}s")

            else:
                print("\n No masks found in the image")
        else:
            print("\n No results returned from model")

    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print(" FastSAM is faster than SAM2 (uses YOLOv8-seg)")
    print("    It segments objects but does NOT label them.")
    print("    For labeled detection, use YOLOE with text prompts.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_fastsam.py <image_path> [--cpu]")
        print("Example: python test_fastsam.py pedidotest.jpg --cpu")
        sys.exit(1)

    image_path = sys.argv[1]
    force_cpu = "--cpu" in sys.argv

    test_fastsam(image_path, force_cpu=force_cpu)
