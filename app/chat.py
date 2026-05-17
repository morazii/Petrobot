"""
app/chat.py
------------
Chat interface for PetroBot.

Session state:
  st.session_state.messages   - list[dict]           - user+assistant messages for LLM context
  st.session_state.responses  - list[AgentResponse]  - one per assistant turn
"""

import pandas as pd
import streamlit as st

from app.components.map_view import render_map
from backend.agent.agent import (
    add_assistant_message,
    add_user_message,
    new_conversation,
    run_agent,
)


def _init_state():
    if "messages" not in st.session_state:
        st.session_state.messages = new_conversation()
    if "responses" not in st.session_state:
        st.session_state.responses = []


def _decode_uri(val) -> str:
    """Convert OSDU URI to readable label for table display."""
    if not isinstance(val, str) or not val.startswith("osdu:"):
        return val
    parts = [p for p in val.split(":") if p.strip() and "--" not in p]
    token = parts[-1] if parts else val
    return token.replace("_", " ").replace("-", " ").title()


def _render_table(data: list[dict]):
    """Render a clean data table with OSDU URIs decoded."""
    if not data:
        return
    decoded = []
    for row in data:
        decoded.append(
            {
                ("label" if k == "_id" else k): (_decode_uri(v) if isinstance(v, str) else v)
                for k, v in row.items()
            }
        )
    df = pd.DataFrame(decoded)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_response_data(response):
    """Render map or table for a completed AgentResponse in inline cards."""
    if response.map_data:
        st.markdown(
            '<div class="inline-result-title">Geospatial Result</div>',
            unsafe_allow_html=True,
        )
        render_map(response.map_data)
    elif response.table:
        with st.expander(f"Structured Result - {len(response.table)} rows", expanded=True):
            _render_table(response.table)


def _render_conversation_stream():
    """Render all chat messages and attached structured outputs."""
    response_idx = 0
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        elif msg["role"] == "assistant":
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
                if response_idx < len(st.session_state.responses):
                    resp = st.session_state.responses[response_idx]
                    meta = []
                    meta.append("kg:on" if getattr(resp, "kg_enabled", False) else "kg:off")
                    elapsed_ms = getattr(resp, "elapsed_ms", None)
                    if elapsed_ms is not None:
                        meta.append(f"{elapsed_ms:.0f}ms")
                    if meta:
                        st.caption(" | ".join(meta))
                    kg_entities = getattr(resp, "kg_entities", [])
                    if kg_entities:
                        st.caption(f"kg entities: {', '.join(kg_entities[:8])}")
                    if resp.tool_calls:
                        st.caption(f"tools: {' -> '.join(resp.tool_calls)}")
                    _render_response_data(resp)
                response_idx += 1


def render_chat():
    """
    Render the full chat page.

    Important: st.chat_input is kept in the page body (not inside tabs) so it
    remains pinned to the bottom in Chat view.
    """
    _init_state()

    user_input = st.chat_input("Ask anything about your well data...", key="chat_input_main")

    if "demo_query" in st.session_state:
        user_input = st.session_state.pop("demo_query")

    _render_conversation_stream()

    if not user_input:
        return

    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages = add_user_message(st.session_state.messages, user_input)

    with st.chat_message("assistant"):
        with st.spinner("Querying well data..."):
            response = run_agent(
                st.session_state.messages,
                use_kg=bool(st.session_state.get("kg_enabled", False)),
            )

        if response.error:
            st.error(response.error)

        meta = []
        meta.append("kg:on" if getattr(response, "kg_enabled", False) else "kg:off")
        if response.elapsed_ms is not None:
            meta.append(f"{response.elapsed_ms:.0f}ms")
        if meta:
            st.caption(" | ".join(meta))
        if getattr(response, "kg_entities", []):
            st.caption(f"kg entities: {', '.join(response.kg_entities[:8])}")

        if response.tool_calls:
            st.caption(f"tools: {' -> '.join(response.tool_calls)}")

        st.markdown(response.text)
        _render_response_data(response)

    st.session_state.messages = add_assistant_message(st.session_state.messages, response)
    st.session_state.responses.append(response)
