"""
Model provider abstraction for Gemini (dev) and OpenRouter (production).

DOCUMENTATION:
- ChatGoogleGenerativeAI: https://python.langchain.com/docs/integrations/chat/google_generative_ai
- ChatOpenAI with OpenRouter: https://openrouter.ai/docs

USAGE:
    model = get_chat_model()  # Uses LLM_PROVIDER env var
    model_with_tools = model.bind_tools(tools)
"""
import os
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


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
        GOOGLE_API_KEY: Required for Gemini
        OPENROUTER_API_KEY: Required for OpenRouter
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=model_name or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
            temperature=0.7,
            convert_system_message_to_human=True  # Gemini quirk
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
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",  # Vision + Audio capable
            google_api_key=os.environ.get("GOOGLE_API_KEY"),
        )
    else:
        return ChatOpenAI(
            model="google/gemini-2.0-flash-exp:free",  # Vision capable via OpenRouter
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
