"""
config/settings.py
-------------------
Centralized configuration loader for PetroBot.
Reads from .env file and validates all required variables on import.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (works whether running from root or a subdirectory)
_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=_env_path)


def _require(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{var}' is not set.\n"
            f"Copy .env.example to .env and fill in your values."
        )
    return val


def _require_any(*vars_: str) -> str:
    for var in vars_:
        val = os.getenv(var)
        if val:
            return val
    joined = " or ".join(f"'{v}'" for v in vars_)
    raise EnvironmentError(f"Required environment variable {joined} is not set.")


def _normalize_provider(raw: str) -> str:
    aliases = {
        "openai": "openai_compatible",
        "groq": "groq",
        "openrouter": "openrouter",
        "ollama": "openai_compatible",
        "azure": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "google": "google_ai_studio",
        "google_ai_studio": "google_ai_studio",
        "google_ai_studio_native": "google_ai_studio",
        "gemini": "google_ai_studio",
    }
    return aliases.get(raw.strip().lower(), "openai_compatible")


LLM_PROVIDER: str = _normalize_provider(os.getenv("LLM_PROVIDER", "openai_compatible"))

if LLM_PROVIDER == "google_ai_studio":
    # Native Gemini REST endpoint root (model path is added by the agent).
    _raw_base_url = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip().rstrip("/")

    # Normalize common mistakes where users paste a full model endpoint.
    if "/models/" in _raw_base_url and _raw_base_url.endswith(":generateContent"):
        _raw_base_url = _raw_base_url.split("/models/", 1)[0]
    if _raw_base_url.endswith("/generateContent"):
        _raw_base_url = _raw_base_url[: -len("/generateContent")]

    LLM_BASE_URL: str = _raw_base_url
    LLM_API_KEY: str = _require_any("GOOGLE_AI_STUDIO_API_KEY", "LLM_API_KEY")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
else:
    # OpenAI-compatible API root (OpenAI, Groq, OpenRouter, Ollama, etc.)
    _raw_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")

    # Normalize common mistakes where users provide the full endpoint URL.
    # OpenAI-compatible clients expect the API root base, not /chat/completions.
    for suffix in ("/chat/completions", "/completions"):
        if _raw_base_url.endswith(suffix):
            _raw_base_url = _raw_base_url[: -len(suffix)]

    LLM_BASE_URL: str = _raw_base_url
    LLM_API_KEY: str = _require("LLM_API_KEY")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")

# MongoDB Atlas
MONGO_URI: str = _require("MONGO_URI")

# Data backend mode:
# - "flat": use flat CSV-style schema for simpler, more reliable POC querying
# - "osdu": use full nested OSDU schema
DATA_BACKEND: str = os.getenv("DATA_BACKEND", "flat").strip().lower()
if DATA_BACKEND not in {"flat", "osdu"}:
    DATA_BACKEND = "flat"

# Source CSV path used by the flat backend seeding helper.
CSV_DATA_PATH: str = os.getenv("CSV_DATA_PATH", "Data/well-information.csv")

# Agent behavior
MAX_TOOL_ROUNDS: int = int(os.getenv("MAX_TOOL_ROUNDS", "6"))  # max tool calls per user turn
MAX_RESULT_CHARS: int = int(os.getenv("MAX_RESULT_CHARS", "8000"))  # truncate huge tool results
LLM_TIMEOUT_S: int = int(os.getenv("LLM_TIMEOUT_S", "30"))  # fail provider calls fast enough for the UI
