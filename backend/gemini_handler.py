"""Gemini AI handler with API key rotation and multimodal support."""
import asyncio
import time
import base64
from typing import List, Tuple, Optional, Any, Union
from pathlib import Path

from google import genai
from google.genai import types
from google.genai.errors import APIError


class GeminiHandler:
    """Manages API requests to Gemini with key rotation and retries."""

    def __init__(self, api_keys: List[str], model_name: str):
        if not api_keys:
            raise ValueError("API keys list cannot be empty")
        self.api_keys = api_keys
        self.model_name = model_name
        self.current_key_index = 0
        self.max_retries = len(api_keys) * 2
        self.client: Optional[genai.Client] = None
        self._configure_client()

    def _configure_client(self):
        """Configure the Gemini client with current API key."""
        api_key = self.api_keys[self.current_key_index]
        self.client = genai.Client(api_key=api_key)

    def _switch_api_key(self):
        """Switch to the next API key in rotation."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self._configure_client()
        print(f"Switched to API key index {self.current_key_index}")

    async def send_request(
        self,
        system_prompt: str,
        contents: List[Any],
        response_mime_type: str = "application/json"
    ) -> Tuple[str, bool]:
        """
        Send request to Gemini with automatic key rotation on rate limits.

        Args:
            system_prompt: System instructions for the model
            contents: List of content (strings, Part objects for images/audio)
            response_mime_type: Expected response format

        Returns:
            Tuple of (response_text, success_bool)
        """
        last_error = None

        # Compact debug
        print(f"[GEMINI] Sending to {self.model_name} (prompt:{len(system_prompt)}c, key:{self.current_key_index})")

        for attempt in range(self.max_retries):
            try:

                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type=response_mime_type
                )

                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=contents,
                    config=config
                )

                # Extract text from response
                if response.candidates and response.candidates[0].content:
                    text = ""
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            text += part.text
                    print(f"[GEMINI] OK ({len(text)}c): {text[:150]}...")
                    return text, True

                print(f"[GEMINI] ERROR: No content in response")
                return "", False

            except APIError as e:
                last_error = e
                error_code = getattr(e, 'code', None)
                print(f"[GEMINI] APIError: code={error_code}, message={e}")

                if error_code in [429, 500, 503]:
                    # Rate limit or server error - switch key and retry
                    print(f"[GEMINI] Switching API key...")
                    self._switch_api_key()
                    await asyncio.sleep(2)
                    continue
                else:
                    print(f"[GEMINI] Non-retryable error, stopping")
                    break

            except Exception as e:
                last_error = e
                print(f"[GEMINI] Unexpected error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                self._switch_api_key()
                await asyncio.sleep(2)
                continue

        print(f"[GEMINI] FAILED after {self.max_retries} attempts")
        return f"Failed after {self.max_retries} attempts: {last_error}", False


def create_image_part(image_data: Union[bytes, str], mime_type: str = "image/jpeg") -> types.Part:
    """
    Create a Part object from image bytes or base64 string.
    
    Args:
        image_data: Either raw bytes or base64 encoded string
        mime_type: MIME type of the image (image/jpeg, image/png, etc.)
    """
    if isinstance(image_data, str):
        # Assume it's base64 encoded
        image_bytes = base64.b64decode(image_data)
    else:
        image_bytes = image_data
    
    return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


def create_audio_part(audio_data: Union[bytes, str], mime_type: str = "audio/wav") -> types.Part:
    """
    Create a Part object from audio bytes or base64 string.
    
    Args:
        audio_data: Either raw bytes or base64 encoded string
        mime_type: MIME type of the audio (audio/wav, audio/mp3, audio/webm, etc.)
    """
    if isinstance(audio_data, str):
        audio_bytes = base64.b64decode(audio_data)
    else:
        audio_bytes = audio_data
    
    return types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)


def load_image_from_file(file_path: str) -> Tuple[bytes, str]:
    """Load image from file and return bytes with detected mime type."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    
    mime_type = mime_types.get(suffix, 'image/jpeg')
    
    with open(file_path, 'rb') as f:
        return f.read(), mime_type


def load_audio_from_file(file_path: str) -> Tuple[bytes, str]:
    """Load audio from file and return bytes with detected mime type."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    mime_types = {
        '.wav': 'audio/wav',
        '.mp3': 'audio/mp3',
        '.webm': 'audio/webm',
        '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4',
    }
    
    mime_type = mime_types.get(suffix, 'audio/wav')
    
    with open(file_path, 'rb') as f:
        return f.read(), mime_type
