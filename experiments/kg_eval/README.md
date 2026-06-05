# KG Offline Evaluation

This folder is isolated from app runtime and is used for KG extraction experiments.

## What this does

- Runs KG entity extraction checks directly against `generate_kg_context(...)`.
- Does **not** call any LLM API.
- Produces reproducible metrics and miss examples.

## Files

- `cases.json`: benchmark queries + expected targets.
- `run_eval.py`: offline evaluator and gate checker.
- `reports/`: generated outputs (JSON reports).

## Run

```bash
.\venv\Scripts\python experiments/kg_eval/run_eval.py --report experiments/kg_eval/reports/baseline.json
```

Optional thresholds:

```bash
.\venv\Scripts\python experiments/kg_eval/run_eval.py --min-f1 0.85 --min-typo-hit-at1 0.90
```
