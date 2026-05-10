import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


LABELS = {"true", "false", "ambiguous"}

FIELDS_TO_COUNT = [
    ("collected", "detected"),
    ("stored", "detected"),
    ("shared", "detected"),
    ("shared", "third_country_sharing"),
    ("retention_policy", "deletion"),
    ("retention_policy", "inactivity"),
    ("data_minimization", "adequate"),
]


def normalize_label(value):
    if value is None:
        return None

    label = str(value).strip().lower()

    if label in LABELS:
        return label

    return None


def count_labels_in_policy(policy_json):
    counts = Counter()

    data_categories = policy_json.get("data_categories", {})

    for category_name, category_data in data_categories.items():
        if not isinstance(category_data, dict):
            continue

        for parent_key, child_key in FIELDS_TO_COUNT:
            parent = category_data.get(parent_key, {})

            if not isinstance(parent, dict):
                continue

            label = normalize_label(parent.get(child_key))

            if label in LABELS:
                counts[label] += 1

    return counts


def convert_model_name(folder_name):
    return folder_name.replace("__", "/").replace("-", " ")


def main():
    parser = argparse.ArgumentParser(
        description="Count true, false and ambiguous labels across model result JSON files."
    )
    parser.add_argument(
        "--results",
        default="results",
        help="Path to the results folder. Default: results"
    )
    parser.add_argument(
        "--output",
        default="label_counts.csv",
        help="Output CSV file. Default: label_counts.csv"
    )

    args = parser.parse_args()

    results_dir = Path(args.results)
    output_path = Path(args.output)

    if not results_dir.exists():
        raise FileNotFoundError(f"Results folder not found: {results_dir}")

    counts_by_model = defaultdict(Counter)
    counts_by_model_run = defaultdict(Counter)

    for run_dir in sorted(results_dir.glob("run_*")):
        if not run_dir.is_dir():
            continue

        run_name = run_dir.name

        for model_dir in sorted(run_dir.iterdir()):
            if not model_dir.is_dir():
                continue

            model_name = model_dir.name

            for json_file in sorted(model_dir.glob("*.json")):
                if json_file.name.endswith("_meta.json"):
                    continue

                try:
                    with json_file.open("r", encoding="utf-8") as f:
                        policy_json = json.load(f)
                except Exception as exc:
                    print(f"Skipping {json_file}: {exc}")
                    continue

                file_counts = count_labels_in_policy(policy_json)

                counts_by_model[model_name].update(file_counts)
                counts_by_model_run[(run_name, model_name)].update(file_counts)

    lines = []
    lines.append("model,true,false,ambiguous,total,true_pct,false_pct,ambiguous_pct")

    for model_name in sorted(counts_by_model):
        c = counts_by_model[model_name]
        total = c["true"] + c["false"] + c["ambiguous"]

        if total == 0:
            true_pct = false_pct = ambiguous_pct = 0
        else:
            true_pct = c["true"] / total * 100
            false_pct = c["false"] / total * 100
            ambiguous_pct = c["ambiguous"] / total * 100

        lines.append(
            f"{model_name},"
            f"{c['true']},"
            f"{c['false']},"
            f"{c['ambiguous']},"
            f"{total},"
            f"{true_pct:.2f},"
            f"{false_pct:.2f},"
            f"{ambiguous_pct:.2f}"
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nSaved label counts to: {output_path}\n")

    print("Label counts by model across all runs:")
    print("-" * 80)
    print(f"{'Model':45} {'True':>6} {'False':>6} {'Ambig':>6} {'Total':>6}")
    print("-" * 80)

    for model_name in sorted(counts_by_model):
        c = counts_by_model[model_name]
        total = c["true"] + c["false"] + c["ambiguous"]
        print(
            f"{model_name:45} "
            f"{c['true']:6} "
            f"{c['false']:6} "
            f"{c['ambiguous']:6} "
            f"{total:6}"
        )


if __name__ == "__main__":
    main()