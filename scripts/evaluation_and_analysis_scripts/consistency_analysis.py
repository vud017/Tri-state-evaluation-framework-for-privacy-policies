"""
Consistency analysis script for LLM privacy policy annotation.

Measures intra-model consistency by comparing outputs across multiple repeated runs
of the same model on the same privacy policies.

For each model, for each policy, for each schema field:
- Collects the label assigned in each run
- Computes the proportion of fields where all runs agree (strict consistency)
- Also computes pairwise agreement rate across all run combinations

Inputs:
  --results_dir : root directory containing run_1, run_2, ... subfolders
  --runs        : number of runs to compare (default: 5)
  --out         : output directory for CSV results

Outputs:
  - consistency_per_model.csv       : overall consistency per model
  - consistency_per_field.csv       : consistency broken down by schema field
  - consistency_per_policy.csv      : consistency broken down by policy per model

Usage:
  python consistency_analysis.py \
    --results_dir results/ \
    --runs 5 \
    --out consistency_out/
"""

import argparse
import csv
import json
import os
from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

TRI_VALUES = ("true", "false", "ambiguous")

TRI_FIELDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("collected.detected",           ("collected", "detected")),
    ("stored.detected",              ("stored", "detected")),
    ("shared.detected",              ("shared", "detected")),
    ("shared.third_country_sharing", ("shared", "third_country_sharing")),
    ("retention_policy.deletion",    ("retention_policy", "deletion")),
    ("retention_policy.inactivity",  ("retention_policy", "inactivity")),
    ("data_minimization.adequate",   ("data_minimization", "adequate")),
]

DATA_CATEGORIES = [
    "biometric_data",
    "health_data",
    "physiological_data",
    "physical_data",
    "behavioral_data",
]


