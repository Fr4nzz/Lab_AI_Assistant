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
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Any, Dict, Set
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

# Disable google-genai SDK internal retries by setting retry attempts to 0
# This allows our key rotation logic to handle rate limits immediately
os.environ.setdefault("GOOGLE_API_PYTHON_CLIENT_RETRIES", "0")

logger = logging.getLogger(__name__)


def _disable_genai_sdk_retry():
    """
    Disable the google-genai SDK's internal tenacity retry.
    The SDK retries 429 errors with exponential backoff which conflicts with our key rotation.
    """
    try:
        from google.genai import _api_client
        from tenacity import stop_after_attempt

        # Check if already patched
        if hasattr(_api_client.BaseApiClient, '_retry_patched'):
            logger.info("[Model] SDK retry already patched")
            return

        # Get the retry-decorated method
        method = _api_client.BaseApiClient._request_once
        logger.info(f"[Model] Found SDK method, type: {type(method)}, has retry: {hasattr(method, 'retry')}")

        # Modify the retry configuration to stop immediately (after 1 attempt = no retries)
        if hasattr(method, 'retry'):
            original_stop = method.retry.stop
            method.retry.stop = stop_after_attempt(1)
            _api_client.BaseApiClient._retry_patched = True
            logger.info(f"[Model] Disabled SDK internal retry (was: {original_stop}, now: stop_after_attempt(1))")
        else:
            # Try alternative: the method might be wrapped differently
            logger.info(f"[Model] SDK method attrs: {[a for a in dir(method) if not a.startswith('_')]}")
    except ImportError as e:
        logger.info(f"[Model] google.genai SDK not found: {e}")
    except Exception as e:
        logger.info(f"[Model] Could not disable SDK retry: {type(e).__name__}: {e}")


# Try to disable SDK retry on module load
_disable_genai_sdk_retry()

# Rate limit tracking file
RATE_LIMIT_FILE = Path(__file__).parent / "data" / "rate_limits.json"


# Class-level shared state (outside class to avoid Pydantic ModelPrivateAttr issues)
_shared_key_index: int = 0
_shared_last_request_time: float = 0
_daily_exhausted_keys: Set[int] = set()  # Indices of keys that hit daily limit


