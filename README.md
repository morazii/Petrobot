# PetroBot â€” LLM-Powered Well Information & Production Analytics Engine

PetroBot is a natural language analytics engine for oil & gas operations. It enables engineers and analysts to query well information and production data using plain English, with no SQL, no dashboards, and no pre-built reports required. An LLM agent translates each question into a live database query, executes it safely, and returns a synthesised answer with supporting data tables and maps.

---

## Interface

> Ask a question, get a structured answer. Every tool call and LLM response is fully auditable in the Prompt Viewer tab.

### Chat â€” Natural Language Analytics
Natural-language well analytics with inline answers, tables, maps, and trace metadata.

### Ontology & Knowledge Graph â€” Entity Explorer
KG ontology and topology views for wells, fields, operators, statuses, objectives, and platforms.

### Prompt Viewer â€” Trace Inspector
Audit tool calls, KG grounding packets, LLM replies, and structured outputs for each turn.

---

## What it does

- **Ask in plain English:** *"Which operator has the most drilling wells right now?"* â†’ returns a ranked table in seconds.
- **Map visualisation:** *"Show all producing wells"* â†’ renders an interactive geographic scatter map.
- **Well lookup with fuzzy matching:** *"Tell me about Deltta-15"* (typo) â†’ still finds the right well.
- **Prompt transparency:** A built-in **Prompt Viewer** tab shows every tool call, query argument, and LLM reply so the reasoning is fully auditable.
- **Dataset preview:** Browse the raw CSV directly inside the UI.
- **Knowledge Graph:** An interactive graph explorer visualises wellâ€“fieldâ€“operatorâ€“platform relationships and provides query hints to the LLM.

---

## Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚            Streamlit UI (app/)           â”‚
â”‚  Chat  â”‚  Dataset Preview  â”‚  KG View    â”‚
â”‚         Prompt Viewer                    â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                 â”‚ run_agent()
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚     Agent Feature (service.py)          â”‚
â”‚  1. Build context: system prompt + KG    â”‚
â”‚  2. Call LLM with 4 tool schemas         â”‚
â”‚  3. Dispatch tool â†’ execute on MongoDB   â”‚
â”‚  4. Feed result back â†’ repeat            â”‚
â”‚  5. Return structured AgentResponse      â”‚
â””â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
       â”‚                   â”‚
â”Œâ”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  KG Module  â”‚   â”‚   Tool Router         â”‚
â”‚ graph_       â”‚   â”‚  query_wells          â”‚
â”‚ context.py  â”‚   â”‚  aggregate_wells       â”‚
â”‚ (networkx)  â”‚   â”‚  get_well (fuzzy)      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚  get_map_data          â”‚
                  â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚  Backend Layer            â”‚
              â”‚  flat_backend  (default)  â”‚
              â”‚  osdu_backend  (OSDU mode)â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚
              â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
              â”‚  MongoDB Atlas            â”‚
              â”‚  wells_flat collection    â”‚
              â”‚  (auto-seeded from CSV)   â”‚
              â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **LLM writes the queries** | The LLM constructs every MongoDB filter and aggregation pipeline at runtime. No hand-written queries â€” the LLM's full expressiveness is used. |
| **Read-only safety scanner** | A recursive `check_safe()` function blocks all write/destructive MongoDB operators (`$out`, `$merge`, `$set`, etc.) before any query runs. |
| **Dual backend (flat / OSDU)** | Swap `DATA_BACKEND=flat` (simple CSV schema) or `DATA_BACKEND=osdu` (full OSDU nested envelope) via `.env`. Same 4 tools, same agent loop, different collection. |
| **Provider-agnostic LLM** | Uses the standard OpenAI SDK with a configurable `base_url`. Works with OpenAI, OpenRouter, Ollama, Azure, or any compatible endpoint â€” no vendor lock-in. |
| **KG augmentation** | A `networkx` graph is built from the CSV at startup (cached with `lru_cache`). For each user query, matched entities and their relationships are injected as system-message hints before the LLM replies. |
| **Auto-seeding** | On first run the flat backend detects an empty MongoDB collection and seeds it from the CSV automatically. Zero manual setup. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Streamlit |
| **LLM Integration** | OpenAI SDK (provider-agnostic) + OpenRouter |
| **Database** | MongoDB Atlas (M0 Free Tier) |
| **Knowledge Graph** | NetworkX |
| **Fuzzy Matching** | TheFuzz (Levenshtein) |
| **Data Processing** | Pandas |
| **Visualisation** | Plotly (maps + KG graph) |
| **Language** | Python 3.11+ |

