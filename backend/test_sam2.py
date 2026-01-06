#!/usr/bin/env python3
"""
Test script for SAM 2.1 (Segment Anything Model 2.1) - Tiny variant
SAM2 segments objects WITHOUT labels - it just finds distinct regions.

Usage:
    python test_sam2.py <image_path>
    python test_sam2.py pedidotest.jpg
"""

import sys
import os
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_sam2(input_path: str):
    """Test SAM 2.1 automatic mask generation."""

    print("=" * 60)
    print("SAM 2.1 Tiny - Automatic Segmentation Test")
    print("=" * 60)

    # Check if file exists
    if not os.path.exists(input_path):
        print(f"❌ Error: File not found: {input_path}")
        return

    print(f"\n📁 Input image: {input_path}")

    # Try to import SAM2
    print("\n📦 Loading SAM 2.1...")

    try:
        from ultralytics import SAM
        print("✅ Using Ultralytics SAM implementation")
        use_ultralytics = True
    except ImportError:
        print("❌ Ultralytics SAM not available, trying sam2 package...")
        use_ultralytics = False

    if use_ultralytics:
        # Use Ultralytics implementation
        try:
            # Load SAM 2.1 tiny model
            model_name = "sam2.1_t.pt"
            print(f"\n🔄 Loading model: {model_name}")
            model = SAM(model_name)
            print(f"✅ Model loaded successfully")

            # Load and process image
            from PIL import Image, ImageOps
            img = Image.open(input_path)
            img = ImageOps.exif_transpose(img)  # Fix rotation
            print(f"📐 Image size: {img.size[0]}x{img.size[1]}")

            # Run automatic segmentation (no prompts)
            print("\n🔍 Running automatic segmentation...")
            results = model.predict(input_path, verbose=False)

            if results and len(results) > 0:
                result = results[0]

                # Check for masks
                if result.masks is not None:
                    num_masks = len(result.masks)
                    print(f"\n✅ Found {num_masks} segments/masks")

                    # Get mask details
                    masks = result.masks

                    print("\n📊 Segment Details:")
                    print("-" * 40)

                    for i, mask in enumerate(masks.data):
                        # Calculate mask area
                        mask_np = mask.cpu().numpy()
                        area = mask_np.sum()
                        total_pixels = mask_np.size
                        percentage = (area / total_pixels) * 100

                        print(f"  Segment {i+1}: {area:,} pixels ({percentage:.1f}% of image)")

                    # Save annotated image
                    output_path = input_path.rsplit('.', 1)[0] + '_sam2_segments.jpg'

                    # Plot and save
                    annotated = result.plot()

                    from PIL import Image as PILImage
                    import numpy as np

                    # Convert BGR to RGB if needed
                    if len(annotated.shape) == 3 and annotated.shape[2] == 3:
                        annotated_rgb = annotated[:, :, ::-1]
                    else:
                        annotated_rgb = annotated

                    output_img = PILImage.fromarray(annotated_rgb)
                    output_img.save(output_path, quality=95)
                    print(f"\n💾 Saved annotated image: {output_path}")

                    # Also save individual masks
                    print("\n🎭 Saving individual mask overlays...")
                    import numpy as np

                    # Create colorful overlay
                    img_array = np.array(img.convert('RGB'))
                    overlay = img_array.copy().astype(np.float32)

                    # Generate colors for each mask
                    colors = [
                        [255, 0, 0],    # Red
                        [0, 255, 0],    # Green
                        [0, 0, 255],    # Blue
                        [255, 255, 0],  # Yellow
                        [255, 0, 255],  # Magenta
                        [0, 255, 255],  # Cyan
                        [255, 128, 0],  # Orange
                        [128, 0, 255],  # Purple
                        [0, 255, 128],  # Spring Green
                        [255, 0, 128],  # Pink
                    ]

                    for i, mask in enumerate(masks.data):
                        mask_np = mask.cpu().numpy()

                        # Resize mask to image size if needed
                        if mask_np.shape != (img.size[1], img.size[0]):
                            from PIL import Image as PILImage
                            mask_pil = PILImage.fromarray((mask_np * 255).astype(np.uint8))
                            mask_pil = mask_pil.resize((img.size[0], img.size[1]), PILImage.NEAREST)
                            mask_np = np.array(mask_pil) > 127

                        color = colors[i % len(colors)]

                        # Apply color overlay where mask is True
                        for c in range(3):
                            overlay[:, :, c] = np.where(
                                mask_np,
                                overlay[:, :, c] * 0.5 + color[c] * 0.5,
                                overlay[:, :, c]
                            )

                    # Save colored overlay
                    overlay_path = input_path.rsplit('.', 1)[0] + '_sam2_colored.jpg'
                    overlay_img = PILImage.fromarray(overlay.astype(np.uint8))
                    overlay_img.save(overlay_path, quality=95)
                    print(f"💾 Saved colored overlay: {overlay_path}")

                else:
                    print("\n⚠️ No masks found in the image")

            else:
                print("\n⚠️ No results returned from model")

        except Exception as e:
            print(f"\n❌ Error during inference: {e}")
            import traceback
            traceback.print_exc()

    else:
        # Try official SAM2 package
        try:
            from sam2.build_sam import build_sam2
            from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
            import torch

            print("\n🔄 Loading SAM 2.1 tiny model...")

            # Check for model weights
            model_cfg = "sam2.1_hiera_t.yaml"
            checkpoint = "sam2.1_hiera_tiny.pt"

            if not os.path.exists(checkpoint):
                print(f"❌ Checkpoint not found: {checkpoint}")
                print("Please download from: https://github.com/facebookresearch/sam2")
                return

            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"🖥️ Using device: {device}")

            sam2 = build_sam2(model_cfg, checkpoint, device=device)
            mask_generator = SAM2AutomaticMaskGenerator(sam2)

            # Load image
            from PIL import Image, ImageOps
            import numpy as np

            img = Image.open(input_path)
            img = ImageOps.exif_transpose(img)
            img_array = np.array(img.convert('RGB'))

            print(f"📐 Image size: {img.size[0]}x{img.size[1]}")

            # Generate masks
            print("\n🔍 Generating masks...")
            masks = mask_generator.generate(img_array)

            print(f"\n✅ Found {len(masks)} segments")

            # Sort by area
            masks = sorted(masks, key=lambda x: x['area'], reverse=True)

            print("\n📊 Segment Details (sorted by size):")
            print("-" * 40)

            for i, mask_data in enumerate(masks[:20]):  # Show top 20
                area = mask_data['area']
                bbox = mask_data['bbox']  # x, y, w, h
                stability = mask_data.get('stability_score', 0)

                print(f"  Segment {i+1}: {area:,} pixels, "
                      f"bbox=({bbox[0]:.0f},{bbox[1]:.0f},{bbox[2]:.0f},{bbox[3]:.0f}), "
                      f"stability={stability:.2f}")

            if len(masks) > 20:
                print(f"  ... and {len(masks) - 20} more segments")

        except ImportError as e:
            print(f"❌ SAM2 package not installed: {e}")
            print("\nTo install, run:")
            print("  pip install sam2")
            print("\nOr use Ultralytics which includes SAM:")
            print("  pip install ultralytics")

    print("\n" + "=" * 60)
    print("ℹ️  Note: SAM2 segments objects but does NOT label them.")
    print("    It finds distinct regions/objects in the image.")
    print("    For labeled detection, use YOLOE with text prompts.")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_sam2.py <image_path>")
        print("Example: python test_sam2.py pedidotest.jpg")
        sys.exit(1)

    test_sam2(sys.argv[1])
