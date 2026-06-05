# PetroBot Agent Structure

This folder is organized so each concern has one clear home.

## Entry points (stable imports)

- `agent.py`  
  Main LLM loop. Handles model calls, tool-call execution, and response traces.

- `tools.py`  
  Compatibility facade imported by the agent. Re-exports the active tool functions.

- `system_prompt.py`  
  Chooses backend-specific prompt text (`flat` vs `osdu`).

- `tool_schemas.py`  
  Chooses backend-specific tool schemas (`flat` vs `osdu`).

## Backend-specific execution

- `backends/flat_backend.py`  
  Query logic for the flat CSV-style schema (`wells_flat` collection).  
  Includes lazy CSV seeding and flat map/well helpers.

- `backends/osdu_backend.py`  
  Query logic for nested OSDU schema (`wells` collection).

- `backends/common.py`  
  Shared guardrails and JSON sanitization utilities.

- `backends/router.py`  
  Dispatch layer called by the LLM tool loop. Routes calls to active backend.

## LLM transport layer

- `../llm/curl_client.py`  
  Shared HTTP transport that executes provider requests with `curl` only.

- `../llm/providers.py`  
  Provider adapters (Google AI Studio + OpenAI-compatible APIs like Groq/OpenRouter).

- `../llm/types.py`  
  Runtime config and normalized response dataclasses used by the agent loop.

## KG grounding layer

- `kg/graph_context.py`  
  Builds KG topology and produces concise relationship hints for planner context.

- `kg/grounding.py`  
  Canonical entity resolution with confidence, planner control packet generation,
  tool-arg normalization, schema validation, and execution-guided repair.

### 7-stage grounding flow (flat backend)

1. `schema_scope_from_query()` narrows allowed columns/filters for the question.
2. `_stage2_candidate_list_for_mentions()` produces deterministic candidates for mention audit.
3. `resolve_query_entities()` outputs canonical entities + confidence + ambiguity notes.
4. Relationship/path constraints are encoded inside schema scope and filter guards.
5. `planner_packet_from_grounding()` builds the control packet injected into model context.
6. `try_repair_tool_args()` performs one deterministic repair on schema-field errors.
7. `validate_tool_args()` enforces final schema gate before backend execution.

## Prompt organization

- `prompts/flat_prompt.py`
- `prompts/osdu_prompt.py`

## Schema organization

- `schemas/flat_schemas.py`
- `schemas/osdu_schemas.py`

## Backend switch

Configured in `.env` via `DATA_BACKEND`:

- `DATA_BACKEND=flat` (default for POC reliability)
- `DATA_BACKEND=osdu` (future nested OSDU mode)

## LLM provider switch

Configured in `.env` via `LLM_PROVIDER`:

- `LLM_PROVIDER=openai_compatible` for OpenAI-style endpoints (OpenAI, Groq, OpenRouter, Ollama, etc.)
- `LLM_PROVIDER=google_ai_studio` for native Gemini `generateContent` endpoint

Common variables:

- `LLM_MODEL`
- `LLM_API_KEY`
- `LLM_BASE_URL`
