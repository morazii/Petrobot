"""
config/settings.py
-------------------
Centralised configuration loader for PetroBot.
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


# LLM — provider-agnostic (OpenAI, Azure, Gemini proxy, Ollama, etc.)
_raw_base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
# Normalize common mistakes where users provide the full endpoint URL.
# OpenAI-compatible clients expect the API root base, not /chat/completions.
for suffix in ("/chat/completions", "/completions"):
    if _raw_base_url.endswith(suffix):
        _raw_base_url = _raw_base_url[: -len(suffix)]
LLM_BASE_URL: str = _raw_base_url
LLM_API_KEY: str  = _require("LLM_API_KEY")
LLM_MODEL: str    = os.getenv("LLM_MODEL", "gpt-4o")

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

# Agent behaviour
MAX_TOOL_ROUNDS: int = int(os.getenv("MAX_TOOL_ROUNDS", "6"))  # max tool calls per user turn
MAX_RESULT_CHARS: int = int(os.getenv("MAX_RESULT_CHARS", "8000"))  # truncate huge tool results
