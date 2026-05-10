"""
Converts a human-annotated Excel privacy policy annotation file
into the same JSON format produced by the LLM pipeline.

Usage:
    python excel_to_json.py --input <file.xlsx> --output <output.json>
"""

import argparse
import json
import re
import pandas as pd

SHEET_TO_CATEGORY = {
    "Biometric Data":     "biometric_data",
    "Health Data":        "health_data",
    "Physiological Data": "physiological_data",
    "Physical Data":      "physical_data",
    "Behavioral Data":    "behavioral_data",
}

ROW_TO_FIELD = {
    "Collected":                     "collected",
    "Data Minimization":             "data_minimization",
    "Stored":                        "stored",
    "Retention – Deletion":          "retention_policy_deletion",
    "Retention – Inactivity":        "retention_policy_inactivity",
    "Shared":                        "shared",
    "Overall Privacy Risk Description": "overall_privacy_risk_description",
}

LEAVE_EMPTY_VALUES = {"leave empty", "not stated", "nan", "none", ""}


def clean(val) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in LEAVE_EMPTY_VALUES:
        return ""
    return s


def normalize_tri(val) -> str:
    s = clean(val).lower()
    if s in ("true", "false", "ambiguous"):
        return s
    return "false"


def parse_sheet(df: pd.DataFrame) -> dict:
    """Parse a single category sheet into a category dict matching the JSON schema."""

    # Rows: index 1-7 (0 is header), columns mapped as:
    # col 1 = Data practice label
    # col 2 = Detected / tri-state value
    # col 3 = Data minimization adequate
    # col 4 = Policy snippet
    # col 5 = Purpose / Reasoning
    # col 6 = Legal basis
    # col 7 = Third country sharing

    rows = {}
    for i in range(1, 8):
        row = df.iloc[i]
        label = clean(row.iloc[1])
        field = ROW_TO_FIELD.get(label)
        if field:
            rows[field] = {
                "detected_or_value": clean(row.iloc[2]),
                "minimization_adequate": clean(row.iloc[3]),
                "snippet": clean(row.iloc[4]),
                "purpose": clean(row.iloc[5]),
                "legal_basis": clean(row.iloc[6]),
                "third_country": clean(row.iloc[7]),
            }

    cat = {
        "collected": {
            "detected": normalize_tri(rows.get("collected", {}).get("detected_or_value")),
            "policy_snippet": rows.get("collected", {}).get("snippet", ""),
            "purpose": rows.get("collected", {}).get("purpose", ""),
            "legal_basis": rows.get("collected", {}).get("legal_basis", ""),
        },
        "data_minimization": {
            "adequate": normalize_tri(rows.get("data_minimization", {}).get("minimization_adequate")),
            "reasoning": rows.get("data_minimization", {}).get("purpose", ""),
        },
        "stored": {
            "detected": normalize_tri(rows.get("stored", {}).get("detected_or_value")),
            "policy_snippet": rows.get("stored", {}).get("snippet", ""),
            "purpose": rows.get("stored", {}).get("purpose", ""),
        },
        "retention_policy": {
            "deletion": normalize_tri(rows.get("retention_policy_deletion", {}).get("detected_or_value")),
            "policy_snippet_deletion": rows.get("retention_policy_deletion", {}).get("snippet", ""),
            "inactivity": normalize_tri(rows.get("retention_policy_inactivity", {}).get("detected_or_value")),
            "policy_snippet_inactivity": rows.get("retention_policy_inactivity", {}).get("snippet", ""),
        },
        "shared": {
            "detected": normalize_tri(rows.get("shared", {}).get("detected_or_value")),
            "policy_snippet": rows.get("shared", {}).get("snippet", ""),
            "purpose": rows.get("shared", {}).get("purpose", ""),
            "legal_basis": rows.get("shared", {}).get("legal_basis", ""),
            "third_country_sharing": normalize_tri(rows.get("shared", {}).get("third_country")),
        },
        "overall_privacy_risk_description": rows.get("overall_privacy_risk_description", {}).get("purpose", ""),
    }

    return cat


def convert(input_path: str, output_path: str) -> None:
    xl = pd.ExcelFile(input_path)

    # Parse metadata
    meta_df = pd.read_excel(input_path, sheet_name="Metadata", header=None)
    org_name = clean(meta_df.iloc[1, 1])
    policy_date = clean(meta_df.iloc[2, 1])
    products_raw = clean(meta_df.iloc[3, 1])
    products = [] if not products_raw else [p.strip() for p in products_raw.split(",")]

    result = {
        "organization_name": org_name,
        "policy_date": policy_date,
        "products_covered": products,
        "data_categories": {},
    }

    for sheet_name, cat_key in SHEET_TO_CATEGORY.items():
        if sheet_name in xl.sheet_names:
            df = pd.read_excel(input_path, sheet_name=sheet_name, header=None)
            result["data_categories"][cat_key] = parse_sheet(df)
        else:
            print(f"WARNING: Sheet '{sheet_name}' not found, skipping.")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    convert(args.input, args.output)
