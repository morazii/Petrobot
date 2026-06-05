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

import config.settings as cfg
from backend.agent.kg.graph_context import generate_kg_context
from backend.agent.kg.grounding import (
    grounding_to_prompt_text,
    planner_packet_from_grounding,
    planner_packet_to_prompt_text,
    resolve_query_entities,
)
from backend.agent.system_prompt import SYSTEM_PROMPT
from backend.agent.tool_schemas import TOOL_SCHEMAS
from backend.agent.tools import dispatch_tool
from backend.llm.providers import google_ai_studio_turn, openai_compatible_turn, to_gemini_contents
from backend.llm.types import LLMRuntimeConfig


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


def _truncate(obj: Any, max_chars: int = cfg.MAX_RESULT_CHARS) -> str:
    """Serialize tool result to JSON and cap size before feeding back to model."""
    payload = json.dumps(obj, default=str, ensure_ascii=False)
    if len(payload) > max_chars:
        payload = payload[:max_chars] + f"\n... [truncated - {len(payload) - max_chars} chars omitted]"
    return payload


def _as_capped_object(obj: Any) -> Any:
    """Keep function response JSON lightweight for providers that need structured objects."""
    payload = json.dumps(obj, default=str, ensure_ascii=False)
    if len(payload) <= cfg.MAX_RESULT_CHARS:
        return obj
    return {"truncated_json": payload[: cfg.MAX_RESULT_CHARS]}


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


def _normalize_provider(raw: str) -> str:
    val = (raw or "").strip().lower()
    aliases = {
        "openai": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "groq": "groq",
        "openrouter": "openrouter",
        "google": "google_ai_studio",
        "google_ai_studio": "google_ai_studio",
        "gemini": "google_ai_studio",
    }
    return aliases.get(val, "openai_compatible")


def _resolve_runtime(llm_config: dict | None) -> LLMRuntimeConfig:
    provider = _normalize_provider((llm_config or {}).get("provider", cfg.LLM_PROVIDER))
    model = str((llm_config or {}).get("model", cfg.LLM_MODEL))
    base_url = str((llm_config or {}).get("base_url", cfg.LLM_BASE_URL)).strip().rstrip("/")
    api_key = str((llm_config or {}).get("api_key", cfg.LLM_API_KEY)).strip()

    if provider == "groq":
        base_url = base_url or "https://api.groq.com/openai/v1"
    elif provider == "openrouter":
        base_url = base_url or "https://openrouter.ai/api/v1"
    elif provider == "google_ai_studio":
        base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"

    # Normalize common OpenAI-compatible copy/paste mistakes.
    if provider in {"openai_compatible", "groq", "openrouter"}:
        for suffix in ("/chat/completions", "/completions"):
            if base_url.endswith(suffix):
                base_url = base_url[: -len(suffix)]

    if not api_key:
        raise ValueError("Selected provider is missing an API key.")

    return LLMRuntimeConfig(provider=provider, model=model, base_url=base_url, api_key=api_key)


def run_agent(
    messages: list[dict],
    stream: bool = False,
    use_kg: bool = False,
    llm_config: dict | None = None,
) -> AgentResponse:
    """
    Execute one end-to-end agent turn.

    `messages` should contain previous user/assistant history. The system prompt
    is always injected here so backend-specific rules stay centralized.
    """
    _ = stream  # Reserved for future streaming support.
    response = AgentResponse()
    response.kg_enabled = bool(use_kg)
    started = time.perf_counter()

    try:
        runtime = _resolve_runtime(llm_config)
    except Exception as exc:
        response.error = f"Invalid LLM configuration: {exc}"
        response.text = "I could not start because the model configuration is invalid."
        response.elapsed_ms = (time.perf_counter() - started) * 1000
        return response

    # Optional KG augmentation:
    latest_user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_user_text = str(msg.get("content", "") or "")
            break

    kg_ctx = generate_kg_context(latest_user_text, enabled=use_kg)
    grounding = resolve_query_entities(latest_user_text, enabled=use_kg)

    if kg_ctx:
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

    grounding_text = grounding_to_prompt_text(grounding)
    grounding_packet = planner_packet_from_grounding(latest_user_text, grounding) if use_kg else None
    grounding_packet_text = planner_packet_to_prompt_text(grounding_packet) if grounding_packet else ""
    if grounding.entities:
        response.trace.append(
            {
                "type": "kg_grounding",
                "round": 0,
                "ambiguous": grounding.ambiguous,
                "entities": [
                    {
                        "entity_type": e.entity_type,
                        "canonical_id": e.canonical_id,
                        "canonical_value": e.canonical_value,
                        "confidence": e.confidence,
                        "source": e.source,
                    }
                    for e in grounding.entities
                ],
                "notes": grounding.notes,
            }
        )
    if grounding_packet:
        response.trace.append({"type": "kg_grounding_packet", "round": 0, "packet": grounding_packet})

    system_text = SYSTEM_PROMPT + (f"\n\n{kg_ctx.text}" if kg_ctx else "") + f"\n\n{grounding_text}"
    if grounding_packet_text:
        system_text += f"\n\n{grounding_packet_text}"

    openai_messages: list[dict] = []
    google_contents: list[dict] = []

    if runtime.provider == "google_ai_studio":
        google_contents = to_gemini_contents(messages)
    else:
        openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if kg_ctx:
            openai_messages.append({"role": "system", "content": kg_ctx.text})
        openai_messages.append({"role": "system", "content": grounding_text})
        if grounding_packet_text:
            openai_messages.append({"role": "system", "content": grounding_packet_text})
        openai_messages.extend(messages)

    last_tool_result: Any = None
    last_tool_name: str | None = None

    for round_num in range(cfg.MAX_TOOL_ROUNDS):
        try:
            if runtime.provider == "google_ai_studio":
                turn = google_ai_studio_turn(
                    runtime=runtime,
                    contents=google_contents,
                    system_instruction=system_text,
                    tool_schemas=TOOL_SCHEMAS,
                )
            else:
                turn = openai_compatible_turn(
                    runtime=runtime,
                    messages=openai_messages,
                    tool_schemas=TOOL_SCHEMAS,
                )
        except Exception as exc:
            response.error = f"LLM API error: {exc}"
            response.text = "I encountered an error reaching the AI model. Please check the selected provider/model and key."
            response.elapsed_ms = (time.perf_counter() - started) * 1000
            return response

        if not turn.tool_calls:
            response.text = turn.content
            response.trace.append({"type": "llm_reply", "round": round_num, "content": response.text})

            if last_tool_name == "get_map_data" and _is_map_result(last_tool_result):
                response.map_data = last_tool_result
            elif last_tool_result is not None and _is_tabular(last_tool_result):
                response.table = last_tool_result

            response.elapsed_ms = (time.perf_counter() - started) * 1000
            return response

        if runtime.provider == "google_ai_studio":
            google_contents.append(turn.raw_message)
        else:
            openai_messages.append(turn.raw_message)

        for tool_call in turn.tool_calls:
            tool_name = tool_call.name
            response.tool_calls.append(tool_name)

            try:
                tool_args = json.loads(tool_call.arguments_json or "{}")
            except json.JSONDecodeError as exc:
                tool_result = {"error": f"Failed to parse tool arguments: {exc}"}
                tool_args = {}
            else:
                tool_result = dispatch_tool(tool_name, tool_args, grounding=grounding)

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

            if runtime.provider == "google_ai_studio":
                google_contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "id": tool_call.id,
                                    "name": tool_name,
                                    "response": {"result": _as_capped_object(tool_result)},
                                }
                            }
                        ],
                    }
                )
            else:
                openai_messages.append(
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