def _load_rate_limits() -> Dict:
    """Load rate limit data from file."""
    if RATE_LIMIT_FILE.exists():
        try:
            with open(RATE_LIMIT_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[Model] Could not load rate limits: {e}")
    return {"date": None, "exhausted_keys": []}


def _save_rate_limits(data: Dict):
    """Save rate limit data to file."""
    RATE_LIMIT_FILE.parent.mkdir(exist_ok=True)
    try:
        with open(RATE_LIMIT_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"[Model] Could not save rate limits: {e}")


def _mark_key_exhausted(key_index: int, model_name: str):
    """Mark a key as exhausted for today's daily limit."""
    global _daily_exhausted_keys
    _daily_exhausted_keys.add(key_index)

    data = _load_rate_limits()
    today = date.today().isoformat()

    # Reset if new day
    if data.get("date") != today:
        data = {"date": today, "exhausted_keys": []}

    # Add key if not already there
    key_entry = {"index": key_index, "model": model_name}
    if key_entry not in data["exhausted_keys"]:
        data["exhausted_keys"].append(key_entry)
        logger.info(f"[Model] Marked Key #{key_index + 1} as daily-exhausted for {model_name}")

    _save_rate_limits(data)


def _init_exhausted_keys(model_name: str):
    """Load exhausted keys from file on startup."""
    global _daily_exhausted_keys
    data = _load_rate_limits()
    today = date.today().isoformat()

    if data.get("date") == today:
        for entry in data.get("exhausted_keys", []):
            if entry.get("model") == model_name:
                _daily_exhausted_keys.add(entry["index"])
                logger.info(f"[Model] Key #{entry['index'] + 1} is daily-exhausted (from file)")
    else:
        # New day, clear exhausted keys
        _daily_exhausted_keys.clear()
        _save_rate_limits({"date": today, "exhausted_keys": []})


def _is_daily_rate_limit(error_str: str) -> bool:
    """Check if error is a daily rate limit (not per-minute)."""
    return "PerDay" in error_str or "per_day" in error_str.lower()


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
    _bound_tools: Optional[List[Any]] = None  # Store tools for re-binding after key switch
    _tool_kwargs: Optional[Dict] = None  # Store bind_tools kwargs

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, api_keys: List[str], model_name: str = "gemini-2.0-flash", **kwargs):
        super().__init__(api_keys=api_keys, model_name=model_name, **kwargs)
        self.max_retries = len(api_keys) * 2
        self._bound_tools = None
        self._tool_kwargs = None

        # Load exhausted keys from file and skip to first available key
        _init_exhausted_keys(model_name)
        self._skip_to_available_key()
        self._configure_model()

    def _skip_to_available_key(self):
        """Skip to the first key that's not daily-exhausted."""
        global _shared_key_index, _daily_exhausted_keys
        original_index = _shared_key_index
        tried = 0

        while _shared_key_index in _daily_exhausted_keys and tried < len(self.api_keys):
            logger.info(f"[Model] Skipping Key #{_shared_key_index + 1} (daily exhausted)")
            _shared_key_index = (_shared_key_index + 1) % len(self.api_keys)
            tried += 1

        if tried == len(self.api_keys):
            logger.warning(f"[Model] All {len(self.api_keys)} keys are daily-exhausted!")
            _shared_key_index = original_index  # Reset to original

    def _configure_model(self):
        """Creates a new model with the current API key. Re-binds tools if previously bound."""
        global _shared_key_index
        key = self.api_keys[_shared_key_index]

        # Detect if using Gemini 3.x (supports thinking_level)
        is_gemini_3 = "gemini-3" in self.model_name.lower()

        model_kwargs = {
            "model": self.model_name,
            "google_api_key": key,
            "temperature": self.temperature,
            "convert_system_message_to_human": True,
            "max_retries": 0,  # Disable LangChain's internal retry
            "timeout": 30,  # Short timeout to fail faster on rate limits
        }

        # Enable thinking for supported models
        if is_gemini_3:
            model_kwargs["include_thoughts"] = True
            model_kwargs["thinking_level"] = "high"  # Maximum reasoning capability
            logger.info(f"[Model] Enabling thinking (HIGH) for Gemini 3 model")

        base_model = ChatGoogleGenerativeAI(**model_kwargs)

        # Re-bind tools if they were previously bound
        if self._bound_tools:
            self._current_model = base_model.bind_tools(self._bound_tools, **(self._tool_kwargs or {}))
            logger.info(f"[Model] Re-bound {len(self._bound_tools)} tools after key switch")
        else:
            self._current_model = base_model

        logger.info(f"[Model] Configured with Key #{_shared_key_index + 1}")

    def _switch_key(self, mark_exhausted: bool = False):
        """Rotates to the next API key, optionally marking current as daily-exhausted."""
        global _shared_key_index, _daily_exhausted_keys

        if mark_exhausted:
            _mark_key_exhausted(_shared_key_index, self.model_name)

        _shared_key_index = (_shared_key_index + 1) % len(self.api_keys)

        # Skip exhausted keys
        tried = 0
        while _shared_key_index in _daily_exhausted_keys and tried < len(self.api_keys):
            logger.info(f"[Model] Skipping Key #{_shared_key_index + 1} (daily exhausted)")
            _shared_key_index = (_shared_key_index + 1) % len(self.api_keys)
            tried += 1

        logger.info(f"[Model] Switching to Key #{_shared_key_index + 1}")
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
        global _shared_last_request_time
        logger.info(f"[Model] _generate called with {len(messages)} messages")
        logger.info(f"[Model] _current_model type: {type(self._current_model)}")
        logger.info(f"[Model] _current_model has _generate: {hasattr(self._current_model, '_generate')}")
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Rate limit between requests
                elapsed = time.time() - _shared_last_request_time
                if elapsed < self.min_request_interval:
                    time.sleep(self.min_request_interval - elapsed)
                _shared_last_request_time = time.time()

                # Handle both ChatGoogleGenerativeAI and RunnableBinding (from bind_tools)
                # RunnableBinding has _generate but it doesn't handle tools properly - use invoke
                from langchain_core.runnables import RunnableBinding
                if isinstance(self._current_model, RunnableBinding):
                    logger.info(f"[Model] Using invoke for RunnableBinding")
                    result = self._current_model.invoke(messages, stop=stop, **kwargs)
                    logger.info(f"[Model] Result type: {type(result)}, has tool_calls: {bool(getattr(result, 'tool_calls', None))}")
                    from langchain_core.outputs import ChatGeneration
                    return ChatResult(generations=[ChatGeneration(message=result)])
                elif hasattr(self._current_model, '_generate'):
                    return self._current_model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                else:
                    # RunnableBinding - use invoke and wrap result
                    logger.debug(f"[Model] Calling RunnableBinding.invoke with {len(messages)} messages")
                    result = self._current_model.invoke(messages, stop=stop, **kwargs)
                    logger.debug(f"[Model] RunnableBinding result type: {type(result)}")
                    logger.debug(f"[Model] RunnableBinding result: {result}")
                    if hasattr(result, 'content'):
                        logger.debug(f"[Model] Result content: {result.content[:200] if result.content else '(empty)'}")
                    if hasattr(result, 'tool_calls'):
                        logger.debug(f"[Model] Result tool_calls: {result.tool_calls}")
                    from langchain_core.outputs import ChatGeneration
                    return ChatResult(generations=[ChatGeneration(message=result)])

            except Exception as e:
                last_error = e
                error_str = str(e)
                if self._is_rate_limit_error(e):
                    is_daily = _is_daily_rate_limit(error_str)

                    if is_daily:
                        logger.warning(f"[Model] DAILY rate limit on Key #{_shared_key_index + 1}, marking exhausted")
                        self._switch_key(mark_exhausted=True)
                        # No wait for daily - just switch immediately
                    else:
                        # Per-minute limit - switch and wait briefly
                        logger.warning(f"[Model] Per-minute rate limit on Key #{_shared_key_index + 1}, switching")
                        self._switch_key(mark_exhausted=False)
                        time.sleep(1)  # Brief pause before retry with new key
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
        global _shared_last_request_time
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Rate limit between requests
                elapsed = time.time() - _shared_last_request_time
                if elapsed < self.min_request_interval:
                    await asyncio.sleep(self.min_request_interval - elapsed)
                _shared_last_request_time = time.time()

                # Handle both ChatGoogleGenerativeAI and RunnableBinding (from bind_tools)
                # RunnableBinding has _agenerate but it doesn't handle tools properly - use ainvoke
                from langchain_core.runnables import RunnableBinding
                if isinstance(self._current_model, RunnableBinding):
                    logger.info(f"[Model] Using ainvoke for RunnableBinding")
                    result = await self._current_model.ainvoke(messages, stop=stop, **kwargs)
                    logger.info(f"[Model] Result type: {type(result)}, has tool_calls: {bool(getattr(result, 'tool_calls', None))}")
                    from langchain_core.outputs import ChatGeneration
                    return ChatResult(generations=[ChatGeneration(message=result)])
                elif hasattr(self._current_model, '_agenerate'):
                    return await self._current_model._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
                else:
                    # Fallback - use ainvoke and wrap result
                    logger.debug(f"[Model] Calling ainvoke fallback with {len(messages)} messages")
                    result = await self._current_model.ainvoke(messages, stop=stop, **kwargs)
                    from langchain_core.outputs import ChatGeneration
                    return ChatResult(generations=[ChatGeneration(message=result)])

            except Exception as e:
                last_error = e
                error_str = str(e)
                if self._is_rate_limit_error(e):
                    is_daily = _is_daily_rate_limit(error_str)

                    if is_daily:
                        logger.warning(f"[Model] DAILY rate limit on Key #{_shared_key_index + 1}, marking exhausted")
                        self._switch_key(mark_exhausted=True)
                        # No wait for daily - just switch immediately
                    else:
                        # Per-minute limit - switch and wait briefly
                        logger.warning(f"[Model] Per-minute rate limit on Key #{_shared_key_index + 1}, switching")
                        self._switch_key(mark_exhausted=False)
                        await asyncio.sleep(1)  # Brief pause before retry with new key
                else:
                    raise

        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    def bind_tools(self, tools: List[Any], **kwargs):
        """Bind tools to the underlying model. Stores tools for re-binding after key switch."""
        bound = self._current_model.bind_tools(tools, **kwargs)

        # Create new instance (shares module-level state automatically)
        wrapper = ChatGoogleGenerativeAIWithKeyRotation(
            api_keys=self.api_keys,
            model_name=self.model_name,
            temperature=self.temperature,
        )
        wrapper._current_model = bound  # Override with tool-bound model
        wrapper._bound_tools = tools  # Store for re-binding after key switch
        wrapper._tool_kwargs = kwargs

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
