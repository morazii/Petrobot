import streamlit as st


def render_sidebar():
    """Render the sidebar with configuration and demo queries."""
    with st.sidebar:
        st.title("Configuration")

        # We don't allow changing config here to keep it simple and safe.
        # It's loaded from .env. We just display what's active.
        import config.settings as cfg

        provider = cfg.LLM_BASE_URL.split("://")[-1].split("/")[0]
        st.info(
            f"**Model:** {cfg.LLM_MODEL}\n\n"
            f"**Provider:** {provider}\n\n"
            f"**Backend:** {cfg.DATA_BACKEND}"
        )

        st.divider()
        st.subheader("Performance")

        if "kg_enabled" not in st.session_state:
            st.session_state.kg_enabled = False

        st.toggle(
            "Knowledge Graph Augmentation",
            key="kg_enabled",
            help="Toggle graph-based context hints on/off to compare response quality and latency.",
        )

        st.divider()
        st.subheader("Try Asking")

        if cfg.DATA_BACKEND == "flat":
            queries = [
                "How many wells per field? Give me a ranked list.",
                "Which operator has the most drilling wells right now?",
                "Tell me about Delta-15",
                "What are the 5 deepest wells by drillers_td_m?",
                "Show producing wells on a map",
                "Wells spudded each year since 2015",
                "Compare Delta and Eagle fields",
            ]
        else:
            queries = [
                "How many wells per field? Give me a ranked list.",
                "Which operator has the most drilling wells right now?",
                "Tell me about Delta-15",
                "Show producing wells on a map",
                "Wells spudded each year since 2015",
                "Compare Delta and Eagle fields",
            ]

        for query in queries:
            if st.button(query, use_container_width=True):
                st.session_state.demo_query = query

        st.divider()

        if st.button("Clear Conversation", type="primary", use_container_width=True):
            st.session_state.messages = []
            st.session_state.responses = []
            st.session_state.pop("demo_query", None)
            st.rerun()
