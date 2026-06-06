"""Deterministic KG grounding helpers for entity resolution and tool constraints."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from thefuzz import fuzz

import config.settings as cfg

_WELL_TOKEN_RE = re.compile(r"([a-zA-Z]+)[\s\-_]?(\d{1,3})([a-zA-Z]?)")
_WELL_NAME_RE = re.compile(r"^\s*([a-zA-Z]+)[\s\-_]?0*(\d{1,3})\s*$")
_MAX_GROUNDED_PER_TYPE = 2
_MIN_CONFIDENCE_STRONG = 0.80
_STAGE5_BASE_ALLOWED_COLUMNS = {
    "well_name",
    "field_name",
    "operator",
    "current_status",
    "spud_date",
    "status_date",
    "drillers_td_m",
    "drillers_tvs_m",
    "logger_tvd_m",
    "latitude",
    "longitude",
    "surface_lat",
    "surface_lon",
    "well_objective",
    "bore_type",
}
_STAGE5_ANALYTICS_KEYWORDS = {
    "map": {"latitude", "longitude", "surface_lat", "surface_lon"},
    "deep": {"drillers_td_m", "logger_tvd_m", "drillers_tvs_m"},
    "spud": {"spud_date"},
    "status": {"current_status"},
    "operator": {"operator"},
}


@dataclass(frozen=True)
class GroundedEntity:
    entity_type: str
    canonical_id: str
    canonical_value: str
    confidence: float
    source: str


@dataclass(frozen=True)
class GroundingResult:
    entities: list[GroundedEntity]
    ambiguous: bool
    notes: list[str]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _norm_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _norm_compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _parse_well_components(name: str) -> tuple[str | None, int | None]:
    m = _WELL_NAME_RE.match(str(name or ""))
    if not m:
        return None, None
    prefix = m.group(1).lower()
    number = int(m.group(2))
    return prefix, number


@lru_cache(maxsize=1)
def _entity_catalog() -> dict[str, Any]:
    csv_path = _project_root() / cfg.CSV_DATA_PATH
    df = pd.read_csv(csv_path)

    fields = sorted(v for v in df["field_name"].dropna().astype(str).str.strip().unique() if v)
    operators = sorted(v for v in df["operator"].dropna().astype(str).str.strip().unique() if v)
    statuses = sorted(v for v in df["current_status"].dropna().astype(str).str.strip().unique() if v)
    wells = sorted(v for v in df["well_name"].dropna().astype(str).str.strip().unique() if v)
    flat_columns = [str(c) for c in df.columns]

    well_rows: list[dict[str, Any]] = []
    for well in wells:
        prefix, number = _parse_well_components(well)
        well_rows.append(
            {
                "name": well,
                "name_norm": _norm_compact(well),
                "prefix": prefix,
                "number": number,
            }
        )

    return {
        "fields": fields,
        "operators": operators,
        "statuses": statuses,
        "wells": wells,
        "well_rows": well_rows,
        "flat_columns": set(flat_columns),
    }


def get_flat_schema_columns() -> set[str]:
    return set(_entity_catalog()["flat_columns"])


def _contains_matches(query: str, candidates: list[str], limit: int = _MAX_GROUNDED_PER_TYPE) -> list[str]:
    q = _norm_text(query)
    hits = [candidate for candidate in candidates if _norm_text(candidate) and _norm_text(candidate) in q]
    return hits[:limit]


def _extract_well_mentions(query: str) -> list[tuple[str, int | None, str]]:
    mentions: list[tuple[str, int | None, str]] = []
    for m in _WELL_TOKEN_RE.finditer(query or ""):
        raw = m.group(0)
        prefix = re.sub(r"[^a-z]", "", m.group(1).lower())
        digits = m.group(2) or ""
        suffix = re.sub(r"[^a-z]", "", (m.group(3) or "").lower())
        if not prefix:
            continue
        number = int(digits) if digits.isdigit() else None
        mentions.append((prefix, number, suffix))
    return mentions


def _score_well_candidate(
    mention_prefix: str,
    mention_number: int | None,
    mention_suffix: str,
    well_prefix: str | None,
    well_number: int | None,
    well_name_norm: str,
) -> float:
    if not well_prefix:
        return 0.0

    prefix_score = float(fuzz.ratio(mention_prefix, well_prefix))
    full_token = mention_prefix if mention_number is None else f"{mention_prefix}{mention_number}"
    full_score = float(fuzz.partial_ratio(full_token, well_name_norm))

    number_score = 0.0
    if mention_number is None or well_number is None:
        number_score = 35.0
    else:
        if mention_suffix and mention_number < 10:
            # Handle wildcard-like typos such as "4x" by matching the tens bucket.
            if 10 <= well_number <= 99 and (well_number // 10) == mention_number:
                # Prefer entries closer to the middle of the bucket to avoid edge bias.
                number_score = 72.0 - abs(well_number - (mention_number * 10 + 5))
            else:
                number_score = 0.0
        elif mention_number == well_number:
            number_score = 100.0
        else:
            delta = abs(mention_number - well_number)
            if delta == 1:
                number_score = 70.0
            elif delta == 2:
                number_score = 55.0
            elif delta <= 5:
                number_score = 35.0
            else:
                number_score = 0.0

    composite = (0.55 * number_score) + (0.30 * prefix_score) + (0.15 * full_score)
    return max(0.0, min(100.0, composite))


def _resolve_well_hits(query: str, max_hits: int = 1) -> tuple[list[tuple[str, float, str]], bool]:
    catalog = _entity_catalog()
    mentions = _extract_well_mentions(query)
    rows = catalog["well_rows"]
    candidates: list[tuple[str, float, str]] = []
    ambiguous = False

    for mention_prefix, mention_number, mention_suffix in mentions:
        scored: list[tuple[str, float]] = []
        for row in rows:
            score = _score_well_candidate(
                mention_prefix=mention_prefix,
                mention_number=mention_number,
                mention_suffix=mention_suffix,
                well_prefix=row["prefix"],
                well_number=row["number"],
                well_name_norm=row["name_norm"],
            )
            if score >= 72.0:
                scored.append((row["name"], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        if scored:
            top = scored[0]
            candidates.append((top[0], top[1] / 100.0, "well_pattern_match"))
            if len(scored) > 1 and (top[1] - scored[1][1]) <= 1.5:
                ambiguous = True

    if candidates:
        dedup: dict[str, tuple[str, float, str]] = {}
        for name, conf, source in candidates:
            prev = dedup.get(name)
            if prev is None or conf > prev[1]:
                dedup[name] = (name, conf, source)
        merged = sorted(dedup.values(), key=lambda x: x[1], reverse=True)
        return merged[:max_hits], ambiguous

    # Fallback fuzzy only when pattern extraction failed.
    fuzzy_pick = catalog["wells"]
    if not fuzzy_pick:
        return [], ambiguous
    from thefuzz import process as fuzz_process

    best = fuzz_process.extractOne(query, fuzzy_pick)
    if not best:
        return [], ambiguous
    best_name, best_score = best
    if best_score < 88:
        return [], ambiguous
    return [(best_name, best_score / 100.0, "well_fuzzy_fallback")], ambiguous


def resolve_query_entities(query: str, enabled: bool = True) -> GroundingResult:
    """
    Resolve mentions in user query to canonical entities with confidence.

    Returns empty result when disabled or when backend is not flat.
    """
    if not enabled or cfg.DATA_BACKEND != "flat":
        return GroundingResult(entities=[], ambiguous=False, notes=["kg_disabled_or_unsupported"])

    query = (query or "").strip()
    if not query:
        return GroundingResult(entities=[], ambiguous=False, notes=["empty_query"])

    catalog = _entity_catalog()
    entities: list[GroundedEntity] = []
    notes: list[str] = []
    ambiguous = False

    for field_name in _contains_matches(query, catalog["fields"]):
        entities.append(
            GroundedEntity(
                entity_type="field",
                canonical_id=f"field:{field_name}",
                canonical_value=field_name,
                confidence=0.99,
                source="substring_match",
            )
        )

    for operator in _contains_matches(query, catalog["operators"]):
        entities.append(
            GroundedEntity(
                entity_type="operator",
                canonical_id=f"operator:{operator}",
                canonical_value=operator,
                confidence=0.99,
                source="substring_match",
            )
        )

    for status in _contains_matches(query, catalog["statuses"]):
        entities.append(
            GroundedEntity(
                entity_type="status",
                canonical_id=f"status:{status}",
                canonical_value=status,
                confidence=0.99,
                source="substring_match",
            )
        )

    well_hits, well_ambiguous = _resolve_well_hits(query, max_hits=1)
    ambiguous = ambiguous or well_ambiguous
    for well_name, confidence, source in well_hits:
        entities.append(
            GroundedEntity(
                entity_type="well",
                canonical_id=f"well:{well_name}",
                canonical_value=well_name,
                confidence=confidence,
                source=source,
            )
        )

    # Keep strongest result per canonical id.
    dedup: dict[str, GroundedEntity] = {}
    for entity in entities:
        prev = dedup.get(entity.canonical_id)
        if prev is None or entity.confidence > prev.confidence:
            dedup[entity.canonical_id] = entity

    ranked = sorted(dedup.values(), key=lambda e: e.confidence, reverse=True)
    if ambiguous:
        notes.append("multiple_close_entity_candidates_detected")

    return GroundingResult(entities=ranked[:12], ambiguous=ambiguous, notes=notes)


def grounding_to_prompt_text(grounding: GroundingResult) -> str:
    """Render resolved entities in a compact planner-facing format."""
    if not grounding.entities:
        return "Grounded entities: none"

    lines = ["Grounded entities (canonical, confidence):"]
    for entity in grounding.entities[:8]:
        lines.append(
            f"- {entity.entity_type}: {entity.canonical_value} "
            f"(id={entity.canonical_id}, confidence={entity.confidence:.2f})"
        )
    if grounding.ambiguous:
        lines.append("- ambiguity: multiple close candidates found; avoid assumptions and verify via tools.")
    return "\n".join(lines)


def schema_scope_from_query(query: str, grounding: GroundingResult) -> dict[str, Any]:
    """
    Stage-1/4 schema scope for planner: domain narrowing + path constraints.

    For this project, the domain is a single table (`wells_flat`) in flat mode.
    We still narrow allowed columns based on query intents and grounded entities.
    """
    all_columns = get_flat_schema_columns()
    allowed_columns = set(_STAGE5_BASE_ALLOWED_COLUMNS).intersection(all_columns)
    q = _norm_text(query)

    for keyword, cols in _STAGE5_ANALYTICS_KEYWORDS.items():
        if keyword in q:
            allowed_columns.update(col for col in cols if col in all_columns)

    grounded_types = {e.entity_type for e in grounding.entities}
    if "well" in grounded_types and "well_name" in all_columns:
        allowed_columns.add("well_name")
    if "field" in grounded_types and "field_name" in all_columns:
        allowed_columns.add("field_name")
    if "operator" in grounded_types and "operator" in all_columns:
        allowed_columns.add("operator")
    if "status" in grounded_types and "current_status" in all_columns:
        allowed_columns.add("current_status")

    allowed_filters = [c for c in ["well_name", "field_name", "operator", "current_status", "spud_date"] if c in all_columns]
    relation_paths = [
        "wells_flat.well_name -> wells_flat.field_name",
        "wells_flat.well_name -> wells_flat.operator",
        "wells_flat.well_name -> wells_flat.current_status",
    ]

    return {
        "domain": "flat_well_analytics",
        "allowed_tables": ["wells_flat"],
        "allowed_columns": sorted(allowed_columns),
        "allowed_filters": allowed_filters,
        "relation_paths": relation_paths,
    }


def _stage2_candidate_list_for_mentions(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Expose deterministic entity candidates for audit/debug (Stage 2)."""
    catalog = _entity_catalog()
    out: list[dict[str, Any]] = []
    mentions = _extract_well_mentions(query)
    rows = catalog["well_rows"]

    for prefix, number, suffix in mentions:
        mention = f"{prefix}-{number if number is not None else ''}{suffix}".strip("-")
        scored: list[tuple[str, float]] = []
        for row in rows:
            score = _score_well_candidate(
                mention_prefix=prefix,
                mention_number=number,
                mention_suffix=suffix,
                well_prefix=row["prefix"],
                well_number=row["number"],
                well_name_norm=row["name_norm"],
            )
            if score >= 60.0:
                scored.append((row["name"], score))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = [{"candidate": name, "score": round(score / 100.0, 3)} for name, score in scored[:limit]]
        out.append({"mention": mention, "entity_type": "well", "candidates": top})
    return out


