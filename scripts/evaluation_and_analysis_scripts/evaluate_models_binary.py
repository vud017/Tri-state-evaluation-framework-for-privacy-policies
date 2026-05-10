import argparse
import csv
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

"""
Binary collapsed evaluation script for LLM privacy policy annotation.

Extends the tri-state evaluation by collapsing ambiguous labels into false,
reducing the task to binary true vs not-true classification. This allows
direct comparison with binary classification benchmarks and isolates how
much of the difficulty in tri-state evaluation stems from ambiguity detection.

Compares model-generated JSON annotations against human researcher annotations
using two metrics:
  - Agreement rate: proportion of attributes with identical collapsed labels
  - Binary F1: one-vs-rest F1 per label (true/not-true), then averaged

Inputs:
  --ground_truth  : directory containing human-annotated JSON files (one per policy)
  --model_dirs    : one or more model result directories (each named after the model)
  --out           : output directory for CSV results

Outputs:
  - binary_results_per_model.csv        : overall binary metrics per model
  - binary_results_per_model_field.csv  : binary metrics broken down by attribute field
  - binary_results_per_policy.csv       : binary metrics broken down by policy per model

Usage:
  python evaluate_models_binary.py \
    --ground_truth human_annotations/ \
    --model_dirs results/anthropic__claude-opus-4-6 results/openai__gpt-5-4 ... \
    --out human_comparison_out/
"""


TRI_VALUES = ("true", "false", "ambiguous")
BINARY_VALUES = ("true", "not_true")

TRI_FIELDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("collected.detected",              ("collected", "detected")),
    ("stored.detected",                 ("stored", "detected")),
    ("shared.detected",                 ("shared", "detected")),
    ("shared.third_country_sharing",    ("shared", "third_country_sharing")),
    ("retention_policy.deletion",       ("retention_policy", "deletion")),
    ("retention_policy.inactivity",     ("retention_policy", "inactivity")),
    ("data_minimization.adequate",      ("data_minimization", "adequate")),
]

DATA_CATEGORIES = [
    "biometric_data",
    "health_data",
    "physiological_data",
    "physical_data",
    "behavioral_data",
]


# =========================
# UTILITY
# =========================

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


def collapse_to_binary(label: Optional[str]) -> Optional[str]:
    """Collapse tri-state label to binary: true stays true, false and ambiguous become not_true."""
    if label is None:
        return None
    if label == "true":
        return "true"
    if label in ("false", "ambiguous"):
        return "not_true"
    return None


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_policy_files(directory: str) -> List[str]:
    """List all JSON files in a directory, excluding metadata files."""
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


# =========================
# METRICS
# =========================

def agreement_rate(pairs: List[Tuple[str, str]]) -> float:
    """Proportion of (model, human) pairs with identical collapsed labels."""
    if not pairs:
        return float("nan")
    return sum(1 for m, e in pairs if m == e) / len(pairs)


