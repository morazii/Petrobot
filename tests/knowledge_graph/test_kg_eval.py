from backend.features.knowledge_graph.graph_context import generate_kg_context
from backend.features.knowledge_graph.grounding import resolve_query_entities


def test_kg_resolves_typo_well_to_canonical_entity():
    grounding = resolve_query_entities("Tell me about deltta-15", enabled=True)

    assert any(
        entity.entity_type == "well" and entity.canonical_value == "Delta-15"
        for entity in grounding.entities
    )


def test_kg_context_returns_relationship_hints():
    context = generate_kg_context("Tell me about Delta-15", enabled=True)

    assert context is not None
    assert context.matched_entities >= 1
    assert "Knowledge graph hints" in context.text