def planner_packet_from_grounding(query: str, grounding: GroundingResult) -> dict[str, Any]:
    """
    Stage-5 packet passed to the LLM so planning is anchored to canonical entities.
    """
    schema_scope = schema_scope_from_query(query, grounding)
    resolved = [
        {
            "entity_type": e.entity_type,
            "canonical_id": e.canonical_id,
            "canonical_value": e.canonical_value,
            "confidence": round(e.confidence, 3),
            "source": e.source,
        }
        for e in grounding.entities
    ]

    unresolved_mentions: list[str] = []
    mentions = _extract_well_mentions(query)
    has_strong_well = any(e.entity_type == "well" and e.confidence >= _MIN_CONFIDENCE_STRONG for e in grounding.entities)
    if mentions and not has_strong_well:
        unresolved_mentions = [f"{p}-{n if n is not None else ''}{s}".strip("-") for p, n, s in mentions]

    packet = {
        "user_query": query,
        "stage_2_candidates": _stage2_candidate_list_for_mentions(query),
        "resolved_entities": resolved,
        "unresolved_mentions": unresolved_mentions,
        "schema_scope": schema_scope,
        "constraints": {
            "must_use_canonical_entities": True,
            "must_stay_within_schema_scope": True,
            "read_only": True,
        },
        "planner_instruction": (
            "Build tool calls using schema_scope and resolved_entities only. "
            "If unresolved_mentions is not empty, avoid guessing and ask for clarification."
        ),
    }
    return packet


