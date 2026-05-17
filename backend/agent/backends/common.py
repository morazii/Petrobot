"""Shared utilities used by both flat and OSDU backends."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

# Operators that can mutate/inspect server internals are blocked.
_BLOCKED_OPERATORS = {
    "$out",
    "$merge",
    "$indexStats",
    "$currentOp",
    "$listLocalSessions",
    "$listSessions",
}

_BLOCKED_UPDATE_OPS = {
    "$set",
    "$unset",
    "$inc",
    "$push",
    "$pull",
    "$addToSet",
    "$rename",
    "$currentDate",
}


def check_safe(obj: Any, context: str = "query") -> None:
    """
    Recursively scan nested query objects for blocked operators.

    Why this exists:
    - LLMs can accidentally generate write stages in an aggregation pipeline.
    - We run the DB tool in read-only mode, so we fail fast if a dangerous
      stage appears anywhere in the payload.
    """
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in _BLOCKED_OPERATORS:
                raise ValueError(
                    f"Blocked pipeline stage '{key}' is not permitted. Only read operations are allowed."
                )
            if context == "update" and key in _BLOCKED_UPDATE_OPS:
                raise ValueError(f"Blocked update operator '{key}' is not permitted.")
            check_safe(val, context)
    elif isinstance(obj, list):
        for item in obj:
            check_safe(item, context)


def sanitize_doc_for_json(doc: dict) -> dict:
    """
    Remove non-JSON-friendly Mongo identifiers.

    Keep grouped '_id' values from aggregation results (e.g., '_id': 'Delta').
    Only remove '_id' when it is a Mongo ObjectId.
    """
    if isinstance(doc.get("_id"), ObjectId):
        doc.pop("_id", None)
    return doc

