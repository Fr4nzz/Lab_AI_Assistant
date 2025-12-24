"""Configuration management for Lab Assistant with LangGraph."""
import os
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
BACKEND_DIR = Path(__file__).parent.absolute()

load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        # LLM Provider settings (new for LangGraph)
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")

        # Gemini settings
        self.gemini_api_keys: List[str] = self._get_api_keys()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        # Also set GOOGLE_API_KEY for LangChain compatibility
        if self.gemini_api_keys and not os.getenv("GOOGLE_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = self.gemini_api_keys[0]

        # OpenRouter settings (for production)
        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_model: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

        # Target website
        self.target_url: str = os.getenv("TARGET_URL", "https://laboratoriofranz.orion-labs.com/ordenes")

        # Browser data uses absolute path by default
        browser_data = os.getenv("BROWSER_DATA_DIR", "browser_data")
        if not Path(browser_data).is_absolute():
            self.browser_data_dir = str(BACKEND_DIR / browser_data)
        else:
            self.browser_data_dir = browser_data

        self.browser_channel: str = os.getenv("BROWSER_CHANNEL", "msedge")
        self.headless: bool = os.getenv("HEADLESS", "false").lower() == "true"

        # Database settings
        self.database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR}/lab_assistant.db")
        self.checkpoints_db: str = os.getenv("CHECKPOINTS_DB", str(BACKEND_DIR / "data" / "checkpoints.db"))

        # Server settings
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))

        # Debug mode
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    def _get_api_keys(self) -> List[str]:
        """Parse comma-separated API keys from environment."""
        keys_str = os.getenv("GEMINI_API_KEYS", "")
        if not keys_str:
            # Try single key from GOOGLE_API_KEY
            single_key = os.getenv("GOOGLE_API_KEY", "")
            if single_key:
                return [single_key]
            # Return empty list instead of raising error (might use OpenRouter)
            return []
        return [k.strip() for k in keys_str.split(",") if k.strip()]


settings = Settings()