def planner_packet_to_prompt_text(packet: dict[str, Any]) -> str:
    return "Grounding control packet:\n" + json.dumps(packet, ensure_ascii=False, indent=2)


def _strongest_entity(grounding: GroundingResult, entity_type: str) -> GroundedEntity | None:
    picks = [e for e in grounding.entities if e.entity_type == entity_type and e.confidence >= _MIN_CONFIDENCE_STRONG]
    if not picks:
        return None
    picks.sort(key=lambda e: e.confidence, reverse=True)
    return picks[0]


def apply_grounding_to_tool_args(tool_name: str, tool_args: dict, grounding: GroundingResult | None) -> tuple[dict, list[str]]:
    """
    Normalize tool args with high-confidence grounded entities.

    Returns transformed args and notes describing any applied grounding.
    """
    if not grounding or not grounding.entities:
        return tool_args, []

    notes: list[str] = []
    args = dict(tool_args or {})

    well = _strongest_entity(grounding, "well")
    field = _strongest_entity(grounding, "field")
    operator = _strongest_entity(grounding, "operator")
    status = _strongest_entity(grounding, "status")

    if tool_name == "get_well":
        if well and args.get("name") != well.canonical_value:
            args["name"] = well.canonical_value
            notes.append(f"normalized:get_well.name->{well.canonical_value}")
        return args, notes

    if tool_name in {"query_wells", "get_map_data"}:
        flt = args.get("filter")
        if not isinstance(flt, dict):
            flt = {}
        if well and "well_name" not in flt:
            flt["well_name"] = well.canonical_value
            notes.append(f"normalized:filter.well_name->{well.canonical_value}")
        if field and "field_name" not in flt:
            flt["field_name"] = field.canonical_value
            notes.append(f"normalized:filter.field_name->{field.canonical_value}")
        if operator and "operator" not in flt:
            flt["operator"] = operator.canonical_value
            notes.append(f"normalized:filter.operator->{operator.canonical_value}")
        if status and "current_status" not in flt:
            flt["current_status"] = status.canonical_value
            notes.append(f"normalized:filter.current_status->{status.canonical_value}")
        args["filter"] = flt
        return args, notes

    if tool_name == "aggregate_wells":
        pipeline = args.get("pipeline")
        if not isinstance(pipeline, list):
            return args, notes
        match_filter: dict[str, Any] = {}
        if well:
            match_filter["well_name"] = well.canonical_value
        if field:
            match_filter["field_name"] = field.canonical_value
        if operator:
            match_filter["operator"] = operator.canonical_value
        if status:
            match_filter["current_status"] = status.canonical_value

        if match_filter:
            if pipeline and isinstance(pipeline[0], dict) and "$match" in pipeline[0] and isinstance(pipeline[0]["$match"], dict):
                for key, value in match_filter.items():
                    pipeline[0]["$match"].setdefault(key, value)
            else:
                pipeline = [{"$match": match_filter}] + pipeline
            args["pipeline"] = pipeline
            notes.append("normalized:aggregate.$match.injected")
        return args, notes

    return args, notes


