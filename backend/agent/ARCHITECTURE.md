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

