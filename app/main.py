import sys
from pathlib import Path

import streamlit as st

# Ensure project root is in path so absolute imports work
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.features.chat.view import render_chat
from app.features.dataset_preview.view import render_dataset_preview
from app.features.knowledge_graph.view import render_kg_view
from app.features.prompt_viewer.view import render_prompt_viewer
from app.shared.components.sidebar import render_sidebar


def load_css():
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def main():
    st.set_page_config(
        page_title="PetroBot Analytics",
        page_icon="â›½",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Apply custom styling
    load_css()

    # Sidebar
    try:
        render_sidebar()
    except Exception as exc:
        st.error(f"Sidebar failed to load: {exc}")
        st.session_state.llm_runtime_config = None

    # Header
    st.markdown(
        """
        <section class="hero-shell">
          <h1 class="hero-brand">PetroBot</h1>
          <p>Ask natural-language questions about your Middle East well portfolio and inspect structured outputs inline.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<section class="view-switch">', unsafe_allow_html=True)
    active_view = st.radio(
        "Workspace View",
        ["Chat", "Dataset Preview", "Prompt Viewer", "Ontology & KG"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("</section>", unsafe_allow_html=True)

    try:
        if active_view == "Chat":
            render_chat()
        elif active_view == "Dataset Preview":
            render_dataset_preview()
        elif active_view == "Prompt Viewer":
            render_prompt_viewer(st.session_state.get("responses", []))
        else:
            render_kg_view()
    except Exception as exc:
        st.error(f"{active_view} view failed to load: {exc}")
        st.exception(exc)


if __name__ == "__main__":
    main()

