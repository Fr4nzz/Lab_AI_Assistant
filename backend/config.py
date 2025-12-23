"""Configuration management for Lab Assistant."""
import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde el directorio del proyecto
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
BACKEND_DIR = Path(__file__).parent.absolute()

load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Application settings loaded from environment variables."""
    
    def __init__(self):
        self.gemini_api_keys: List[str] = self._get_api_keys()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-preview-05-20")
        self.target_url: str = os.getenv("TARGET_URL", "https://laboratoriofranz.orion-labs.com/")
        
        # Browser data usa ruta absoluta por defecto
        browser_data = os.getenv("BROWSER_DATA_DIR", "browser_data")
        if not Path(browser_data).is_absolute():
            self.browser_data_dir = str(BACKEND_DIR / browser_data)
        else:
            self.browser_data_dir = browser_data
        
        self.browser_channel: str = os.getenv("BROWSER_CHANNEL", "msedge")
        self.database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR}/lab_assistant.db")
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    def _get_api_keys(self) -> List[str]:
        """Parse comma-separated API keys from environment."""
        keys_str = os.getenv("GEMINI_API_KEYS", "")
        if not keys_str:
            raise ValueError("GEMINI_API_KEYS environment variable is required")
        return [k.strip() for k in keys_str.split(",") if k.strip()]


settings = Settings()