def binary_f1(pairs: List[Tuple[str, str]]) -> Tuple[float, Dict[str, float]]:
    """
    Compute macro-averaged F1 using one-vs-rest formulation for binary labels.
    Returns (macro_f1_score, {label: f1_score}).
    """
    per_label_f1 = {}

    for label in BINARY_VALUES:
        tp = sum(1 for m, e in pairs if m == label and e == label)
        fp = sum(1 for m, e in pairs if m == label and e != label)
        fn = sum(1 for m, e in pairs if m != label and e == label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        if (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0

        per_label_f1[label] = f1

    macro = sum(per_label_f1.values()) / len(BINARY_VALUES)
    return macro, per_label_f1


# =========================
# MAIN EVALUATION
# =========================

def evaluate_model_binary(
    model_dir: str,
    gt_dir: str,
) -> Dict[str, Any]:
    """
    Evaluate a single model directory against the human annotation directory
    using binary collapsed labels (true vs not_true).
    """
    model_name = os.path.basename(model_dir)
    gt_files = set(list_policy_files(gt_dir))
    model_files = set(list_policy_files(model_dir))
    common_files = sorted(gt_files & model_files)

    if not common_files:
        print(f"  WARNING: No common policy files found for model '{model_name}'")
        return {}

    print(f"  Evaluating {model_name} on {len(common_files)} policies: {common_files}")

    all_pairs:                           List[Tuple[str, str]] = []
    pairs_by_field:  Dict[str, List]     = defaultdict(list)
    pairs_by_policy: Dict[str, List]     = defaultdict(list)

    for fname in common_files:
        policy_id = os.path.splitext(fname)[0]
        gt_doc    = load_json(os.path.join(gt_dir, fname))
        mod_doc   = load_json(os.path.join(model_dir, fname))

        for cat in DATA_CATEGORIES:
            for field_name, path_parts in TRI_FIELDS:
                gt_cat  = (gt_doc.get("data_categories") or {}).get(cat, {})
                mod_cat = (mod_doc.get("data_categories") or {}).get(cat, {})

                gt_tri  = normalize_tri(safe_get(gt_cat, path_parts))
                mod_tri = normalize_tri(safe_get(mod_cat, path_parts))

                if gt_tri not in TRI_VALUES or mod_tri not in TRI_VALUES:
                    continue

                gt_bin  = collapse_to_binary(gt_tri)
                mod_bin = collapse_to_binary(mod_tri)

                if gt_bin is None or mod_bin is None:
                    continue

                pair = (mod_bin, gt_bin)
                all_pairs.append(pair)
                pairs_by_field[field_name].append(pair)
                pairs_by_policy[policy_id].append(pair)

    macro, per_label = binary_f1(all_pairs)
    agr = agreement_rate(all_pairs)

    result = {
        "model":             model_name,
        "n_policies":        len(common_files),
        "n_pairs":           len(all_pairs),
        "agreement_rate":    agr,
        "macro_f1":          macro,
        "f1_true":           per_label["true"],
        "f1_not_true":       per_label["not_true"],
        "by_field":          {},
        "by_policy":         {},
    }

    for fld, pairs in pairs_by_field.items():
        m, pl = binary_f1(pairs)
        result["by_field"][fld] = {
            "n_pairs":        len(pairs),
            "agreement_rate": agreement_rate(pairs),
            "macro_f1":       m,
            "f1_true":        pl["true"],
            "f1_not_true":    pl["not_true"],
        }

    for pol, pairs in pairs_by_policy.items():
        m, pl = binary_f1(pairs)
        result["by_policy"][pol] = {
            "n_pairs":        len(pairs),
            "agreement_rate": agreement_rate(pairs),
            "macro_f1":       m,
            "f1_true":        pl["true"],
            "f1_not_true":    pl["not_true"],
        }

    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ground_truth", required=True,
                    help="Directory containing human researcher annotation JSON files.")
    ap.add_argument("--model_dirs", nargs="+", required=True,
                    help="One or more model result directories.")
    ap.add_argument("--out", required=True,
                    help="Output directory for CSV results.")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    all_results = []
    for model_dir in args.model_dirs:
        print(f"\nEvaluating: {model_dir}")
        res = evaluate_model_binary(model_dir, args.ground_truth)
        if res:
            all_results.append(res)

    if not all_results:
        raise SystemExit("No results to write. Check that model and human annotation directories share policy filenames.")

    # --- Output 1: Overall per model ---
    overall_rows = []
    for r in all_results:
        overall_rows.append({
            "model":          r["model"],
            "n_policies":     r["n_policies"],
            "n_pairs":        r["n_pairs"],
            "agreement_rate": round(r["agreement_rate"], 4),
            "macro_f1":       round(r["macro_f1"], 4),
            "f1_true":        round(r["f1_true"], 4),
            "f1_not_true":    round(r["f1_not_true"], 4),
        })
    write_csv(
        os.path.join(args.out, "binary_results_per_model.csv"),
        overall_rows,
        ["model", "n_policies", "n_pairs", "agreement_rate", "macro_f1",
         "f1_true", "f1_not_true"],
    )

    # --- Output 2: Per model per field ---
    field_rows = []
    for r in all_results:
        for fld, metrics in r["by_field"].items():
            field_rows.append({
                "model":          r["model"],
                "field":          fld,
                "n_pairs":        metrics["n_pairs"],
                "agreement_rate": round(metrics["agreement_rate"], 4),
                "macro_f1":       round(metrics["macro_f1"], 4),
                "f1_true":        round(metrics["f1_true"], 4),
                "f1_not_true":    round(metrics["f1_not_true"], 4),
            })
    write_csv(
        os.path.join(args.out, "binary_results_per_model_field.csv"),
        field_rows,
        ["model", "field", "n_pairs", "agreement_rate", "macro_f1",
         "f1_true", "f1_not_true"],
    )

    # --- Output 3: Per model per policy ---
    policy_rows = []
    for r in all_results:
        for pol, metrics in r["by_policy"].items():
            policy_rows.append({
                "model":          r["model"],
                "policy":         pol,
                "n_pairs":        metrics["n_pairs"],
                "agreement_rate": round(metrics["agreement_rate"], 4),
                "macro_f1":       round(metrics["macro_f1"], 4),
                "f1_true":        round(metrics["f1_true"], 4),
                "f1_not_true":    round(metrics["f1_not_true"], 4),
            })
    write_csv(
        os.path.join(args.out, "binary_results_per_policy.csv"),
        policy_rows,
        ["model", "policy", "n_pairs", "agreement_rate", "macro_f1",
         "f1_true", "f1_not_true"],
    )

    # --- Print summary ---
    print("\n===== BINARY EVALUATION SUMMARY (true vs not_true) =====")
    print(f"{'Model':<40} {'Agree':>8} {'MacroF1':>9} {'F1-true':>9} {'F1-not_true':>12}")
    print("-" * 82)
    for r in overall_rows:
        print(f"{r['model']:<40} {r['agreement_rate']:>8.4f} {r['macro_f1']:>9.4f} "
              f"{r['f1_true']:>9.4f} {r['f1_not_true']:>12.4f}")

    print(f"\nOutputs written to: {args.out}")


if __name__ == "__main__":
    main()
