"""
Model provider abstraction for Gemini (dev) and OpenRouter (production).
Includes API key rotation for handling rate limits.

DOCUMENTATION:
- ChatGoogleGenerativeAI: https://python.langchain.com/docs/integrations/chat/google_generative_ai
- ChatOpenAI with OpenRouter: https://openrouter.ai/docs

USAGE:
    model = get_chat_model()  # Uses LLM_PROVIDER env var
    model_with_tools = model.bind_tools(tools)
"""
import os
import time
import asyncio
import logging
import re
from typing import Optional, List, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ChatGoogleGenerativeAIWithKeyRotation(BaseChatModel):
    """
    Wrapper around ChatGoogleGenerativeAI that rotates API keys on rate limits.
    Disables internal retry so our key rotation works properly.
    """
    api_keys: List[str]
    model_name: str
    max_retries: int = 6
    temperature: float = 0.7
    min_request_interval: float = 4.0  # 15 RPM = 4s interval
    _current_model: Optional[ChatGoogleGenerativeAI] = None

    # Class-level shared state
    _key_index: int = 0
    _last_request_time: float = 0

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, api_keys: List[str], model_name: str = "gemini-2.0-flash", **kwargs):
        super().__init__(api_keys=api_keys, model_name=model_name, **kwargs)
        self.max_retries = len(api_keys) * 2
        self._configure_model()

    def _configure_model(self):
        """Creates a new model with the current API key."""
        key = self.api_keys[ChatGoogleGenerativeAIWithKeyRotation._key_index]
        self._current_model = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=key,
            temperature=self.temperature,
            convert_system_message_to_human=True,
            max_retries=0,  # Disable internal retry
        )
        logger.info(f"[Model] Configured with Key #{ChatGoogleGenerativeAIWithKeyRotation._key_index + 1}")

    def _switch_key(self):
        """Rotates to the next API key."""
        ChatGoogleGenerativeAIWithKeyRotation._key_index = (
            ChatGoogleGenerativeAIWithKeyRotation._key_index + 1
        ) % len(self.api_keys)
        logger.info(f"[Model] Switching to Key #{ChatGoogleGenerativeAIWithKeyRotation._key_index + 1}")
        self._configure_model()

    @property
    def _llm_type(self) -> str:
        return "google-generative-ai-with-rotation"

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is a rate limit error."""
        error_str = str(error).lower()
        return "429" in str(error) or "resource_exhausted" in error_str or "quota" in error_str

    def _parse_retry_delay(self, error_str: str) -> float:
        """Parse retry delay from error message."""
        match = re.search(r'retry.*?(\d+(?:\.\d+)?)\s*s', error_str.lower())
        return float(match.group(1)) if match else 5.0

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate with automatic key rotation on rate limits."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Rate limit between requests
                elapsed = time.time() - ChatGoogleGenerativeAIWithKeyRotation._last_request_time
                if elapsed < self.min_request_interval:
                    time.sleep(self.min_request_interval - elapsed)
                ChatGoogleGenerativeAIWithKeyRotation._last_request_time = time.time()

                return self._current_model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

            except Exception as e:
                last_error = e
                if self._is_rate_limit_error(e):
                    wait = min(self._parse_retry_delay(str(e)), 10)
                    logger.warning(f"[Model] Rate limit on Key #{ChatGoogleGenerativeAIWithKeyRotation._key_index + 1}, "
                                   f"waiting {wait:.0f}s (attempt {attempt + 1}/{self.max_retries})")
                    self._switch_key()
                    time.sleep(wait)
                else:
                    raise

        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate with automatic key rotation on rate limits."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Rate limit between requests
                elapsed = time.time() - ChatGoogleGenerativeAIWithKeyRotation._last_request_time
                if elapsed < self.min_request_interval:
                    await asyncio.sleep(self.min_request_interval - elapsed)
                ChatGoogleGenerativeAIWithKeyRotation._last_request_time = time.time()

                return await self._current_model._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

            except Exception as e:
                last_error = e
                if self._is_rate_limit_error(e):
                    wait = min(self._parse_retry_delay(str(e)), 10)
                    logger.warning(f"[Model] Rate limit on Key #{ChatGoogleGenerativeAIWithKeyRotation._key_index + 1}, "
                                   f"waiting {wait:.0f}s (attempt {attempt + 1}/{self.max_retries})")
                    self._switch_key()
                    await asyncio.sleep(wait)
                else:
                    raise

        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    def bind_tools(self, tools: List[Any], **kwargs):
        """Bind tools to the underlying model."""
        bound = self._current_model.bind_tools(tools, **kwargs)

        # Create wrapper sharing state (skip __init__ to avoid reconfiguring)
        wrapper = object.__new__(ChatGoogleGenerativeAIWithKeyRotation)
        wrapper.api_keys = self.api_keys
        wrapper.model_name = self.model_name
        wrapper.temperature = self.temperature
        wrapper.max_retries = self.max_retries
        wrapper.min_request_interval = self.min_request_interval
        wrapper._current_model = bound

        logger.info(f"[Model] Bound {len(tools)} tools")
        return wrapper

    @property
    def _identifying_params(self):
        return {"model_name": self.model_name, "num_keys": len(self.api_keys)}


def get_chat_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseChatModel:
    """
    Get chat model based on provider.

    Environment Variables:
        LLM_PROVIDER: "gemini" or "openrouter"
        GEMINI_API_KEYS: Comma-separated API keys for rotation
        GOOGLE_API_KEY: Single API key (fallback)
        OPENROUTER_API_KEY: Required for OpenRouter
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        # Get API keys (support multiple for rotation)
        keys_str = os.environ.get("GEMINI_API_KEYS", "")
        api_keys = [k.strip() for k in keys_str.split(",") if k.strip()] if keys_str else []

        # Fallback to single key
        if not api_keys:
            single_key = os.environ.get("GOOGLE_API_KEY", "")
            if single_key:
                api_keys = [single_key]

        if not api_keys:
            raise ValueError("No Gemini API keys found. Set GEMINI_API_KEYS or GOOGLE_API_KEY")

        model = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info(f"[Model] Using Gemini with {len(api_keys)} key(s), model: {model}")

        if len(api_keys) > 1:
            return ChatGoogleGenerativeAIWithKeyRotation(api_keys=api_keys, model_name=model)
        else:
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_keys[0],
                temperature=0.7,
                convert_system_message_to_human=True
            )

    elif provider == "openrouter":
        return ChatOpenAI(
            model=model_name or os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free"),
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": os.environ.get("APP_URL", "http://localhost:3000"),
                "X-Title": "Lab Assistant"
            },
            temperature=0.7
        )

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'gemini' or 'openrouter'.")


def get_model_with_multimodal_support(provider: Optional[str] = None) -> BaseChatModel:
    """Get model configured for multi-modal input (images, audio)."""
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        return get_chat_model(provider="gemini", model_name="gemini-2.0-flash")
    else:
        return ChatOpenAI(
            model="google/gemini-2.0-flash-exp:free",
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
