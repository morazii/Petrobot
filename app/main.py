import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure project root is in path so absolute imports work
project_root = str(Path(__file__).resolve().parents[1])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.chat import render_chat
from app.components.kg_view import render_kg_view
from app.components.prompt_viewer import render_prompt_viewer
from app.components.sidebar import render_sidebar


@st.cache_data
def load_dataset_preview():
    """Load a small preview dataset for the right-rail panel."""
    data_path = Path(__file__).resolve().parents[1] / "Data" / "well-information.csv"
    return pd.read_csv(data_path, nrows=50)


def load_css():
    css_path = Path(__file__).parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


st.set_page_config(
    page_title="PetroBot Analytics",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom styling
load_css()

# Sidebar
render_sidebar()

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

if active_view == "Chat":
    render_chat()
elif active_view == "Dataset Preview":
    st.subheader("Dataset Preview")
    st.caption("Showing the first 50 rows from well-information.csv.")
    st.dataframe(load_dataset_preview(), use_container_width=True, hide_index=True)
elif active_view == "Prompt Viewer":
    render_prompt_viewer(st.session_state.get("responses", []))
else:
    render_kg_view()