def _validate_filter_fields(filter_doc: Any, allowed_fields: set[str], strict: bool = True) -> None:
    if isinstance(filter_doc, dict):
        for key, value in filter_doc.items():
            if key.startswith("$"):
                _validate_filter_fields(value, allowed_fields, strict=strict)
                continue
            root = key.split(".", 1)[0]
            if strict and root not in allowed_fields:
                raise ValueError(
                    f"Schema validation failed: unknown field '{key}' in filter. "
                    "Use canonical flat schema fields only."
                )
            _validate_filter_fields(value, allowed_fields, strict=strict)
    elif isinstance(filter_doc, list):
        for item in filter_doc:
            _validate_filter_fields(item, allowed_fields, strict=strict)


def _validate_pipeline_field_refs(pipeline: list[Any], allowed_fields: set[str]) -> None:
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                visit(k)
                visit(v)
        elif isinstance(node, list):
            for x in node:
                visit(x)
        elif isinstance(node, str) and node.startswith("$") and not node.startswith("$$"):
            ref = node[1:].split(".", 1)[0]
            if ref and ref not in allowed_fields:
                # Allow synthetic accumulator aliases in later pipeline stages.
                if ref not in {"_id", "count", "avg_td", "sum", "total"}:
                    raise ValueError(
                        f"Schema validation failed: pipeline references unknown field '${ref}'."
                    )

    for stage in pipeline:
        if not isinstance(stage, dict):
            raise ValueError("Schema validation failed: each pipeline stage must be an object.")
        if len(stage) != 1:
            raise ValueError("Schema validation failed: each pipeline stage must have exactly one operator key.")
        op, body = next(iter(stage.items()))
        if not str(op).startswith("$"):
            raise ValueError("Schema validation failed: pipeline stage operator must start with '$'.")
        if op == "$match":
            _validate_filter_fields(body, allowed_fields, strict=False)
        visit(body)


