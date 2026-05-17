"""Flat CSV-style backend implementation for tool execution."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pymongo import ASCENDING
from thefuzz import process as fuzz_process

import config.settings as cfg
from backend.agent.backends.common import check_safe, sanitize_doc_for_json
from backend.db.mongo_client import get_wells_flat_collection

_flat_ready = False
_MAX_LIMIT = 1000


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ensure_flat_collection_ready() -> None:
    """
    Lazy-load flat CSV rows into Mongo `wells_flat` when first needed.

    This gives us:
    - fast in-memory-like querying through Mongo indexes
    - zero manual seed step for POC users
    """
    global _flat_ready
    if _flat_ready:
        return

    collection = get_wells_flat_collection()
    if collection.estimated_document_count() > 0:
        _flat_ready = True
        return

    csv_path = _project_root() / cfg.CSV_DATA_PATH
    if not csv_path.exists():
        raise FileNotFoundError(f"Flat CSV data file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    records = df.where(pd.notna(df), None).to_dict(orient="records")

    docs: list[dict] = []
    for idx, rec in enumerate(records):
        doc = dict(rec)
        doc["_id"] = rec.get("wellbore_id") or rec.get("well_id") or f"row-{idx}"
        docs.append(doc)

    if docs:
        collection.insert_many(docs, ordered=False)

    collection.create_index([("well_name", ASCENDING)], name="idx_well_name")
    collection.create_index([("field_name", ASCENDING)], name="idx_field_name")
    collection.create_index([("operator", ASCENDING)], name="idx_operator")
    collection.create_index([("current_status", ASCENDING)], name="idx_current_status")
    collection.create_index([("spud_date", ASCENDING)], name="idx_spud_date")
    _flat_ready = True


def _collection():
    ensure_flat_collection_ready()
    return get_wells_flat_collection()


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

    doc = collection.find_one({"well_name": name})
    if doc:
        return sanitize_doc_for_json(doc)

    doc = collection.find_one({"well_name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
    if doc:
        return sanitize_doc_for_json(doc)

    doc = collection.find_one({"well_id": {"$regex": f"^{re.escape(name)}$", "$options": "i"}})
    if doc:
        return sanitize_doc_for_json(doc)

    all_names = [d.get("well_name") for d in collection.find({}, {"well_name": 1, "_id": 0}) if d.get("well_name")]
    if not all_names:
        return {"error": "No wells available in flat collection."}

    best_match, score = fuzz_process.extractOne(name, all_names)
    if score >= 80:
        doc = collection.find_one({"well_name": best_match})
        if doc:
            doc = sanitize_doc_for_json(doc)
            doc["_fuzzy_match"] = {
                "original_query": name,
                "matched_name": best_match,
                "score": score,
            }
            return doc

    return {"error": f"Well not found: '{name}'. No close match in the database."}


def get_map_data(filter: dict | None = None) -> list[dict]:
    filter = filter or {}
    check_safe(filter)
    projection = {
        "well_name": 1,
        "field_name": 1,
        "operator": 1,
        "current_status": 1,
        "sector": 1,
        "latitude": 1,
        "longitude": 1,
        "surface_lat": 1,
        "surface_lon": 1,
    }

    results: list[dict] = []
    for doc in _collection().find(filter, projection):
        lat = doc.get("latitude") if doc.get("latitude") is not None else doc.get("surface_lat")
        lon = doc.get("longitude") if doc.get("longitude") is not None else doc.get("surface_lon")
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            continue

        results.append(
            {
                "name": doc.get("well_name", ""),
                "field": doc.get("field_name", ""),
                "operator": doc.get("operator", ""),
                "status": doc.get("current_status", ""),
                "environment": doc.get("sector", ""),
                "lat": lat,
                "lon": lon,
            }
        )
    return results

