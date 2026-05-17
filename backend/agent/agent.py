"""
backend/agent/agent.py
----------------------
PetroBot agent loop.

Per-turn sequence:
1. Build model context: [system prompt] + conversation history.
2. Call the LLM with active tool schemas.
3. If the LLM asks for tools, execute each call and append tool outputs.
4. Re-call the LLM with updated context so it can reason on tool results.
5. Return final assistant text plus structured artifacts for the UI.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

import config.settings as cfg
from backend.agent.kg.graph_context import generate_kg_context
from backend.agent.system_prompt import SYSTEM_PROMPT
from backend.agent.tool_schemas import TOOL_SCHEMAS
from backend.agent.tools import dispatch_tool


@dataclass
class AgentResponse:
    text: str = ""
    table: list[dict] | None = None
    map_data: list[dict] | None = None
    tool_calls: list[str] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float | None = None
    kg_enabled: bool = False
    kg_matched_entities: int = 0
    kg_entities: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    # trace item examples:
    # {"type": "tool_call", "round": 0, "name": "query_wells", "args": {...}}
    # {"type": "tool_result", "round": 0, "name": "query_wells", "result": [...], "char_count": 1234}
    # {"type": "llm_reply", "round": 1, "content": "Final answer..."}


def _make_client() -> OpenAI:
    headers = None
    # These attribution headers are specific to OpenRouter.
    if "openrouter.ai" in cfg.LLM_BASE_URL:
        headers = {
            "HTTP-Referer": "https://petrobot.app",
            "X-OpenRouter-Title": "PetroBot",
        }

    return OpenAI(
        api_key=cfg.LLM_API_KEY,
        base_url=cfg.LLM_BASE_URL,
        default_headers=headers,
    )


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def _truncate(obj: Any, max_chars: int = cfg.MAX_RESULT_CHARS) -> str:
    """Serialize tool result to JSON and cap size before feeding back to model."""
    payload = json.dumps(obj, default=str, ensure_ascii=False)
    if len(payload) > max_chars:
        payload = payload[:max_chars] + f"\n... [truncated - {len(payload) - max_chars} chars omitted]"
    return payload


def _is_map_result(result: Any) -> bool:
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return "lat" in result[0] and "lon" in result[0]
    return False


def _is_tabular(result: Any) -> bool:
    return (
        isinstance(result, list)
        and len(result) > 0
        and isinstance(result[0], dict)
        and "error" not in result[0]
        and "lat" not in result[0]
    )


def run_agent(messages: list[dict], stream: bool = False, use_kg: bool = False) -> AgentResponse:
    """
    Execute one end-to-end agent turn.

    `messages` should contain previous user/assistant history. The system prompt
    is always injected here so backend-specific rules stay centralized.
    """
    _ = stream  # Reserved for future streaming support.
    response = AgentResponse()
    response.kg_enabled = bool(use_kg)
    client = _get_client()
    started = time.perf_counter()

    full_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Optional KG augmentation:
    # we add one extra system hint that summarizes graph relationships relevant
    # to the current user query. The model must still verify final answers via tools.
    latest_user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_user_text = str(msg.get("content", "") or "")
            break

    kg_ctx = generate_kg_context(latest_user_text, enabled=use_kg)
    if kg_ctx:
        full_messages.append({"role": "system", "content": kg_ctx.text})
        response.kg_matched_entities = kg_ctx.matched_entities
        response.kg_entities = kg_ctx.entities
        response.trace.append(
            {
                "type": "kg_context",
                "round": 0,
                "matched_entities": kg_ctx.matched_entities,
                "entities": kg_ctx.entities,
                "content": kg_ctx.text,
            }
        )

    full_messages.extend(messages)

    last_tool_result: Any = None
    last_tool_name: str | None = None

    for round_num in range(cfg.MAX_TOOL_ROUNDS):
        try:
            completion = client.chat.completions.create(
                model=cfg.LLM_MODEL,
                messages=full_messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0.1,
            )
        except Exception as exc:
            response.error = f"LLM API error: {exc}"
            response.text = "I encountered an error reaching the AI model. Please check your API key and try again."
            response.elapsed_ms = (time.perf_counter() - started) * 1000
            return response

        msg = completion.choices[0].message

        # No tool calls means the model finalized its answer.
        if not msg.tool_calls:
            response.text = msg.content or ""
            response.trace.append({"type": "llm_reply", "round": round_num, "content": response.text})

            if last_tool_name == "get_map_data" and _is_map_result(last_tool_result):
                response.map_data = last_tool_result
            elif last_tool_result is not None and _is_tabular(last_tool_result):
                response.table = last_tool_result

            response.elapsed_ms = (time.perf_counter() - started) * 1000
            return response

        # Keep assistant tool-call message in history, then execute each tool.
        full_messages.append(msg.model_dump(exclude_unset=True))

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            response.tool_calls.append(tool_name)

            # Parse function arguments exactly as returned by the LLM.
            try:
                tool_args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                tool_result = {"error": f"Failed to parse tool arguments: {exc}"}
                tool_args = {}
            else:
                tool_result = dispatch_tool(tool_name, tool_args)

            response.trace.append(
                {"type": "tool_call", "round": round_num, "name": tool_name, "args": tool_args}
            )
            response.trace.append(
                {
                    "type": "tool_result",
                    "round": round_num,
                    "name": tool_name,
                    "result": tool_result,
                    "char_count": len(json.dumps(tool_result, default=str, ensure_ascii=False)),
                }
            )

            last_tool_result = tool_result
            last_tool_name = tool_name

            # This tool payload is what the model "sees" before next reasoning step.
            full_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _truncate(tool_result),
                }
            )

    response.error = f"Agent reached maximum tool rounds ({cfg.MAX_TOOL_ROUNDS}) without a final answer."
    response.text = (
        "I was unable to complete the analysis within the allowed number of steps. "
        "Try rephrasing your question or asking for something more specific."
    )
    response.elapsed_ms = (time.perf_counter() - started) * 1000
    return response


def new_conversation() -> list[dict]:
    return []


def add_user_message(messages: list[dict], text: str) -> list[dict]:
    return messages + [{"role": "user", "content": text}]


def add_assistant_message(messages: list[dict], response: AgentResponse) -> list[dict]:
    return messages + [{"role": "assistant", "content": response.text}]
