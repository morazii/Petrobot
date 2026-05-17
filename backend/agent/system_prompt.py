"""
System prompt selector.

This file intentionally stays as the import path used by `agent.py`.
Prompt content now lives in dedicated modules under `backend/agent/prompts/`.
"""

import config.settings as cfg
from backend.agent.prompts.flat_prompt import FLAT_SYSTEM_PROMPT
from backend.agent.prompts.osdu_prompt import OSDU_SYSTEM_PROMPT

SYSTEM_PROMPT = FLAT_SYSTEM_PROMPT if cfg.DATA_BACKEND == "flat" else OSDU_SYSTEM_PROMPT

