"""
LLM tool router.

This module is the single place where tool calls from the model are:
1) decoded from raw arguments,
2) routed to the active backend (flat or osdu),
3) normalized into stable JSON-friendly error/result payloads.
"""

from __future__ import annotations

import json
from typing import Any

import config.settings as cfg
from backend.agent.backends import flat_backend, osdu_backend

ACTIVE_BACKEND = flat_backend if cfg.DATA_BACKEND == "flat" else osdu_backend


def query_wells(filter: dict, projection: dict | None = None, limit: int = 100) -> list[dict]:
    try:
        return ACTIVE_BACKEND.query_wells(filter=filter, projection=projection, limit=limit)
    except ValueError as exc:
        return [{"error": str(exc)}]
    except Exception as exc:
        return [{"error": f"query_wells failed: {exc}"}]


def aggregate_wells(pipeline: list) -> list[dict]:
    try:
        return ACTIVE_BACKEND.aggregate_wells(pipeline=pipeline)
    except ValueError as exc:
        return [{"error": str(exc)}]
    except Exception as exc:
        return [{"error": f"aggregate_wells failed: {exc}. Check pipeline syntax."}]


def get_well(name: str) -> dict:
    try:
        return ACTIVE_BACKEND.get_well(name=name)
    except Exception as exc:
        return {"error": f"get_well failed: {exc}"}


def get_map_data(filter: dict | None = None) -> list[dict]:
    try:
        return ACTIVE_BACKEND.get_map_data(filter=filter)
    except ValueError as exc:
        return [{"error": str(exc)}]
    except Exception as exc:
        return [{"error": f"get_map_data failed: {exc}"}]


TOOL_FUNCTIONS = {
    "query_wells": query_wells,
    "aggregate_wells": aggregate_wells,
    "get_well": get_well,
    "get_map_data": get_map_data,
}


def dispatch_tool(tool_name: str, tool_args: dict | str) -> Any:
    """
    Dispatch one model tool call.

    Tool-call lifecycle in this project:
    - `agent.py` receives `tool_calls` from the LLM response.
    - each call is sent here with `tool_name` + `tool_args`.
    - we parse stringified JSON args (provider quirk tolerance).
    - we execute the mapped function on the currently active backend.
    - return value is always JSON-serializable so it can be sent back to the model.
    """
    fn = TOOL_FUNCTIONS.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: '{tool_name}'. Valid tools: {list(TOOL_FUNCTIONS)}"}

    # Some providers return function arguments as a JSON string.
    if isinstance(tool_args, str):
        try:
            tool_args = json.loads(tool_args)
        except json.JSONDecodeError as exc:
            return {"error": f"Could not parse tool arguments as JSON: {exc}"}

    return fn(**tool_args)