---

## Project Structure

```text
petrobot/
|-- app/
|   |-- main.py                  # Streamlit entry point and feature routing
|   |-- assets/style.css         # App styling
|   |-- features/
|   |   |-- chat/view.py          # Chat workflow
|   |   |-- dataset_preview/view.py
|   |   |-- knowledge_graph/view.py
|   |   `-- prompt_viewer/view.py
|   `-- shared/components/
|       |-- sidebar.py            # Runtime config and demo prompts
|       |-- map_view.py           # Reusable map rendering
|       `-- charts.py
|-- backend/
|   |-- ARCHITECTURE.md
|   |-- features/
|   |   |-- agent/                # Agent loop, prompts, schemas, tool backends
|   |   `-- knowledge_graph/      # KG graph, grounding, planner constraints
|   `-- shared/
|       |-- data_access/          # MongoDB clients, seed scripts, URI helpers
|       |-- llm/                  # Curl transport and provider adapters
|       `-- validators/           # Read-only safety and JSON helpers
|-- config/settings.py            # Centralized env config loader
|-- Data/                         # Source datasets
|-- tests/knowledge_graph/kg_eval/          # Isolated KG evaluation suite
|-- tests/agent/test_agent.py
|-- requirements.txt
`-- run.py                        # Start the Streamlit app
```

---

## Quick Start

```bash
# 1. Clone and set up environment
git clone <repo-url> && cd petrobot
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Fill in: LLM_API_KEY, LLM_MODEL, MONGO_URI

# 3. Run
python run.py
```

The app seeds MongoDB automatically on first launch â€” no separate data ingestion step needed.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | âœ… | API key for your LLM provider |
| `LLM_BASE_URL` | âœ… | OpenAI-compatible API base URL |
| `LLM_MODEL` | âœ… | Model identifier (e.g. `deepseek/deepseek-r1:free`) |
| `MONGO_URI` | âœ… | MongoDB Atlas connection string |
| `DATA_BACKEND` | âŒ | `flat` (default) or `osdu` |
| `MAX_TOOL_ROUNDS` | âŒ | Max LLM tool calls per turn (default: 6) |

---

## Knowledge Graph Grounding (How It Works)

In flat backend mode, KG is implemented as a deterministic 7-stage grounding pipeline:

1. **Schema Scope**
- Infer the domain and allowed table/columns/filters for this question.

2. **Candidate Generation**
- Generate entity candidates for mentions (especially well names with typos/format drift).

3. **Entity Resolution**
- Pick canonical IDs/values with confidence, and flag ambiguity when close candidates exist.

4. **Path Constraints**
- Build relationship-safe query constraints so planner/tool calls stay schema-valid.

5. **Planner Control Packet**
- Inject a structured packet into the LLM prompt:
  `resolved_entities`, `unresolved_mentions`, `schema_scope`, and hard constraints.

6. **Execution-Guided Repair**
- If schema validation fails (e.g., misspelled field), attempt one deterministic repair,
  re-validate, then execute.

7. **Final Validation Gate**
- Validate filter fields and pipeline references against the flat schema before DB execution.

This ensures canonical entity usage, constrained planning, and strict query validation.

Core KG files:

- `backend/features/knowledge_graph/graph_context.py`
- `backend/features/knowledge_graph/grounding.py`
- `backend/features/agent/service.py`
- `backend/features/agent/backends/router.py`

