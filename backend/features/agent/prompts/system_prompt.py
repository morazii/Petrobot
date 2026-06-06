"""
System prompt selector.

This selector is used by the agent feature service.
Prompt content lives in this feature's `prompts/` package.
"""

import config.settings as cfg
from backend.features.agent.prompts.flat_prompt import FLAT_SYSTEM_PROMPT
from backend.features.agent.prompts.osdu_prompt import OSDU_SYSTEM_PROMPT

SYSTEM_PROMPT = FLAT_SYSTEM_PROMPT if cfg.DATA_BACKEND == "flat" else OSDU_SYSTEM_PROMPT


