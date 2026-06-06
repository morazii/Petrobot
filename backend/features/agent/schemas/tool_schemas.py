"""
Tool schema selector.

This selector is used by the agent feature service.
Schema payloads live in this feature's `schemas/` package.
"""

import config.settings as cfg
from backend.features.agent.schemas.flat_schemas import FLAT_TOOL_SCHEMAS
from backend.features.agent.schemas.osdu_schemas import OSDU_TOOL_SCHEMAS

TOOL_SCHEMAS = FLAT_TOOL_SCHEMAS if cfg.DATA_BACKEND == "flat" else OSDU_TOOL_SCHEMAS


