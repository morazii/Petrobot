"""
Lightweight knowledge-graph context generator.

This module builds a cached graph from the flat CSV data and returns concise
relationship hints for the current user query. The hints are advisory only:
the agent still verifies answers using tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import networkx as nx
import pandas as pd

import config.settings as cfg
from backend.features.knowledge_graph.grounding import GroundingResult, resolve_query_entities


@dataclass(frozen=True)
class KGContext:
    text: str
    matched_entities: int
    entities: list[str]


def get_ontology_definition() -> list[dict]:
    """Return the ontology entities and relationship labels used in KG mode."""
    return [
        {
            "entity": "well",
            "description": "Individual well identity node",
            "key_fields": "well_name, well_id, wellbore_id",
            "relationships": "WELL_IN_FIELD, WELL_OPERATED_BY, WELL_STATUS, WELL_OBJECTIVE, WELL_ON_PLATFORM",
        },
        {
            "entity": "field",
            "description": "Field membership taxonomy node",
            "key_fields": "field_name",
            "relationships": "WELL_IN_FIELD",
        },
        {
            "entity": "operator",
            "description": "Operating company node",
            "key_fields": "operator",
            "relationships": "WELL_OPERATED_BY",
        },
        {
            "entity": "status",
            "description": "Current lifecycle state node",
            "key_fields": "current_status",
            "relationships": "WELL_STATUS",
        },
        {
            "entity": "objective",
            "description": "Well objective/purpose node",
            "key_fields": "well_objective",
            "relationships": "WELL_OBJECTIVE",
        },
        {
            "entity": "platform",
            "description": "Platform or facility node",
            "key_fields": "platform",
            "relationships": "WELL_ON_PLATFORM",
        },
    ]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _build_flat_graph() -> tuple[nx.Graph, dict[str, list[str]], dict[str, int]]:
    """
    Build graph + indexes from flat CSV once per process.

    Nodes:
    - well, field, operator, status, objective, platform
    Edges:
    - WELL_IN_FIELD, WELL_OPERATED_BY, WELL_STATUS, WELL_OBJECTIVE, WELL_ON_PLATFORM
    """
    csv_path = _project_root() / cfg.CSV_DATA_PATH
    df = pd.read_csv(csv_path)

    graph = nx.Graph()
    wells: list[str] = []
    fields: set[str] = set()
    operators: set[str] = set()
    statuses: set[str] = set()

    for row in df.itertuples(index=False):
        well_name = str(getattr(row, "well_name", "") or "").strip()
        field_name = str(getattr(row, "field_name", "") or "").strip()
        operator = str(getattr(row, "operator", "") or "").strip()
        status = str(getattr(row, "current_status", "") or "").strip()
        objective = str(getattr(row, "well_objective", "") or "").strip()
        platform = str(getattr(row, "platform", "") or "").strip()

        if not well_name:
            continue

        well_node = f"well:{well_name}"
        graph.add_node(well_node, kind="well", label=well_name)
        wells.append(well_name)

        if field_name:
            field_node = f"field:{field_name}"
            graph.add_node(field_node, kind="field", label=field_name)
            graph.add_edge(well_node, field_node, rel="WELL_IN_FIELD")
            fields.add(field_name)

        if operator:
            operator_node = f"operator:{operator}"
            graph.add_node(operator_node, kind="operator", label=operator)
            graph.add_edge(well_node, operator_node, rel="WELL_OPERATED_BY")
            operators.add(operator)

        if status:
            status_node = f"status:{status}"
            graph.add_node(status_node, kind="status", label=status)
            graph.add_edge(well_node, status_node, rel="WELL_STATUS")
            statuses.add(status)

        if objective:
            objective_node = f"objective:{objective}"
            graph.add_node(objective_node, kind="objective", label=objective)
            graph.add_edge(well_node, objective_node, rel="WELL_OBJECTIVE")

        if platform:
            platform_node = f"platform:{platform}"
            graph.add_node(platform_node, kind="platform", label=platform)
            graph.add_edge(well_node, platform_node, rel="WELL_ON_PLATFORM")

    indexes = {
        "wells": wells,
        "fields": sorted(fields),
        "operators": sorted(operators),
        "statuses": sorted(statuses),
    }
    stats = {"wells": len(wells), "fields": len(fields), "operators": len(operators), "statuses": len(statuses)}
    return graph, indexes, stats


def get_kg_snapshot(max_wells: int = 180) -> dict:
    """
    Return a sampled graph snapshot suitable for GUI visualization.

    We cap the number of well nodes to keep rendering smooth in Streamlit while
    still showing ontology structure around those wells.
    """
    if cfg.DATA_BACKEND != "flat":
        return {
            "supported": False,
            "reason": "Graph visualization currently targets flat backend mode.",
            "graph": nx.Graph(),
            "stats": {},
            "edge_counts": {},
        }

    graph, _, stats = _build_flat_graph()
    max_wells = max(20, int(max_wells))

    well_nodes = [n for n, data in graph.nodes(data=True) if data.get("kind") == "well"]
    well_nodes = sorted(well_nodes, key=lambda n: graph.nodes[n].get("label", n))
    selected_wells = well_nodes[:max_wells]

    included_nodes = set(selected_wells)
    for well_node in selected_wells:
        included_nodes.update(graph.neighbors(well_node))

    sampled_graph = graph.subgraph(included_nodes).copy()
    edge_counts: dict[str, int] = {}
    for _, _, data in sampled_graph.edges(data=True):
        rel = str(data.get("rel", "UNKNOWN"))
        edge_counts[rel] = edge_counts.get(rel, 0) + 1

    return {
        "supported": True,
        "graph": sampled_graph,
        "stats": stats,
        "edge_counts": edge_counts,
    }


def generate_kg_context(query: str, enabled: bool) -> KGContext | None:
    """
    Return compact KG hints for current query.

    Returns None when disabled or when backend is not flat.
    """
    if not enabled or cfg.DATA_BACKEND != "flat":
        return None

    query = (query or "").strip()
    if not query:
        return None

    graph, _, stats = _build_flat_graph()
    grounding: GroundingResult = resolve_query_entities(query, enabled=enabled)

    lines: list[str] = [
        "Knowledge graph hints (verify with tools):",
        f"- graph_size: wells={stats['wells']}, fields={stats['fields']}, operators={stats['operators']}, statuses={stats['statuses']}",
    ]
    entity_hits: list[str] = []

    matched = 0
    for entity in grounding.entities:
        etype = entity.entity_type
        value = entity.canonical_value
        canonical_id = entity.canonical_id
        confidence = entity.confidence

        if etype == "field":
            field_node = canonical_id
            if field_node not in graph:
                continue
            well_count = sum(1 for n in graph.neighbors(field_node) if str(n).startswith("well:"))
            lines.append(
                f"- field:{value} connected_wells={well_count} confidence={confidence:.2f}"
            )
            entity_hits.append(canonical_id)
            matched += 1
            continue

        if etype == "operator":
            operator_node = canonical_id
            if operator_node not in graph:
                continue
            well_count = sum(1 for n in graph.neighbors(operator_node) if str(n).startswith("well:"))
            lines.append(
                f"- operator:{value} connected_wells={well_count} confidence={confidence:.2f}"
            )
            entity_hits.append(canonical_id)
            matched += 1
            continue

        if etype == "status":
            status_node = canonical_id
            if status_node not in graph:
                continue
            well_count = sum(1 for n in graph.neighbors(status_node) if str(n).startswith("well:"))
            lines.append(
                f"- status:{value} connected_wells={well_count} confidence={confidence:.2f}"
            )
            entity_hits.append(canonical_id)
            matched += 1
            continue

        if etype == "well":
            well_node = canonical_id
            if well_node not in graph:
                continue
            neighbors = [graph.nodes[n].get("label", str(n)) for n in graph.neighbors(well_node)]
            lines.append(
                f"- well:{value} neighbors={', '.join(neighbors[:5])} confidence={confidence:.2f}"
            )
            entity_hits.append(canonical_id)
            matched += 1

    if grounding.ambiguous:
        lines.append("- ambiguity: multiple close candidates detected; prefer tool verification.")

    if grounding.notes:
        lines.append(f"- grounding_notes: {', '.join(grounding.notes[:3])}")

    if matched == 0:
        lines.append("- no_direct_entity_match: use tools normally and rely on filter/aggregation.")

    return KGContext(text="\n".join(lines), matched_entities=matched, entities=entity_hits[:12])

