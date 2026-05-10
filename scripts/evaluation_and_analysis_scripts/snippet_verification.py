"""
Snippet Grounding Verification Script

For each LLM output JSON, extracts all policy_snippet fields and checks
whether they can be found in the original policy text file after normalisation.
Normalisation includes:
  - Collapsing whitespace and newlines to single spaces
  - Stripping leading and trailing punctuation such as dashes, colons, semicolons
  - Handling ellipsis truncation by checking each part of a split snippet separately

Inputs:
  --results_dir  : Root directory containing run_1, run_2, ... subfolders
  --policies_dir : Directory containing original policy .txt files
  --run          : Which run to analyse (default: 1)
  --out          : Output directory for CSV results

Outputs:
  - snippet_verification.csv : One row per snippet with match result

Usage:
  python snippet_verification.py \
    --results_dir results/ \
    --policies_dir policies_main_experiment/ \
    --run 1 \
    --out snippet_out/

CSV columns:
  model, policy, category, field, snippet, found
"""

import argparse
import csv
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

DATA_CATEGORIES = [
    "biometric_data",
    "health_data",
    "physiological_data",
    "physical_data",
    "behavioral_data",
]

# Fields that contain policy snippets
SNIPPET_FIELDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("collected.policy_snippet",            ("collected", "policy_snippet")),
    ("stored.policy_snippet",               ("stored", "policy_snippet")),
    ("shared.policy_snippet",               ("shared", "policy_snippet")),
    ("retention_policy.policy_snippet_deletion",   ("retention_policy", "policy_snippet_deletion")),
    ("retention_policy.policy_snippet_inactivity", ("retention_policy", "policy_snippet_inactivity")),
]


def safe_get(d: Dict[str, Any], path: Tuple[str, ...]) -> Optional[str]:
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur if isinstance(cur, str) else None


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_policy_text(policies_dir: str, policy_filename: str) -> Optional[str]:
    """
    Search for the policy text file recursively within policies_dir.
    The policy filename is the JSON filename without extension.
    """
    policy_name = os.path.splitext(policy_filename)[0]
    for root, dirs, files in os.walk(policies_dir):
        for fname in files:
            if fname.lower().endswith(".txt"):
                stem = os.path.splitext(fname)[0].lower()
                if stem == policy_name.lower():
                    path = os.path.join(root, fname)
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
    return None


