"""
Offline KG entity extraction benchmark runner.

No LLM API calls are made by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config.settings as cfg
from backend.features.knowledge_graph.graph_context import generate_kg_context


@dataclass
class TargetMetrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    hits: int = 0
    hit_at1: int = 0
    hit_at2: int = 0
    total: int = 0


def _norm(text: str) -> str:
    return str(text or "").strip().lower()


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def _split_entities(entities: list[str]) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for item in entities:
        if ":" not in item:
            continue
        etype, value = item.split(":", 1)
        parsed.append((_norm(etype), _norm(value)))
    return parsed


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("cases.json must include a top-level 'cases' list.")
    return cases


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline KG extraction benchmark.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).resolve().parent / "cases.json",
        help="Path to cases JSON file.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional output path for machine-readable JSON report.",
    )
    parser.add_argument(
        "--show-misses",
        type=int,
        default=12,
        help="Max number of miss examples to print.",
    )
    parser.add_argument("--min-f1", type=float, default=0.85, help="Gate: minimum target micro F1.")
    parser.add_argument(
        "--min-typo-hit-at1",
        type=float,
        default=0.90,
        help="Gate: minimum typo well hit@1.",
    )
    args = parser.parse_args()

    if cfg.DATA_BACKEND != "flat":
        raise SystemExit("Offline KG eval requires DATA_BACKEND=flat.")

    cases = _load_cases(args.cases)
    target_metrics = TargetMetrics()
    type_metrics: dict[str, TargetMetrics] = {}
    typo_metrics = TargetMetrics()
    none_total = 0
    none_pass = 0
    misses: list[dict[str, Any]] = []

    for raw_case in cases:
        case = dict(raw_case)
        case_id = str(case.get("id", ""))
        query = str(case.get("query", "")).strip()
        expectation = _norm(case.get("expectation", "target"))

        ctx = generate_kg_context(query, enabled=True)
        entities = list(ctx.entities if ctx else [])
        parsed = _split_entities(entities)

        if expectation == "none":
            none_total += 1
            is_pass = len(parsed) == 0
            none_pass += int(is_pass)
            if not is_pass:
                misses.append(
                    {
                        "id": case_id,
                        "query": query,
                        "reason": "expected_no_entity",
                        "predicted_entities": entities,
                    }
                )
            continue

        target_type = _norm(case.get("target_type", ""))
        target = _norm(case.get("target", ""))
        if not target_type or not target:
            raise ValueError(f"Case '{case_id}' is missing target_type or target.")

        if target_type not in type_metrics:
            type_metrics[target_type] = TargetMetrics()

        typed_preds = [value for etype, value in parsed if etype == target_type]
        hit = target in typed_preds
        hit_at1 = bool(typed_preds) and typed_preds[0] == target
        hit_at2 = target in typed_preds[:2]

        tp = int(hit)
        fp = max(0, len(typed_preds) - tp)
        fn = int(not hit)

        for bucket in (target_metrics, type_metrics[target_type]):
            bucket.total += 1
            bucket.tp += tp
            bucket.fp += fp
            bucket.fn += fn
            bucket.hits += int(hit)
            bucket.hit_at1 += int(hit_at1)
            bucket.hit_at2 += int(hit_at2)

        if "typo" in case_id and target_type == "well":
            typo_metrics.total += 1
            typo_metrics.tp += tp
            typo_metrics.fp += fp
            typo_metrics.fn += fn
            typo_metrics.hits += int(hit)
            typo_metrics.hit_at1 += int(hit_at1)
            typo_metrics.hit_at2 += int(hit_at2)

        if not hit:
            misses.append(
                {
                    "id": case_id,
                    "query": query,
                    "reason": "target_missed",
                    "target_type": target_type,
                    "target": target,
                    "predicted_entities": entities,
                    "typed_predictions": typed_preds,
                }
            )

    precision = _safe_div(target_metrics.tp, target_metrics.tp + target_metrics.fp)
    recall = _safe_div(target_metrics.tp, target_metrics.tp + target_metrics.fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    hit_rate = _safe_div(target_metrics.hits, target_metrics.total)
    hit_at1_rate = _safe_div(target_metrics.hit_at1, target_metrics.total)
    hit_at2_rate = _safe_div(target_metrics.hit_at2, target_metrics.total)

    typo_hit_at1 = _safe_div(typo_metrics.hit_at1, typo_metrics.total)
    none_pass_rate = _safe_div(none_pass, none_total)

    print("KG Offline Benchmark")
    print(f"- backend: {cfg.DATA_BACKEND}")
    print(f"- cases: {len(cases)} total | {target_metrics.total} target | {none_total} no-entity")
    print("-")
    print("Target Extraction Metrics")
    print(f"- precision: {_pct(precision)}")
    print(f"- recall:    {_pct(recall)}")
    print(f"- f1:        {_pct(f1)}")
    print(f"- hit_rate:  {_pct(hit_rate)}")
    print(f"- hit@1:     {_pct(hit_at1_rate)}")
    print(f"- hit@2:     {_pct(hit_at2_rate)}")
    print("-")
    print("Special Buckets")
    print(f"- typo_well_hit@1: {_pct(typo_hit_at1)} ({typo_metrics.hit_at1}/{typo_metrics.total})")
    print(f"- no_entity_pass:  {_pct(none_pass_rate)} ({none_pass}/{none_total})")
    print("-")
    print("Per-Type Hit Rate")
    for etype in sorted(type_metrics.keys()):
        metrics = type_metrics[etype]
        etype_hit = _safe_div(metrics.hits, metrics.total)
        etype_hit1 = _safe_div(metrics.hit_at1, metrics.total)
        print(f"- {etype}: hit={_pct(etype_hit)} hit@1={_pct(etype_hit1)} n={metrics.total}")

    print("-")
    if misses:
        print(f"Miss Examples (showing up to {args.show_misses})")
        for row in misses[: args.show_misses]:
            print(
                json.dumps(
                    {
                        "id": row.get("id"),
                        "reason": row.get("reason"),
                        "query": row.get("query"),
                        "target_type": row.get("target_type"),
                        "target": row.get("target"),
                        "typed_predictions": row.get("typed_predictions"),
                        "predicted_entities": row.get("predicted_entities"),
                    },
                    ensure_ascii=False,
                )
            )
    else:
        print("Miss Examples: none")

    gates = {
        "min_f1": args.min_f1,
        "min_typo_hit_at1": args.min_typo_hit_at1,
    }
    gate_results = {
        "f1_pass": f1 >= args.min_f1,
        "typo_hit_at1_pass": typo_hit_at1 >= args.min_typo_hit_at1,
    }
    overall_pass = all(gate_results.values())

    print("-")
    print("Gate Check")
    print(f"- f1 >= {args.min_f1:.2f}: {gate_results['f1_pass']}")
    print(f"- typo_hit@1 >= {args.min_typo_hit_at1:.2f}: {gate_results['typo_hit_at1_pass']}")
    print(f"- overall: {overall_pass}")

    report = {
        "suite": "kg_entity_extraction_offline_suite_v1",
        "cases_path": str(args.cases),
        "summary": {
            "total_cases": len(cases),
            "target_cases": target_metrics.total,
            "no_entity_cases": none_total,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "hit_rate": hit_rate,
            "hit_at1_rate": hit_at1_rate,
            "hit_at2_rate": hit_at2_rate,
            "typo_well_hit_at1_rate": typo_hit_at1,
            "no_entity_pass_rate": none_pass_rate,
            "overall_pass": overall_pass,
        },
        "per_type": {
            etype: {
                "cases": m.total,
                "hit_rate": _safe_div(m.hits, m.total),
                "hit_at1_rate": _safe_div(m.hit_at1, m.total),
            }
            for etype, m in sorted(type_metrics.items())
        },
        "gates": gates,
        "gate_results": gate_results,
        "misses": misses,
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"- report_written: {args.report}")


if __name__ == "__main__":
    main()