def safe_get(d: Dict[str, Any], path_parts: Tuple[str, ...]) -> Optional[Any]:
    cur: Any = d
    for p in path_parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def normalize_tri(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        s = v.strip().lower()
        if s in TRI_VALUES:
            return s
    return None


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_policy_files(directory: str) -> List[str]:
    files = []
    for name in sorted(os.listdir(directory)):
        if name.lower().endswith(".json") and not name.lower().endswith("_meta.json"):
            files.append(name)
    return files


def write_csv(path: str, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def strict_agreement(labels: List[str]) -> bool:
    """Returns True if all labels in the list are identical."""
    return len(set(labels)) == 1


def pairwise_agreement_rate(labels: List[str]) -> float:
    """Computes pairwise agreement rate across all combinations of runs."""
    pairs = list(combinations(labels, 2))
    if not pairs:
        return float("nan")
    return sum(1 for a, b in pairs if a == b) / len(pairs)



def analyze_model_consistency(
    model_name: str,
    run_dirs: List[str],
) -> Dict[str, Any]:
    """
    Analyze consistency for a single model across multiple run directories.
    """
    # Find policy files common to all runs
    all_policy_sets = []
    for run_dir in run_dirs:
        model_dir = os.path.join(run_dir, model_name)
        if os.path.isdir(model_dir):
            all_policy_sets.append(set(list_policy_files(model_dir)))
        else:
            print(f"  WARNING: {model_dir} not found, skipping this run.")
            all_policy_sets.append(set())

    common_policies = sorted(set.intersection(*all_policy_sets)) if all_policy_sets else []

    if not common_policies:
        print(f"  WARNING: No common policy files found for model '{model_name}'")
        return {}

    available_runs = [
        os.path.join(run_dir, model_name)
        for run_dir in run_dirs
        if os.path.isdir(os.path.join(run_dir, model_name))
    ]

    print(f"  {model_name}: {len(available_runs)} runs, {len(common_policies)} policies")

    # Collect labels across runs for each (policy, category, field)
    strict_counts = {"total": 0, "agree": 0}
    pairwise_scores = []

    field_strict: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "agree": 0})
    field_pairwise: Dict[str, List[float]] = defaultdict(list)

    policy_strict: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "agree": 0})
    policy_pairwise: Dict[str, List[float]] = defaultdict(list)

    for fname in common_policies:
        policy_id = os.path.splitext(fname)[0]

        # Load all run documents for this policy
        run_docs = []
        for run_model_dir in available_runs:
            path = os.path.join(run_model_dir, fname)
            if os.path.exists(path):
                run_docs.append(load_json(path))

        if len(run_docs) < 2:
            continue

        for cat in DATA_CATEGORIES:
            for field_name, path_parts in TRI_FIELDS:
                labels = []
                for doc in run_docs:
                    cat_data = (doc.get("data_categories") or {}).get(cat, {})
                    val = normalize_tri(safe_get(cat_data, path_parts))
                    if val in TRI_VALUES:
                        labels.append(val)

                if len(labels) < 2:
                    continue

                is_strict = strict_agreement(labels)
                pw = pairwise_agreement_rate(labels)

                strict_counts["total"] += 1
                if is_strict:
                    strict_counts["agree"] += 1
                pairwise_scores.append(pw)

                field_strict[field_name]["total"] += 1
                if is_strict:
                    field_strict[field_name]["agree"] += 1
                field_pairwise[field_name].append(pw)

                policy_strict[policy_id]["total"] += 1
                if is_strict:
                    policy_strict[policy_id]["agree"] += 1
                policy_pairwise[policy_id].append(pw)

    overall_strict = (
        strict_counts["agree"] / strict_counts["total"]
        if strict_counts["total"] > 0 else float("nan")
    )
    overall_pairwise = (
        sum(pairwise_scores) / len(pairwise_scores)
        if pairwise_scores else float("nan")
    )
    return {
        "model": model_name,
        "n_runs": len(available_runs),
        "n_policies": len(common_policies),
        "strict_agreement_rate": overall_strict,
        "pairwise_agreement_rate": overall_pairwise,
        "by_field": {
            f: {
                "strict_agreement_rate": (
                    field_strict[f]["agree"] / field_strict[f]["total"]
                    if field_strict[f]["total"] > 0 else float("nan")
                ),
                "pairwise_agreement_rate": (
                    sum(field_pairwise[f]) / len(field_pairwise[f])
                    if field_pairwise[f] else float("nan")
                ),
            }
            for f in [fn for fn, _ in TRI_FIELDS]
        },
        "by_policy": {
            os.path.splitext(p)[0]: {
                "strict_agreement_rate": (
                    policy_strict[os.path.splitext(p)[0]]["agree"] / policy_strict[os.path.splitext(p)[0]]["total"]
                    if policy_strict[os.path.splitext(p)[0]]["total"] > 0 else float("nan")
                ),
                "pairwise_agreement_rate": (
                    sum(policy_pairwise[os.path.splitext(p)[0]]) / len(policy_pairwise[os.path.splitext(p)[0]])
                    if policy_pairwise[os.path.splitext(p)[0]] else float("nan")
                ),
            }
            for p in common_policies
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", required=True,
                    help="Root directory containing run_1, run_2, ... subfolders.")
    ap.add_argument("--runs", type=int, default=5,
                    help="Number of runs to compare (default: 5).")
    ap.add_argument("--out", required=True,
                    help="Output directory for CSV results.")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Build list of run directories
    run_dirs = []
    for i in range(1, args.runs + 1):
        run_path = os.path.join(args.results_dir, f"run_{i}")
        if os.path.isdir(run_path):
            run_dirs.append(run_path)
        else:
            print(f"WARNING: run_{i} not found at {run_path}, skipping.")

    if len(run_dirs) < 2:
        raise SystemExit("Need at least 2 run directories to compute consistency.")

    print(f"Found {len(run_dirs)} run directories: {run_dirs}")

    # Discover models from run_1
    first_run = run_dirs[0]
    models = sorted([
        d for d in os.listdir(first_run)
        if os.path.isdir(os.path.join(first_run, d))
    ])

    print(f"Found {len(models)} models: {models}\n")

    all_results = []
    for model in models:
        print(f"Analyzing: {model}")
        result = analyze_model_consistency(model, run_dirs)
        if result:
            all_results.append(result)

    if not all_results:
        raise SystemExit("No results to write.")

    # Output 1: Overall per model
    model_rows = []
    for r in all_results:
        model_rows.append({
            "model": r["model"],
            "n_runs": r["n_runs"],
            "n_policies": r["n_policies"],
            "strict_agreement_rate": round(r["strict_agreement_rate"], 4),
            "pairwise_agreement_rate": round(r["pairwise_agreement_rate"], 4),
        })
    write_csv(
        os.path.join(args.out, "consistency_per_model.csv"),
        model_rows,
        ["model", "n_runs", "n_policies", "strict_agreement_rate", "pairwise_agreement_rate"],
    )

    # Output 2: Per model per field
    field_rows = []
    for r in all_results:
        for field, metrics in r["by_field"].items():
            field_rows.append({
                "model": r["model"],
                "field": field,
                "strict_agreement_rate": round(metrics["strict_agreement_rate"], 4),
                "pairwise_agreement_rate": round(metrics["pairwise_agreement_rate"], 4),
            })
    write_csv(
        os.path.join(args.out, "consistency_per_field.csv"),
        field_rows,
        ["model", "field", "strict_agreement_rate", "pairwise_agreement_rate"],
    )

    # Output 3: Per model per policy
    policy_rows = []
    for r in all_results:
        for policy, metrics in r["by_policy"].items():
            policy_rows.append({
                "model": r["model"],
                "policy": policy,
                "strict_agreement_rate": round(metrics["strict_agreement_rate"], 4),
                "pairwise_agreement_rate": round(metrics["pairwise_agreement_rate"], 4),
            })
    write_csv(
        os.path.join(args.out, "consistency_per_policy.csv"),
        policy_rows,
        ["model", "policy", "strict_agreement_rate", "pairwise_agreement_rate"],
    )

    # Print summary
    print("\n===== CONSISTENCY SUMMARY =====")
    print(f"{'Model':<45} {'Strict':>8} {'Pairwise':>10}")
    print("-" * 65)
    for r in model_rows:
        print(f"{r['model']:<45} {r['strict_agreement_rate']:>8.4f} {r['pairwise_agreement_rate']:>10.4f}")

    print(f"\nOutputs written to: {args.out}")


if __name__ == "__main__":
    main()