def validate_tool_args(tool_name: str, tool_args: dict) -> None:
    """
    Validate tool payload against flat schema constraints.

    This prevents invalid field drift before DB execution.
    """
    if cfg.DATA_BACKEND != "flat":
        return

    allowed_fields = _entity_catalog()["flat_columns"]
    if tool_name == "get_well":
        name = str(tool_args.get("name", "")).strip()
        if not name:
            raise ValueError("Schema validation failed: get_well requires a non-empty 'name'.")
        return

    if tool_name in {"query_wells", "get_map_data"}:
        flt = tool_args.get("filter", {})
        if flt is None:
            return
        if not isinstance(flt, dict):
            raise ValueError("Schema validation failed: 'filter' must be an object.")
        _validate_filter_fields(flt, allowed_fields, strict=True)
        return

    if tool_name == "aggregate_wells":
        pipeline = tool_args.get("pipeline")
        if not isinstance(pipeline, list):
            raise ValueError("Schema validation failed: 'pipeline' must be an array.")
        _validate_pipeline_field_refs(pipeline, allowed_fields)
        return


def try_repair_tool_args(tool_name: str, tool_args: dict, validation_error: str) -> tuple[dict, str] | None:
    """
    Stage-6 execution-guided repair attempt for common schema errors.

    Returns (repaired_args, note) when a deterministic repair is applied.
    """
    if cfg.DATA_BACKEND != "flat":
        return None

    msg = str(validation_error)
    m = re.search(r"unknown field '([^']+)'", msg)
    if not m:
        return None

    bad_key = m.group(1)
    root_bad = bad_key.split(".", 1)[0]
    root_bad_clean = root_bad.lstrip("$")
    allowed = sorted(get_flat_schema_columns())
    candidates = [(field_name, fuzz.ratio(root_bad_clean.lower(), field_name.lower())) for field_name in allowed]
    candidates.sort(key=lambda x: x[1], reverse=True)
    if not candidates or candidates[0][1] < 88:
        return None
    replacement = candidates[0][0]

    repaired = json.loads(json.dumps(tool_args, ensure_ascii=False))
    bad_ref_exact = f"${root_bad_clean}"
    bad_ref_prefix = bad_ref_exact + "."
    replacement_ref = f"${replacement}"
    replacement_bad_key = replacement if bad_key == root_bad else bad_key.replace(root_bad, replacement, 1)

    def rewrite_keys(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for k, v in obj.items():
                nk = k
                if k == bad_key or k == root_bad or k == root_bad_clean:
                    nk = replacement_bad_key
                out[nk] = rewrite_keys(v)
            return out
        if isinstance(obj, list):
            return [rewrite_keys(x) for x in obj]
        if isinstance(obj, str):
            if obj == bad_ref_exact:
                return replacement_ref
            if obj.startswith(bad_ref_prefix):
                return replacement_ref + obj[len(bad_ref_exact) :]
        return obj

    repaired = rewrite_keys(repaired)
    note = f"execution_guided_repair: field '{bad_key}' -> '{replacement}'"
    return repaired, note
