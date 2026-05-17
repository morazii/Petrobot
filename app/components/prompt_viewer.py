"""
app/components/prompt_viewer.py
-------------------------------
Render a full execution trace per assistant turn:
- system prompt
- tool calls and tool results
- optional KG context (when enabled)
- final LLM reply
"""

import json

import streamlit as st

from backend.agent.system_prompt import SYSTEM_PROMPT


def _json_block(obj) -> str:
    try:
        return json.dumps(obj, indent=2, default=str, ensure_ascii=False)
    except Exception:
        return str(obj)


def render_prompt_viewer(responses: list, compact: bool = False):
    if compact:
        st.caption("Full trace of LLM inputs, tool calls, KG hints, and outputs.")
    else:
        st.subheader("Prompt Viewer")
        st.caption("Full trace of model input/output and tool execution.")

    with st.expander("System Prompt (injected at start of every conversation)", expanded=False):
        st.code(SYSTEM_PROMPT, language="markdown")

    if not responses:
        st.info("No conversations yet. Ask a question in the Chat view to see traces here.")
        return

    st.divider()

    for turn_idx, response in enumerate(responses):
        turn_label = f"Turn {turn_idx + 1}"
        if response.tool_calls:
            turn_label += f"  ·  tools: {' -> '.join(response.tool_calls)}"

        with st.expander(turn_label, expanded=(turn_idx == len(responses) - 1)):
            trace = getattr(response, "trace", [])
            if not trace:
                st.warning("No trace data for this turn.")
                continue

            for entry in trace:
                entry_type = entry.get("type")
                round_num = entry.get("round", 0)

                if entry_type == "kg_context":
                    st.markdown(
                        f"**KG Context** (matched entities: {entry.get('matched_entities', 0)})"
                    )
                    entities = entry.get("entities", [])
                    if entities:
                        st.caption(f"entities: {', '.join(entities)}")
                    st.code(entry.get("content", ""), language="markdown")
                    continue

                if entry_type == "tool_call":
                    st.markdown(f"**Tool Call:** `{entry['name']}` (round {round_num + 1})")
                    st.code(_json_block(entry.get("args", {})), language="json")
                    continue

                if entry_type == "tool_result":
                    result = entry.get("result", [])
                    char_count = entry.get("char_count", 0)
                    if isinstance(result, list):
                        label = f"**Tool Result:** `{entry['name']}` - {len(result)} row(s), {char_count:,} chars"
                    else:
                        label = f"**Tool Result:** `{entry['name']}` - {char_count:,} chars"
                    st.markdown(label)
                    preview = result[:10] if isinstance(result, list) else result
                    st.code(_json_block(preview), language="json")
                    if isinstance(result, list) and len(result) > 10:
                        st.caption(f"Showing 10 of {len(result)} rows.")
                    continue

                if entry_type == "llm_reply":
                    st.markdown(f"**Final LLM Reply** (round {round_num + 1})")
                    st.markdown(
                        f"""<div style="background:rgba(9,18,29,0.92);border:1px solid rgba(93,126,157,0.38);
                        padding:12px 14px;border-radius:10px;white-space:pre-wrap;
                        color:#d7e4f1;font-family:monospace;font-size:0.85rem;">{entry.get('content','')}</div>""",
                        unsafe_allow_html=True,
                    )

            if response.error:
                st.error(f"Agent error: {response.error}")
