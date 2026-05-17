"""
Compatibility facade for agent tool execution.

Why this file still exists:
- Existing code imports from `backend.agent.tools`.
- We moved implementation into structured backend modules for readability.
- Keeping this facade avoids breaking imports while exposing the same API.
"""

from backend.agent.backends.router import (
    aggregate_wells,
    dispatch_tool,
    get_map_data,
    get_well,
    query_wells,
)

__all__ = [
    "query_wells",
    "aggregate_wells",
    "get_well",
    "get_map_data",
    "dispatch_tool",
]

