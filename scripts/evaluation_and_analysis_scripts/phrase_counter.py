import os
import re
import csv

# Config
POLICIES_DIR = "./policies"

PHRASES = [
    "may be shared",
    "may be used",
    "only as long as necessary",
    "as long as necessary",
    "legitimate interests",
    "may collect",
    "where appropriate",
    "in some cases",
    "as needed",
    "certain circumstances",
    "where necessary",
    "may include",
    
]

OUTPUT_DIR = "./output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "phrase_frequency.csv")

# Helper functions

def load_policies(policies_dir):
    """Load all .txt files from all subdirectories."""
    policies = {}
    for subfolder in os.listdir(policies_dir):
        subfolder_path = os.path.join(policies_dir, subfolder)
        if os.path.isdir(subfolder_path):
            for filename in os.listdir(subfolder_path):
                if filename.endswith(".txt"):
                    filepath = os.path.join(subfolder_path, filename)
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        policies[filename] = f.read().lower()
    return policies

def count_phrases(policies, phrases):
    """
    For each phrase, count:
    - Total occurrences across all policies
    - Number of policies containing the phrase at least once
    - Per policy occurrence counts
    """
    results = {}
    for phrase in phrases:
        total_occurrences = 0
        policies_containing = 0
        per_policy = {}
        for policy_name, text in policies.items():
            count = len(re.findall(re.escape(phrase.lower()), text))
            total_occurrences += count
            per_policy[policy_name] = count
            if count > 0:
                policies_containing += 1
        results[phrase] = {
            "total_occurrences": total_occurrences,
            "policies_containing": policies_containing,
            "per_policy": per_policy,
        }
    return results

def save_summary_csv(results, total_policies, output_file):
    """Save summary results to CSV."""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "phrase",
            "total_occurrences",
            "policies_containing",
            "total_policies",
            "pct_policies_containing",
        ])
        for phrase, data in sorted(
            results.items(),
            key=lambda x: x[1]["total_occurrences"],
            reverse=True,
        ):
            pct = round(data["policies_containing"] / total_policies * 100, 1)
            writer.writerow([
                phrase,
                data["total_occurrences"],
                data["policies_containing"],
                total_policies,
                pct,
            ])
    print(f"Summary CSV saved to {output_file}")

def save_per_policy_csv(results, output_dir):
    """Save per policy counts to a separate CSV."""
    per_policy_file = os.path.join(output_dir, "phrase_frequency_per_policy.csv")
    
    phrases = list(results.keys())
    policy_names = list(next(iter(results.values()))["per_policy"].keys())
    
    with open(per_policy_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["policy"] + phrases)
        for policy_name in sorted(policy_names):
            row = [policy_name] + [
                results[phrase]["per_policy"][policy_name] for phrase in phrases
            ]
            writer.writerow(row)
    print(f"Per policy CSV saved to {per_policy_file}")

def print_summary(results, total_policies):
    """Print a readable summary to the console."""
    print(f"\nPhrase frequency summary across {total_policies} policies:\n")
    print(f"{'Phrase':<35} {'Total':>8} {'Policies':>10} {'Pct':>8}")
    print("-" * 65)
    for phrase, data in sorted(
        results.items(),
        key=lambda x: x[1]["total_occurrences"],
        reverse=True,
    ):
        pct = round(data["policies_containing"] / total_policies * 100, 1)
        print(
            f"{phrase:<35} "
            f"{data['total_occurrences']:>8} "
            f"{data['policies_containing']:>10} "
            f"{pct:>7}%"
        )

# main
if __name__ == "__main__":
    print("Loading policies...")
    policies = load_policies(POLICIES_DIR)
    total_policies = len(policies)
    print(f"Loaded {total_policies} policies.")

    print("Counting phrases...")
    results = count_phrases(policies, PHRASES)

    print_summary(results, total_policies)
    save_summary_csv(results, total_policies, OUTPUT_FILE)
    save_per_policy_csv(results, OUTPUT_DIR)