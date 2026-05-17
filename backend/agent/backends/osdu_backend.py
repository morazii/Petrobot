"""OSDU nested-document backend implementation for tool execution."""

from __future__ import annotations

import re

from thefuzz import process as fuzz_process

from backend.agent.backends.common import check_safe, sanitize_doc_for_json
from backend.db.mongo_client import get_wells_collection

_MAX_LIMIT = 500


def _collection():
    return get_wells_collection()


def query_wells(filter: dict, projection: dict | None = None, limit: int = 100) -> list[dict]:
    check_safe(filter)
    if projection:
        check_safe(projection)

    limit = min(int(limit), _MAX_LIMIT)
    cursor = _collection().find(filter, projection or {}).limit(limit)
    return [sanitize_doc_for_json(doc) for doc in cursor]


def aggregate_wells(pipeline: list) -> list[dict]:
    if not isinstance(pipeline, list):
        raise ValueError("pipeline must be a JSON array of stage objects.")
    check_safe(pipeline)
    return [sanitize_doc_for_json(doc) for doc in _collection().aggregate(pipeline)]


def get_well(name: str) -> dict:
    name = str(name).strip()
    collection = _collection()

    doc = collection.find_one({"data.Name": name})
    if doc:
        return sanitize_doc_for_json(doc)

    doc = collection.find_one({"data.Name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
    if doc:
        return sanitize_doc_for_json(doc)

    doc = collection.find_one(
        {"data.NameAliases.AliasName": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
    )
    if doc:
        return sanitize_doc_for_json(doc)

    all_names_cursor = collection.find({}, {"data.Name": 1, "_id": 0})
    all_names = [d["data"]["Name"] for d in all_names_cursor if d.get("data", {}).get("Name")]
    best_match, score = fuzz_process.extractOne(name, all_names)
    if score >= 80:
        doc = collection.find_one({"data.Name": best_match})
        if doc:
            doc = sanitize_doc_for_json(doc)
            doc["_fuzzy_match"] = {
                "original_query": name,
                "matched_name": best_match,
                "score": score,
            }
            return doc

    return {"error": f"Well not found: '{name}'. No close match in the database."}


def _tok(uri: str) -> str:
    if not uri or not uri.startswith("osdu:"):
        return uri or ""
    parts = [p for p in uri.split(":") if p.strip()]
    return parts[-1] if parts else uri


def get_map_data(filter: dict | None = None) -> list[dict]:
    filter = filter or {}
    check_safe(filter)
    projection = {
        "data.Name": 1,
        "data.FieldID": 1,
        "data.OriginalOperator": 1,
        "data.WellStatusID": 1,
        "data.OperatingEnvironmentID": 1,
        "data.SpatialLocation": 1,
    }

    results: list[dict] = []
    for doc in _collection().find(filter, projection):
        data = doc.get("data", {})
        try:
            features = data.get("SpatialLocation", {}).get("Wgs84Coordinates", {}).get("features", [])
            coords = features[0]["geometry"]["coordinates"]
            lon, lat = float(coords[0]), float(coords[1])
        except (IndexError, KeyError, TypeError, ValueError):
            continue

        results.append(
            {
                "name": data.get("Name", ""),
                "field": _tok(data.get("FieldID", "")).title(),
                "operator": data.get("OriginalOperator", ""),
                "status": _tok(data.get("WellStatusID", "")).replace("-", " ").title(),
                "environment": _tok(data.get("OperatingEnvironmentID", "")).title(),
                "lat": lat,
                "lon": lon,
            }
        )
    return results

