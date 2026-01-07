"""
Pre-download AI models required by Lab Assistant.

This script downloads:
- YOLOE model for document detection
- MobileCLIP for text prompts

Run during first-time setup to avoid delays on first use.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def download_yoloe_model():
    """Download YOLOE model if not already present."""
    model_name = "yoloe-11l-seg.pt"

    # Check if model already exists in ultralytics cache
    from pathlib import Path
    cache_dir = Path.home() / ".cache" / "ultralytics"

    # Also check current directory (ultralytics sometimes downloads here)
    if Path(model_name).exists():
        print(f"  [OK] {model_name} already downloaded")
        return True

    print(f"  Downloading {model_name}...")
    try:
        from ultralytics import YOLOE

        # Creating the model triggers download
        model = YOLOE(model_name)

        # Initialize with text prompts (downloads MobileCLIP if needed)
        prompts = ["document", "paper", "notebook", "book"]
        text_pe = model.get_text_pe(prompts)
        model.set_classes(prompts, text_pe)

        print(f"  [OK] YOLOE model downloaded and initialized")
        return True

    except ImportError:
        print("  [!] ultralytics not installed - skipping YOLOE download")
        return False
    except Exception as e:
        print(f"  [!] Failed to download YOLOE model: {e}")
        return False


def main():
    """Download all required models."""
    print("Checking AI models...")

    success = download_yoloe_model()

    if success:
        print("Model download complete!")
    else:
        print("Some models could not be downloaded - they will download on first use")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
