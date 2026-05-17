"""
Tool schema selector.

This file remains the stable import path used by `agent.py`.
Schema payloads now live in `backend/agent/schemas/`.
"""

import config.settings as cfg
from backend.agent.schemas.flat_schemas import FLAT_TOOL_SCHEMAS
from backend.agent.schemas.osdu_schemas import OSDU_TOOL_SCHEMAS

TOOL_SCHEMAS = FLAT_TOOL_SCHEMAS if cfg.DATA_BACKEND == "flat" else OSDU_TOOL_SCHEMAS

