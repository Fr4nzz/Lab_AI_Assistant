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
import logging
from typing import Optional, List, Any, Iterator
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ChatGoogleGenerativeAIWithKeyRotation(BaseChatModel):
    """
    Wrapper around ChatGoogleGenerativeAI that rotates API keys on rate limits.
    """
    api_keys: List[str]
    model_name: str
    current_key_index: int = 0
    max_retries: int = 6
    temperature: float = 0.7
    _current_model: Optional[ChatGoogleGenerativeAI] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, api_keys: List[str], model_name: str = "gemini-2.0-flash", **kwargs):
        super().__init__(
            api_keys=api_keys,
            model_name=model_name,
            **kwargs
        )
        self.max_retries = len(api_keys) * 2
        self._create_model()

    def _create_model(self):
        """Create a new model instance with current API key."""
        api_key = self.api_keys[self.current_key_index]
        self._current_model = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=self.temperature,
            convert_system_message_to_human=True
        )
        logger.info(f"[Model] Using API key index {self.current_key_index}")

    def _switch_api_key(self):
        """Switch to the next API key in rotation."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self._create_model()
        logger.info(f"[Model] Switched to API key index {self.current_key_index}")

    @property
    def _llm_type(self) -> str:
        return "google-generative-ai-with-rotation"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate with automatic key rotation on rate limits."""
        import time

        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._current_model._generate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors
                if "429" in str(e) or "resource_exhausted" in error_str or "quota" in error_str:
                    logger.warning(f"[Model] Rate limit hit, switching API key (attempt {attempt + 1}/{self.max_retries})")
                    self._switch_api_key()
                    time.sleep(1)
                    continue
                else:
                    # Non-rate-limit error, raise immediately
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
        import asyncio

        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await self._current_model._agenerate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit errors
                if "429" in str(e) or "resource_exhausted" in error_str or "quota" in error_str:
                    logger.warning(f"[Model] Rate limit hit, switching API key (attempt {attempt + 1}/{self.max_retries})")
                    self._switch_api_key()
                    await asyncio.sleep(1)
                    continue
                else:
                    # Non-rate-limit error, raise immediately
                    raise

        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    def bind_tools(self, tools: List[Any], **kwargs):
        """Bind tools to the underlying model."""
        # Create a new instance with tools bound
        bound_model = self._current_model.bind_tools(tools, **kwargs)

        # Create a wrapper that maintains key rotation
        wrapper = ChatGoogleGenerativeAIWithKeyRotation(
            api_keys=self.api_keys,
            model_name=self.model_name,
            temperature=self.temperature
        )
        wrapper._current_model = bound_model
        return wrapper

    @property
    def _identifying_params(self):
        return {
            "model_name": self.model_name,
            "num_keys": len(self.api_keys),
            "current_key_index": self.current_key_index
        }


def get_chat_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None
) -> BaseChatModel:
    """
    Get chat model based on provider.

    Args:
        provider: "gemini" or "openrouter". Defaults to LLM_PROVIDER env var.
        model_name: Specific model name. Defaults based on provider.

    Returns:
        Configured chat model instance.

    Environment Variables:
        LLM_PROVIDER: Default provider ("gemini" or "openrouter")
        GEMINI_API_KEYS: Comma-separated list of API keys for rotation
        GOOGLE_API_KEY: Single API key (fallback)
        OPENROUTER_API_KEY: Required for OpenRouter
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        # Get API keys (support multiple for rotation)
        api_keys = []
        keys_str = os.environ.get("GEMINI_API_KEYS", "")
        if keys_str:
            api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]

        # Fallback to single key
        if not api_keys:
            single_key = os.environ.get("GOOGLE_API_KEY", "")
            if single_key:
                api_keys = [single_key]

        if not api_keys:
            raise ValueError("No Gemini API keys found. Set GEMINI_API_KEYS or GOOGLE_API_KEY")

        model = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        logger.info(f"[Model] Using Gemini with {len(api_keys)} API key(s), model: {model}")

        if len(api_keys) > 1:
            return ChatGoogleGenerativeAIWithKeyRotation(
                api_keys=api_keys,
                model_name=model
            )
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
    """
    Get model configured for multi-modal input (images, audio).

    For Gemini: Native multi-modal support
    For OpenRouter: Use vision-capable models
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        return get_chat_model(provider="gemini", model_name="gemini-2.0-flash")
    else:
        return ChatOpenAI(
            model="google/gemini-2.0-flash-exp:free",
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
