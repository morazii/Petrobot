from pathlib import Path

import pandas as pd
import streamlit as st


@st.cache_data
def load_dataset_preview():
    """Load a small preview dataset for the dataset preview feature."""
    data_path = Path(__file__).resolve().parents[3] / "Data" / "well-information.csv"
    return pd.read_csv(data_path, nrows=50)


def render_dataset_preview():
    st.subheader("Dataset Preview")
    st.caption("Showing the first 50 rows from well-information.csv.")
    st.dataframe(load_dataset_preview(), use_container_width=True, hide_index=True)
