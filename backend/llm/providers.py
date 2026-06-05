"""Provider adapters that normalize model responses for the agent loop."""

from __future__ import annotations

import json
import time

from backend.llm.curl_client import post_json
from backend.llm.types import LLMRuntimeConfig, NormalizedAssistantTurn, NormalizedToolCall


def _to_gemini_tools(tool_schemas: list[dict]) -> list[dict]:
    declarations: list[dict] = []
    for tool in tool_schemas:
        fn = tool.get("function", {})
        if not fn:
            continue
        declarations.append(
            {
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return [{"functionDeclarations": declarations}] if declarations else []


def to_gemini_contents(messages: list[dict]) -> list[dict]:
    contents: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = str(msg.get("content", "") or "")
        contents.append(
            {
                "role": "user" if role == "user" else "model",
                "parts": [{"text": text}],
            }
        )
    return contents


def _extract_gemini_text(candidate: dict) -> str:
    parts = ((candidate.get("content") or {}).get("parts") or [])
    chunks: list[str] = []
    for part in parts:
        text = part.get("text")
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip()


def _extract_gemini_tool_calls(candidate: dict) -> list[NormalizedToolCall]:
    parts = ((candidate.get("content") or {}).get("parts") or [])
    calls: list[NormalizedToolCall] = []
    for idx, part in enumerate(parts):
        call = part.get("functionCall")
        if not call:
            continue
        call_id = call.get("id") or f"fc_{int(time.time() * 1000)}_{idx}"
        calls.append(
            NormalizedToolCall(
                id=call_id,
                name=call.get("name", ""),
                arguments_json=json.dumps(call.get("args", {}), ensure_ascii=False),
            )
        )
    return calls


def openai_compatible_turn(
    runtime: LLMRuntimeConfig,
    messages: list[dict],
    tool_schemas: list[dict],
) -> NormalizedAssistantTurn:
    url = f"{runtime.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {runtime.api_key}"}
    if "openrouter.ai" in runtime.base_url:
        headers["HTTP-Referer"] = "https://petrobot.app"
        headers["X-OpenRouter-Title"] = "PetroBot"

    payload = {
        "model": runtime.model,
        "messages": messages,
        "tools": tool_schemas,
        "tool_choice": "auto",
        "temperature": 0.1,
    }
    raw = post_json(url=url, headers=headers, payload=payload, timeout_s=90)

    choices = raw.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices in provider response: {raw}")

    msg = (choices[0] or {}).get("message") or {}
    tool_calls = []
    for tool_call in msg.get("tool_calls") or []:
        fn = tool_call.get("function") or {}
        tool_calls.append(
            NormalizedToolCall(
                id=tool_call.get("id", f"call_{int(time.time() * 1000)}"),
                name=fn.get("name", ""),
                arguments_json=fn.get("arguments") or "{}",
            )
        )

    return NormalizedAssistantTurn(
        content=msg.get("content") or "",
        tool_calls=tool_calls,
        raw_message=msg,
    )


def google_ai_studio_turn(
    runtime: LLMRuntimeConfig,
    contents: list[dict],
    system_instruction: str,
    tool_schemas: list[dict],
) -> NormalizedAssistantTurn:
    url = f"{runtime.base_url.rstrip('/')}/models/{runtime.model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "tools": _to_gemini_tools(tool_schemas),
        "generationConfig": {"temperature": 0.1},
    }
    raw = post_json(
        url=url,
        headers={"X-goog-api-key": runtime.api_key},
        payload=payload,
        timeout_s=90,
    )

    candidates = raw.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Google AI Studio returned no candidates: {raw}")
    candidate = candidates[0]

    return NormalizedAssistantTurn(
        content=_extract_gemini_text(candidate),
        tool_calls=_extract_gemini_tool_calls(candidate),
        raw_message=candidate.get("content") or {"role": "model", "parts": [{"text": ""}]},
    )
