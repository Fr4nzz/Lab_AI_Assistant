"""
Pre-download AI models required by Lab Assistant.

This script downloads:
- YOLOE model for document detection
- MobileCLIP for text prompts

Run during first-time setup to avoid delays on first use.
Models are saved in the backend/ directory.
"""

import sys
import os
from pathlib import Path

# Get the backend directory (parent of scripts/)
BACKEND_DIR = Path(__file__).parent.parent.absolute()

# Add backend to path
sys.path.insert(0, str(BACKEND_DIR))


def download_yoloe_model():
    """Download YOLOE model if not already present."""
    model_name = "yoloe-11l-seg.pt"
    model_path = BACKEND_DIR / model_name

    # Check if model already exists in backend directory
    if model_path.exists():
        print(f"  [OK] {model_name} already downloaded")
        return True

    print(f"  Downloading {model_name} to backend/...")

    # Change to backend directory so models are saved there
    original_dir = os.getcwd()
    os.chdir(BACKEND_DIR)

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
    finally:
        # Restore original directory
        os.chdir(original_dir)


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
