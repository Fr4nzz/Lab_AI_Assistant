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
    The SDK uses Retrying class internally (not decorator), so we patch that.
    """
    try:
        import tenacity
        from tenacity import stop_after_attempt

        # Check if already patched
        if hasattr(tenacity.Retrying, '_patched_for_genai'):
            logger.info("[Model] Tenacity Retrying already patched")
            return

        # Store original __init__
        original_init = tenacity.Retrying.__init__

        def patched_init(self, *args, **kwargs):
            # Force stop after 1 attempt (no retries) for all Retrying instances
            kwargs['stop'] = stop_after_attempt(1)
            # Also disable wait time
            kwargs['wait'] = tenacity.wait_none()
            original_init(self, *args, **kwargs)

        # Apply patch
        tenacity.Retrying.__init__ = patched_init
        tenacity.Retrying._patched_for_genai = True
        logger.info("[Model] Patched tenacity.Retrying to stop after 1 attempt (no retries)")

    except ImportError as e:
        logger.info(f"[Model] tenacity not found: {e}")
    except Exception as e:
        logger.info(f"[Model] Could not patch tenacity: {type(e).__name__}: {e}")


# Flag to track if we've tried to patch
_sdk_retry_patch_attempted = False

# Rate limit tracking file
RATE_LIMIT_FILE = Path(__file__).parent / "data" / "rate_limits.json"
USAGE_FILE = Path(__file__).parent / "data" / "usage_stats.json"

# Free tier limit per API key per day
FREE_TIER_DAILY_LIMIT = 20


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


# ============================================================
# USAGE TRACKING
# ============================================================

def _load_usage_stats() -> Dict:
    """Load usage stats from file."""
    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"date": None, "models": {}}


def _save_usage_stats(data: Dict):
    """Save usage stats to file."""
    USAGE_FILE.parent.mkdir(exist_ok=True)
    try:
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"[Model] Could not save usage stats: {e}")


def increment_usage(model_name: str) -> int:
    """Increment usage counter for a model. Returns new count."""
    data = _load_usage_stats()
    today = date.today().isoformat()

    # Reset if new day
    if data.get("date") != today:
        data = {"date": today, "models": {}}

    # Increment counter
    current = data["models"].get(model_name, 0)
    data["models"][model_name] = current + 1

    _save_usage_stats(data)
    return data["models"][model_name]


def get_usage_stats() -> Dict:
    """Get current usage stats for all models."""
    data = _load_usage_stats()
    today = date.today().isoformat()

    # Return empty if different day
    if data.get("date") != today:
        return {"date": today, "models": {}}

    return data


def get_num_api_keys() -> int:
    """Get the number of configured API keys."""
    keys_str = os.environ.get("GEMINI_API_KEYS", "")
    api_keys = [k.strip() for k in keys_str.split(",") if k.strip()] if keys_str else []
    if not api_keys:
        single_key = os.environ.get("GOOGLE_API_KEY", "")
        if single_key:
            return 1
    return len(api_keys)


def get_daily_limit() -> int:
    """Get total daily limit (num_keys * FREE_TIER_DAILY_LIMIT)."""
    return get_num_api_keys() * FREE_TIER_DAILY_LIMIT


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
        exhausted_count = 0
        for entry in data.get("exhausted_keys", []):
            if entry.get("model") == model_name:
                _daily_exhausted_keys.add(entry["index"])
                exhausted_count += 1
        if exhausted_count > 0:
            logger.info(f"[Model] {exhausted_count} key(s) daily-exhausted for {model_name}")
    else:
        # New day, clear exhausted keys
        _daily_exhausted_keys.clear()
        _save_rate_limits({"date": today, "exhausted_keys": []})


def _is_daily_rate_limit(error_str: str) -> bool:
    """Check if error is a daily rate limit (not per-minute)."""
    error_lower = error_str.lower()

    # Explicit daily indicators
    if "PerDay" in error_str or "per_day" in error_lower or "daily" in error_lower:
        return True

    # Free tier limits are typically daily
    if "free_tier" in error_lower or "freetier" in error_lower:
        return True

    # If it's a quota error but does NOT mention per-minute/rpm, assume daily
    is_quota_error = "quota" in error_lower or "resource_exhausted" in error_lower
    is_per_minute = "per minute" in error_lower or "per_minute" in error_lower or "rpm" in error_lower

    if is_quota_error and not is_per_minute:
        return True

    return False


class AllKeysExhaustedError(Exception):
    """Raised when all API keys have hit their daily rate limit."""
    pass


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
    thinking_budget: Optional[int] = None  # For Gemini 2.5: None=default, 0=disable, -1=dynamic
    thinking_level: Optional[str] = None  # For Gemini 3: None=default(high), 'minimal'/'low'/'medium'/'high' (minimal only for Flash)
    media_resolution: Optional[str] = None  # For Gemini 3: 'unspecified'/'low'/'medium'/'high'/'ultra_high'
    _current_model: Optional[ChatGoogleGenerativeAI] = None
    _bound_tools: Optional[List[Any]] = None  # Store tools for re-binding after key switch
    _tool_kwargs: Optional[Dict] = None  # Store bind_tools kwargs

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, api_keys: List[str], model_name: str = "gemini-flash-latest", thinking_budget: Optional[int] = None, thinking_level: Optional[str] = None, media_resolution: Optional[str] = None, **kwargs):
        super().__init__(api_keys=api_keys, model_name=model_name, thinking_budget=thinking_budget, thinking_level=thinking_level, media_resolution=media_resolution, **kwargs)
        self.max_retries = len(api_keys) * 2
        self._bound_tools = None
        self._tool_kwargs = None

        # Load exhausted keys from file and skip to first available key
        _init_exhausted_keys(model_name)
        self._skip_to_available_key()
        self._configure_model()

    def _skip_to_available_key(self, raise_if_all_exhausted: bool = False):
        """Skip to the first key that's not daily-exhausted.

        Args:
            raise_if_all_exhausted: If True, raises AllKeysExhaustedError when all keys are exhausted.
        """
        global _shared_key_index, _daily_exhausted_keys
        original_index = _shared_key_index
        tried = 0

        while _shared_key_index in _daily_exhausted_keys and tried < len(self.api_keys):
            _shared_key_index = (_shared_key_index + 1) % len(self.api_keys)
            tried += 1

        if tried == len(self.api_keys):
            logger.warning(f"[Model] All {len(self.api_keys)} keys daily-exhausted for {self.model_name}")
            _shared_key_index = original_index  # Reset to original
            if raise_if_all_exhausted:
                raise AllKeysExhaustedError(
                    f"All {len(self.api_keys)} API keys have reached their daily rate limit for {self.model_name}. "
                    f"Please try a different model or wait until tomorrow."
                )

    def _configure_model(self):
        """Creates a new model with the current API key. Re-binds tools if previously bound."""
        global _shared_key_index, _sdk_retry_patch_attempted

        # Try to disable SDK retry on first model creation (when SDK is fully loaded)
        if not _sdk_retry_patch_attempted:
            _sdk_retry_patch_attempted = True
            _disable_genai_sdk_retry()

        key = self.api_keys[_shared_key_index]

        # Detect if using Gemini 3.x (supports thinking_level)
        is_gemini_3 = "gemini-3" in self.model_name.lower()
        # Detect if using Gemini 2.5 (supports thinking_budget)
        is_gemini_25 = "gemini-2.5" in self.model_name.lower()

        model_kwargs = {
            "model": self.model_name,
            "google_api_key": key,
            "temperature": self.temperature,
            "convert_system_message_to_human": True,
            "max_retries": 0,  # Disable LangChain's internal retry
            "timeout": 30,  # Short timeout to fail faster on rate limits
        }

        # Apply thinking configuration
        if is_gemini_3:
            # Gemini 3.x: use thinking_level ('minimal'/'low'/'medium'/'high', minimal only for Flash)
            model_kwargs["include_thoughts"] = True
            if self.thinking_level is not None:
                model_kwargs["thinking_level"] = self.thinking_level
                logger.info(f"[Model] Thinking level '{self.thinking_level}' for {self.model_name}")
            else:
                model_kwargs["thinking_level"] = "high"  # Default to high

            # Apply media resolution for Gemini 3 (only for models that support it)
            if self.media_resolution and self.media_resolution != "unspecified":
                # Convert to the proper format expected by the API
                resolution_map = {
                    "low": "low",
                    "medium": "medium",
                    "high": "high",
                    "ultra_high": "high"  # Map ultra_high to high as fallback
                }
                resolution = resolution_map.get(self.media_resolution, "high")
                model_kwargs["media_resolution"] = resolution
                logger.info(f"[Model] Media resolution '{resolution}' for {self.model_name}")
        elif self.thinking_budget is not None:
            # Explicit thinking_budget was provided (e.g., 0 to disable for Gemini 2.5)
            model_kwargs["thinking_budget"] = self.thinking_budget
            if self.thinking_budget == 0:
                logger.info(f"[Model] Thinking disabled for {self.model_name}")
        elif is_gemini_25:
            # Gemini 2.5: default to dynamic thinking (-1) unless explicitly disabled
            model_kwargs["thinking_budget"] = -1  # Dynamic thinking

        base_model = ChatGoogleGenerativeAI(**model_kwargs)

        # Re-bind tools if they were previously bound
        if self._bound_tools:
            self._current_model = base_model.bind_tools(self._bound_tools, **(self._tool_kwargs or {}))
        else:
            self._current_model = base_model

    def _switch_key(self, mark_exhausted: bool = False):
        """Rotates to the next API key, optionally marking current as daily-exhausted."""
        global _shared_key_index, _daily_exhausted_keys

        old_key = _shared_key_index + 1
        if mark_exhausted:
            _mark_key_exhausted(_shared_key_index, self.model_name)

        _shared_key_index = (_shared_key_index + 1) % len(self.api_keys)

        # Skip exhausted keys
        tried = 0
        while _shared_key_index in _daily_exhausted_keys and tried < len(self.api_keys):
            _shared_key_index = (_shared_key_index + 1) % len(self.api_keys)
            tried += 1

        logger.info(f"[Model] Switched from Key #{old_key} to Key #{_shared_key_index + 1}")
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

    def _check_all_keys_exhausted(self):
        """Check if all keys are exhausted and raise error if so."""
        global _daily_exhausted_keys
        if len(_daily_exhausted_keys) >= len(self.api_keys):
            raise AllKeysExhaustedError(
                f"Todas las {len(self.api_keys)} API keys han alcanzado su límite diario para {self.model_name}. "
                f"Por favor cambia de modelo o intenta mañana."
            )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate with automatic key rotation on rate limits."""
        global _shared_last_request_time

        # Check upfront if all keys are already exhausted
        self._check_all_keys_exhausted()

        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Rate limit between requests
                elapsed = time.time() - _shared_last_request_time
                if elapsed < self.min_request_interval:
                    time.sleep(self.min_request_interval - elapsed)
                _shared_last_request_time = time.time()

                # Handle both ChatGoogleGenerativeAI and RunnableBinding (from bind_tools)
                from langchain_core.runnables import RunnableBinding
                from langchain_core.outputs import ChatGeneration

                if isinstance(self._current_model, RunnableBinding):
                    result = self._current_model.invoke(messages, stop=stop, **kwargs)
                    return ChatResult(generations=[ChatGeneration(message=result)])
                elif hasattr(self._current_model, '_generate'):
                    return self._current_model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                else:
                    result = self._current_model.invoke(messages, stop=stop, **kwargs)
                    return ChatResult(generations=[ChatGeneration(message=result)])

            except AllKeysExhaustedError:
                raise  # Re-raise immediately, don't retry
            except Exception as e:
                last_error = e
                error_str = str(e)
                if self._is_rate_limit_error(e):
                    is_daily = _is_daily_rate_limit(error_str)

                    if is_daily:
                        logger.warning(f"[Model] DAILY rate limit on Key #{_shared_key_index + 1}, marking exhausted")
                        self._switch_key(mark_exhausted=True)
                        # Check if all keys are now exhausted
                        self._check_all_keys_exhausted()
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

        # Check upfront if all keys are already exhausted
        self._check_all_keys_exhausted()

        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Rate limit between requests
                elapsed = time.time() - _shared_last_request_time
                if elapsed < self.min_request_interval:
                    await asyncio.sleep(self.min_request_interval - elapsed)
                _shared_last_request_time = time.time()

                # Handle both ChatGoogleGenerativeAI and RunnableBinding (from bind_tools)
                from langchain_core.runnables import RunnableBinding
                from langchain_core.outputs import ChatGeneration

                if isinstance(self._current_model, RunnableBinding):
                    result = await self._current_model.ainvoke(messages, stop=stop, **kwargs)
                    return ChatResult(generations=[ChatGeneration(message=result)])
                elif hasattr(self._current_model, '_agenerate'):
                    return await self._current_model._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
                else:
                    result = await self._current_model.ainvoke(messages, stop=stop, **kwargs)
                    return ChatResult(generations=[ChatGeneration(message=result)])

            except AllKeysExhaustedError:
                raise  # Re-raise immediately, don't retry
            except Exception as e:
                last_error = e
                error_str = str(e)
                if self._is_rate_limit_error(e):
                    is_daily = _is_daily_rate_limit(error_str)

                    if is_daily:
                        logger.warning(f"[Model] DAILY rate limit on Key #{_shared_key_index + 1}, marking exhausted")
                        self._switch_key(mark_exhausted=True)
                        # Check if all keys are now exhausted
                        self._check_all_keys_exhausted()
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
    model_name: Optional[str] = None,
    thinking_budget: Optional[int] = None,
    thinking_level: Optional[str] = None,
    media_resolution: Optional[str] = None
) -> BaseChatModel:
    """
    Get chat model based on provider.

    Args:
        provider: "gemini" or "openrouter"
        model_name: Model identifier
        thinking_budget: For Gemini 2.5: None=default, 0=disable thinking, -1=dynamic
        thinking_level: For Gemini 3: None=default(high), 'minimal'/'low'/'medium'/'high' (minimal only for Flash)
        media_resolution: For Gemini 3: 'unspecified'/'low'/'medium'/'high'/'ultra_high' for image resolution

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

        model = model_name or os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
        logger.info(f"[Model] Using Gemini with {len(api_keys)} key(s), model: {model}")

        if len(api_keys) > 1:
            return ChatGoogleGenerativeAIWithKeyRotation(
                api_keys=api_keys,
                model_name=model,
                thinking_budget=thinking_budget,
                thinking_level=thinking_level,
                media_resolution=media_resolution
            )
        else:
            is_gemini_3 = "gemini-3" in model.lower()
            model_kwargs = {
                "model": model,
                "google_api_key": api_keys[0],
                "temperature": 0.7,
                "convert_system_message_to_human": True
            }
            if is_gemini_3:
                if thinking_level is not None:
                    model_kwargs["include_thoughts"] = True
                    model_kwargs["thinking_level"] = thinking_level
                if media_resolution and media_resolution != "unspecified":
                    model_kwargs["media_resolution"] = media_resolution
            elif thinking_budget is not None:
                model_kwargs["thinking_budget"] = thinking_budget
            return ChatGoogleGenerativeAI(**model_kwargs)

    elif provider == "openrouter":
        return ChatOpenAI(
            model=model_name or os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-preview-05-20"),
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
        return get_chat_model(provider="gemini", model_name="gemini-flash-latest")
    else:
        return ChatOpenAI(
            model="google/gemini-2.5-flash-preview-05-20",
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
