import os

import streamlit as st


def _normalize_provider(raw: str) -> str:
    aliases = {
        "openai": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "groq": "groq",
        "openrouter": "openrouter",
        "google": "google_ai_studio",
        "google_ai_studio": "google_ai_studio",
        "gemini": "google_ai_studio",
    }
    return aliases.get((raw or "").strip().lower(), "openai_compatible")


def render_sidebar():
    """Render the sidebar with runtime LLM config and demo queries."""
    with st.sidebar:
        st.title("Configuration")

        import config.settings as cfg

        profile_defaults = {
            "google_ai_studio": {
                "label": "Google AI Studio",
                "model": "gemini-flash-latest",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "api_key_env": "GOOGLE_AI_STUDIO_API_KEY",
            },
            "groq": {
                "label": "Groq",
                "model": "openai/gpt-oss-120b",
                "base_url": "https://api.groq.com/openai/v1",
                "api_key_env": "GROQ_API_KEY",
            },
            "openrouter": {
                "label": "OpenRouter",
                "model": "openai/gpt-oss-120b:free",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
            },
        }

        active_provider = _normalize_provider(cfg.LLM_PROVIDER)
        if active_provider not in profile_defaults:
            active_provider = "google_ai_studio"

        if "llm_provider" not in st.session_state:
            st.session_state.llm_provider = active_provider

        provider = st.selectbox(
            "LLM Provider",
            options=["google_ai_studio", "groq", "openrouter"],
            format_func=lambda p: profile_defaults[p]["label"],
            key="llm_provider",
        )

        defaults = profile_defaults[provider]
        model_key = f"llm_model_{provider}"
        base_key = f"llm_base_{provider}"

        if model_key not in st.session_state:
            st.session_state[model_key] = cfg.LLM_MODEL if provider == active_provider else defaults["model"]
        if base_key not in st.session_state:
            st.session_state[base_key] = cfg.LLM_BASE_URL if provider == active_provider else defaults["base_url"]

        model = st.text_input("Model", key=model_key)
        base_url = st.text_input("Base URL", key=base_key)
        api_key = os.getenv(defaults["api_key_env"], "")
        if provider == "google_ai_studio" and not api_key:
            api_key = cfg.LLM_API_KEY if cfg.LLM_PROVIDER == "google_ai_studio" else ""

        st.session_state.llm_runtime_config = {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
        }

        st.info(
            f"**Model:** {model}\n\n"
            f"**Provider:** {profile_defaults[provider]['label']}\n\n"
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
