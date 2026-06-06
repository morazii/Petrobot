# PetroBot Backend Structure

The backend is organized by feature ownership, with shared infrastructure kept
under `backend/shared/`.

## Feature Modules

- `features/agent/`
  Owns the LLM agent loop, tool dispatch, prompt selection, tool schemas, and
  flat/OSDU tool backends.

- `features/knowledge_graph/`
  Owns KG topology generation, canonical entity grounding, planner control
  packets, schema validation, and deterministic tool-argument repair.

## Shared Infrastructure

- `shared/data_access/`
  MongoDB client helpers, seed scripts, and URI utilities.

- `shared/llm/`
  Curl-based provider transport, provider adapters, and normalized LLM types.

- `shared/validators/`
  Shared read-only safety checks and JSON sanitization helpers.

## Runtime Flow

1. `app/features/chat/view.py` calls `backend.features.agent.service.run_agent`.
2. The agent feature builds model context using prompts, schemas, and KG output.
3. The knowledge graph feature resolves entities and builds planner guidance.
4. Tool calls are routed through `features/agent/backends/router.py`.
5. Backend tools use shared data access helpers to query MongoDB.

## Import Rule

Use feature paths for domain behavior:

```python
from backend.features.agent.service import run_agent
from backend.features.knowledge_graph.graph_context import generate_kg_context
```

Use shared paths only for infrastructure:

```python
from backend.shared.llm.providers import openai_compatible_turn
from backend.shared.data_access.mongo_client import get_wells_flat_collection
```