def verify_snippets(
    results_dir: str,
    policies_dir: str,
    run: int,
    out_dir: str,
) -> None:
    os.makedirs(out_dir, exist_ok=True)

    run_dir = os.path.join(results_dir, f"run_{run}")
    if not os.path.isdir(run_dir):
        raise SystemExit(f"Run directory not found: {run_dir}")

    models = sorted([
        d for d in os.listdir(run_dir)
        if os.path.isdir(os.path.join(run_dir, d))
    ])

    rows = []
    summary = {"total": 0, "found": 0, "not_found": 0, "empty": 0}

    for model in models:
        model_dir = os.path.join(run_dir, model)
        policy_files = sorted([
            f for f in os.listdir(model_dir)
            if f.lower().endswith(".json") and not f.lower().endswith("_meta.json")
        ])

        for policy_file in policy_files:
            policy_path = os.path.join(model_dir, policy_file)
            policy_name = os.path.splitext(policy_file)[0]

            # Load policy text
            policy_text = load_policy_text(policies_dir, policy_file)
            if policy_text is None:
                print(f"  WARNING: Could not find policy text for {policy_file}")
                continue

            # Load LLM JSON output
            try:
                data = load_json(policy_path)
            except Exception as e:
                print(f"  ERROR loading {policy_path}: {e}")
                continue

            for cat in DATA_CATEGORIES:
                cat_data = (data.get("data_categories") or {}).get(cat, {})
                if not cat_data:
                    continue

                for field_name, path_parts in SNIPPET_FIELDS:
                    snippet = safe_get(cat_data, path_parts)

                    if not snippet or snippet.strip() == "":
                        summary["empty"] += 1
                        rows.append({
                            "model": model,
                            "policy": policy_name,
                            "category": cat,
                            "field": field_name,
                            "snippet": "",
                            "found": "empty",
                        })
                        continue

                    snippet_stripped = snippet.strip()

                    # Normalise whitespace and quotes in policy text
                    policy_text_normalised = re.sub(r'\s+', ' ', policy_text)
                    policy_text_normalised = policy_text_normalised.replace('\u2018', "'").replace('\u2019', "'")
                    policy_text_normalised = policy_text_normalised.replace('\u201c', '"').replace('\u201d', '"')

                    def normalise(s: str) -> str:
                        # Collapse whitespace
                        s = re.sub(r'\s+', ' ', s)
                        # Strip leading/trailing quotation marks (straight and curly)
                        # Claude models sometimes wrap snippets in quotes
                        s = s.strip(' -:;\"\u201c\u201d\u2018\u2019')
                        # Normalise curly/smart quotes to straight quotes
                        s = s.replace('\u2018', "'").replace('\u2019', "'")
                        s = s.replace('\u201c', '"').replace('\u201d', '"')
                        return s

                    def check_match(snippet_text: str, policy_norm: str) -> bool:
                        # Try direct match after normalisation
                        s = normalise(snippet_text)
                        if s in policy_norm:
                            return True

                        # If snippet contains ellipsis, split and check each part
                        # appears within 250 characters of each other in the policy
                        if '...' in s:
                            parts = [p.strip() for p in s.split('...') if p.strip() and len(p.strip()) > 10]
                            if not parts:
                                return False
                            first = parts[0]
                            pos = policy_norm.find(first)
                            if pos == -1:
                                return False
                            current_pos = pos + len(first)
                            for part in parts[1:]:
                                window = policy_norm[current_pos:current_pos + 250]
                                part_pos = window.find(part)
                                if part_pos == -1:
                                    return False
                                current_pos = current_pos + part_pos + len(part)
                            return True

                        return False

                    found = check_match(snippet_stripped, policy_text_normalised)

                    summary["total"] += 1
                    if found:
                        summary["found"] += 1
                    else:
                        summary["not_found"] += 1

                    rows.append({
                        "model": model,
                        "policy": policy_name,
                        "category": cat,
                        "field": field_name,
                        "snippet": snippet_stripped,
                        "found": "true" if found else "false",
                    })

    # Write CSV
    out_path = os.path.join(out_dir, "snippet_verification.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["model", "policy", "category", "field", "snippet", "found"]
        )
        writer.writeheader()
        writer.writerows(rows)

    # Print summary
    total_checked = summary["found"] + summary["not_found"]
    match_rate = summary["found"] / total_checked if total_checked > 0 else 0

    print("\n===== SNIPPET VERIFICATION SUMMARY =====")
    print(f"Run:              run_{run}")
    print(f"Total snippets:   {total_checked}")
    print(f"Exact match:      {summary['found']} ({match_rate:.1%})")
    print(f"No match:         {summary['not_found']} ({1 - match_rate:.1%})")
    print(f"Empty snippets:   {summary['empty']}")
    print(f"\nResults written to: {out_path}")

    # Per model summary
    print("\n===== PER MODEL MATCH RATE =====")
    import pandas as pd
    df = pd.read_csv(out_path)
    df_checked = df[df['found'].isin(['true', 'false'])]
    per_model = df_checked.groupby('model').apply(
        lambda x: (x['found'] == 'true').sum() / len(x)
    ).round(4)
    for model, rate in per_model.items():
        print(f"  {model:<45} {rate:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True,
                        help="Root directory containing run_1, run_2, ... subfolders")
    parser.add_argument("--policies_dir", required=True,
                        help="Directory containing original policy .txt files")
    parser.add_argument("--run", type=int, default=1,
                        help="Which run to analyse (default: 1)")
    parser.add_argument("--out", required=True,
                        help="Output directory for CSV results")
    args = parser.parse_args()

    verify_snippets(
        results_dir=args.results_dir,
        policies_dir=args.policies_dir,
        run=args.run,
        out_dir=args.out,
    )
