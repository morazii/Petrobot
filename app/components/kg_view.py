"""Ontology and knowledge-graph visualization view."""

from __future__ import annotations

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.agent.kg.graph_context import get_kg_snapshot, get_ontology_definition


_KIND_COLORS = {
    "well": "#6ea8ff",
    "field": "#f59e0b",
    "operator": "#34d399",
    "status": "#f87171",
    "objective": "#c084fc",
    "platform": "#22d3ee",
}


def _build_plotly_graph(graph: nx.Graph) -> go.Figure:
    """Create an interactive Plotly network figure from a sampled KG graph."""
    if graph.number_of_nodes() == 0:
        return go.Figure()

    # Deterministic layout keeps view stable while users compare runs.
    positions = nx.spring_layout(graph, seed=42, k=0.42, iterations=65)

    edge_x: list[float] = []
    edge_y: list[float] = []
    for src, dst in graph.edges():
        x0, y0 = positions[src]
        x1, y1 = positions[dst]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(width=0.7, color="rgba(159, 178, 198, 0.42)"),
        hoverinfo="skip",
        showlegend=False,
    )

    node_traces: list[go.Scatter] = []
    kinds = sorted({str(data.get("kind", "other")) for _, data in graph.nodes(data=True)})
    for kind in kinds:
        kind_nodes = [node for node, data in graph.nodes(data=True) if str(data.get("kind", "other")) == kind]
        x_vals: list[float] = []
        y_vals: list[float] = []
        texts: list[str] = []
        for node in kind_nodes:
            x, y = positions[node]
            x_vals.append(x)
            y_vals.append(y)
            label = graph.nodes[node].get("label", node)
            degree = graph.degree[node]
            texts.append(f"{label}<br>kind={kind}<br>degree={degree}")

        node_traces.append(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="markers",
                name=kind,
                text=texts,
                hovertemplate="%{text}<extra></extra>",
                marker=dict(
                    size=8 if kind == "well" else 13,
                    color=_KIND_COLORS.get(kind, "#94a3b8"),
                    line=dict(width=0.7, color="rgba(9, 18, 29, 0.9)"),
                    opacity=0.92,
                ),
            )
        )

    fig = go.Figure(data=[edge_trace, *node_traces])
    fig.update_layout(
        title="Knowledge Graph Topology",
        title_font=dict(color="#e6eef7"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=44, b=10),
        height=680,
        showlegend=True,
        legend=dict(
            bgcolor="rgba(9,18,29,0.72)",
            bordercolor="rgba(117,142,165,0.42)",
            borderwidth=1,
            font=dict(color="#d7e4f1"),
        ),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
    )
    return fig


def render_kg_view():
    """Render full-page ontology + KG visual explorer."""
    st.subheader("Ontology & Knowledge Graph")
    st.caption("Inspect entity types, relationships, and sampled graph topology used by KG augmentation.")

    ontology_df = pd.DataFrame(get_ontology_definition())
    st.markdown("#### Ontology")
    st.dataframe(ontology_df, use_container_width=True, hide_index=True)

    max_wells = st.slider(
        "Well nodes to include in graph sample",
        min_value=40,
        max_value=500,
        value=180,
        step=20,
        help="Higher values show more graph coverage but can reduce rendering responsiveness.",
    )

    snapshot = get_kg_snapshot(max_wells=max_wells)
    if not snapshot.get("supported"):
        st.info(snapshot.get("reason", "Knowledge graph visualization is not available for this backend mode."))
        return

    graph = snapshot["graph"]
    stats = snapshot.get("stats", {})
    edge_counts = snapshot.get("edge_counts", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Wells (dataset)", int(stats.get("wells", 0)))
    c2.metric("Fields", int(stats.get("fields", 0)))
    c3.metric("Operators", int(stats.get("operators", 0)))
    c4.metric("Statuses", int(stats.get("statuses", 0)))

    c5, c6 = st.columns(2)
    c5.metric("Sampled Nodes", graph.number_of_nodes())
    c6.metric("Sampled Edges", graph.number_of_edges())

    if edge_counts:
        rel_df = pd.DataFrame(
            [{"relationship": rel, "edges": count} for rel, count in sorted(edge_counts.items())]
        ).sort_values("edges", ascending=False)
        st.markdown("#### Relationship Counts (Sampled Graph)")
        st.dataframe(rel_df, use_container_width=True, hide_index=True)

    st.markdown("#### Graph Visualization")
    fig = _build_plotly_graph(graph)
    st.plotly_chart(fig, use_container_width=True)

