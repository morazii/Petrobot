"""Shared runtime types for LLM provider calls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMRuntimeConfig:
    provider: str
    model: str
    base_url: str
    api_key: str


@dataclass
class NormalizedToolCall:
    id: str
    name: str
    arguments_json: str


@dataclass
class NormalizedAssistantTurn:
    content: str
    tool_calls: list[NormalizedToolCall]
    raw_message: dict
