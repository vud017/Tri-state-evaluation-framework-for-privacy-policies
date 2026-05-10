import os
import json
import requests
import hashlib
import time
from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout
from datetime import datetime, timezone
from copy import deepcopy

# =========================
# CONFIG
# =========================

# Should only be hardoded for testing/debugging purposes
#OPENROUTER_API_KEY = 

# API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model name
MODEL_NAME = "anthropic/claude-sonnet-4.6"

# Policy directory
POLICIES_DIR = "policies_main_experiment" 

#RESULTS_DIR = "archive/my_dataset/test_folder"
RUN_ID = "run_6"  # numeration for each specefic run
RESULTS_DIR = "results/" + RUN_ID + "/" + MODEL_NAME.replace("/", "__").replace(".", "-") # Output folder

def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# =========================
# BASE JSON TEMPLATE
# ============================

BASE_JSON_TEMPLATE = {
    "organization_name": "",
    "policy_date": "",
    "products_covered": [],

    "data_categories": {

        "biometric_data": {
            "collected": { "detected": "false", "policy_snippet": "", "purpose": "", "legal_basis": "" },
            "data_minimization": { "adequate": "false", "reasoning": "" },

            "stored": { "detected": "false", "policy_snippet": "", "purpose": "" },
            "retention_policy": {
                "deletion": "false",
                "policy_snippet_deletion": "",
                "inactivity": "false",
                "policy_snippet_inactivity": ""
            },

            "shared": {
                "detected": "false",
                "policy_snippet": "",
                "purpose": "",
                "legal_basis": "",
                "third_country_sharing": "false"
            },

            "overall_privacy_risk_description": ""
        },

        "health_data": {
            "collected": { "detected": "false", "policy_snippet": "", "purpose": "", "legal_basis": "" },
            "data_minimization": { "adequate": "false", "reasoning": "" },

            "stored": { "detected": "false", "policy_snippet": "", "purpose": "" },
            "retention_policy": {
                "deletion": "false",
                "policy_snippet_deletion": "",
                "inactivity": "false",
                "policy_snippet_inactivity": ""
            },

            "shared": {
                "detected": "false",
                "policy_snippet": "",
                "purpose": "",
                "legal_basis": "",
                "third_country_sharing": "false"
            },

            "overall_privacy_risk_description": ""
        },

        "physiological_data": {
            "collected": { "detected": "false", "policy_snippet": "", "purpose": "", "legal_basis": "" },
            "data_minimization": { "adequate": "false", "reasoning": "" },

            "stored": { "detected": "false", "policy_snippet": "", "purpose": "" },
            "retention_policy": {
                "deletion": "false",
                "policy_snippet_deletion": "",
                "inactivity": "false",
                "policy_snippet_inactivity": ""
            },

            "shared": {
                "detected": "false",
                "policy_snippet": "",
                "purpose": "",
                "legal_basis": "",
                "third_country_sharing": "false"
            },

            "overall_privacy_risk_description": ""
        },

        "physical_data": {
            "collected": { "detected": "false", "policy_snippet": "", "purpose": "", "legal_basis": "" },
            "data_minimization": { "adequate": "false", "reasoning": "" },

            "stored": { "detected": "false", "policy_snippet": "", "purpose": "" },
            "retention_policy": {
                "deletion": "false",
                "policy_snippet_deletion": "",
                "inactivity": "false",
                "policy_snippet_inactivity": ""
            },

            "shared": {
                "detected": "false",
                "policy_snippet": "",
                "purpose": "",
                "legal_basis": "",
                "third_country_sharing": "false"
            },

            "overall_privacy_risk_description": ""
        },

        "behavioral_data": {
            "collected": { "detected": "false", "policy_snippet": "", "purpose": "", "legal_basis": "" },
            "data_minimization": { "adequate": "false", "reasoning": "" },

            "stored": { "detected": "false", "policy_snippet": "", "purpose": "" },
            "retention_policy": {
                "deletion": "false",
                "policy_snippet_deletion": "",
                "inactivity": "false",
                "policy_snippet_inactivity": ""
            },

            "shared": {
                "detected": "false",
                "policy_snippet": "",
                "purpose": "",
                "legal_basis": "",
                "third_country_sharing": "false"
            },

            "overall_privacy_risk_description": ""
        }
    }
}


# ===========================
# SYSTEM PROMPT
# ========================

system_prompt = """
You are a GDPR expert and a user-centric privacy risk analyst.

INTERPRETATION GUIDELINES AND OUTPUT CONSTRAINTS
- Output ONLY a single valid JSON object, do not include Markdown code fences or text outside the JSON object.
- Do not add, remove, reorder, or rename any fields.
- Escape all double quotes inside JSON strings and do NOT include trailing commas.
- Base all answers ONLY on the provided policy text section, and do NOT infer actions or practices that are not explicitly stated in that policy text.
- Do NOT treat examples or definitions as proof of actual practices.
- Do NOT use any outside knowledge or assumptions.


TRI-STATE RULE 
For any field whose value must be evaluated as true/false/ambiguous (such as detected, adequate, deletion, inactivity, or third_country_sharing), you must choose one of the following values:
- "true"      = The policy explicitly states that the practice occurs.
- "ambiguous" = the practise is mentioned in the policy, but described in conditional, vague, or insufficiently language that prevents a definitive determination, using terms like: "may", "might", "could", "as needed", or missing  the scope/limits.
- "false"     = The practice is explicitly denied or not mentioned anywhere in the policy.


EVIDENCE RULES
- If a field is "true" or "ambiguous":
  - policy_snippet must be an exact quote from the relevant policy text (maximum 500 characters).
  - purpose or reasoning must be one or more factual sentences explaining how that exact snippet supports the value.
  - Do NOT paraphrase or modify the snippet.
- If a field is "false": 
  - leave policy_snippet="" and other explanatory fields empty.

DEFINITIONS OF DATA CATEGORIES
Use the following definitions when determining which category applies:

- Biometric data:
  Personal data resulting from specific technical processing of physical, physiological, or behavioral characteristics that allows or confirms the unique identification of an individual.
  Examples: Facial recognition templates, fingerprint templates, voiceprints used for identification, gait analysis patterns, keystroke dynamics patterns.
  
- Health data:
  Personal data concerning the physical or mental health of a person, including data collected in the course of the provision of health care services, which reveals information about their past, current, or future health status.
  Examples: Medical diagnoses, symptoms, prescriptions, treatment records, clinical test results, data from medical devices, disability health conditions, medical history, healthcare provider notes.

- Physiological data:
  Information about internal bodily functions or biological states of a person.  
  Examples: Heart rate, sleep patterns, respiration rate, body temperature, blood oxygen levels, stress levels, EEG signals, galvanic skin response, fitness tracking data, menstrual cycle data, emotional state indicators.

- Physical data:
  Information about a person’s external characteristics, appearance, or movements.
  Examples: Height, weight, body measurements, photographs, video recordings, voice recording, motion patterns, posture data, gait characteristics, location data, geolocation data or history.

- Behavioral data:
  Information that describes a person's actions, habits, preferences, lifestyle patterns, or patterns of interaction with a service or system.
  Examples:  App usage history, browsing patterns, clicks, purchase history, time spent on pages, search queries, interaction logs, content preferences, voice or virtual assistant interactions, wake/sleep times, daily routines, recurring habits.

MEANING OF EACH SUBFIELD
For every category, interpret fields as follows:

1) collected
- detected  (choose exactly one): 
    - "true" if the policy clearly states that this type of data is gathered, generated, or recorded.
    - "ambiguous" if the policy suggests collection in vague/conditional terms or unclear scope, using terms like: “may collect”, “might receive”, “can collect”, “as needed”, or if the data category is implied but not clearly stated.
    - "false" if the policy explicitly denies collecting this data type OR does not mention collecting it at all.
- policy_snippet: exact quote showing that the data is collected.
- purpose: short explanation of WHY the data is collected, based only on the text.
- legal_basis: the legal reason stated in the policy (e.g., consent, contract, legal obligation, legitimate interest).
  If no legal basis is stated, leave this field empty.

2) stored
- detected (choose exactly one): 
    - "true" only if the policy explicitly states that the data is retained, kept, maintained, or stored after collection.
    - "ambiguous" if the policy mentions storage or retention in vague or conditional terms like: "may retain", "might store", "as needed", "as necessary", "as long as needed/necessary".
    - "false" if the policy does not explicitly mention storage or retention of this data category.
- policy_snippet: exact quote that clearly refers to storage, retention, or keeping of the data.
- purpose: short explanation of why the data is stored.

3) shared 
- detected (choose exactly one):
    - "true" only if the policy explicitly states that the data is shared, disclosed, transferred, or provided to third parties.
    - "ambiguous" only if the policy states that the data may or might be shared with third parties, or describes sharing in vague or conditional terms.
    - "false" if the policy does not mention sharing this data category.
- policy_snippet: exact quote showing sharing.
- purpose: short explanation of why the data is shared.
- legal_basis: legal reason for sharing, if mentioned.
- third_country_sharing (choose exactly one): 
    - "true" if the policy explicitly states that data is transferred outside the user's country or region.
    - "ambiguous" if the policy states that data "may" or "might" be transferred internationally.
    - "false" if no cross-border transfer is mentioned.

4) retention_policy
- deletion (choose exactly one): 
    - "true" only if the policy explicitly states when, how, or under what conditions the data will be deleted or erased.
    - "ambiguous" if deletion is mentioned vaguely or conditionally without clear conditions/timing, terms like: “we may delete”, “we delete when appropriate”, “we retain as necessary” without deletion rules
    - "false" if the policy does not mention deletion or erasure for this data category.
- policy_snippet_deletion: exact quote that clearly refers to deletion, erasure, or removal of the data.
- inactivity (choose exactly one): 
    - "true" only if the policy explicitly states that data is automatically deleted, erased, or removed after a defined period of user inactivity, without the user needing to request deletion.
    - "ambiguous" if deletion by inactivity is mentioned but the mechanism/timing is unclear or not clearly automatic.
    - "false" if the policy does not mention automatic inactivity-based deletion.
- policy_snippet_inactivity: exact quote that clearly describes this automatic inactivity-based deletion.

5) data_minimization
- adequate (choose exactly one): 
    - "true" only if the policy clearly describes concrete and meaningful limits on what data is collected and provides a clear justification for why each type of data is necessary.
    - "ambiguous" if the policy contains only generic claims such as "we only collect what is necessary" or "we collect minimal data" without supporting specifics, limits, or examples.
    - "false" if the policy suggests collecting more data than necessary, describes broad or unlimited collection, or lacks meaningful limits.
- reasoning: one or a few short sentences explaining this judgment based only on what is found/missing from the policy text.

6) overall_privacy_risk_description
- Write 1–3 sentences summarizing the main privacy risks for this category, based only on the policy text.
- If no clear risk can be identified, leave this field empty.

"""

# =========================
# PER-SECTION PROMPT TEMPLATE
# =======================

SECTION_PROMPT_TEMPLATE = """
Below is the relevant section of the privacy policy you should use for this assessment:

----- BEGIN POLICY SECTION -----
{policy_section}
----- END POLICY SECTION -----

You must now fill ONLY the following JSON subsection:

{subsection_schema}

Instructions:
- Use ONLY the policy section shown above for evidence. Do not rely on outside knowledge.
- Preserve the exact JSON structure and fields shown in the subsection.
- All boolean-like fields must be "true", "false", or "ambiguous".
- Fill evidence and explanation fields exactly as defined in the schema (e.g., policy_snippet, purpose, legal_basis, reasoning).
- Output ONLY this updated subsection as a single JSON object (no Markdown, no extra text).
"""


REPAIR_SYSTEM_PROMPT = """
You are a JSON repair assistant.

You will receive:
- A target JSON schema (fields/structure that MUST be preserved).
- An invalid JSON fragment.

Your task:
- Output ONLY syntactically valid JSON matching the schema fields/structure.
- Do NOT change semantic values unless required to fix JSON syntax.
- Do NOT rewrite evidence/explanation text fields (e.g., policy_snippet, purpose, legal_basis, reasoning) except to escape characters or fix broken strings.
- If fields are missing, add them using schema defaults:
  - boolean-like fields: "false"
  - strings: ""
  - arrays: []
- No Markdown, no backticks, no extra text.
"""

REPAIR_PROMPT_TEMPLATE = """
You must repair the following JSON to make it syntactically valid and consistent with the schema.

JSON schema (structure and fields to follow):
{subsection_schema}

Invalid JSON that needs repair:
{invalid_json}

Instructions:
- Fix any syntax errors (unterminated strings, missing commas/braces, etc.).
- Ensure the output is valid JSON.
- Ensure all required fields from the schema exist in the output.
- Respond with ONLY the repaired JSON.
"""


# ========================
# SIMPLE OPENROUTER CALL
# ====================


def call_openrouter(system_prompt: str, user_prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }

    max_attempts = 5

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )

            print("\n------ OPENROUTER RESPONSE DEBUG ------")
            print("URL:     ", OPENROUTER_API_URL)
            print("Status:  ", resp.status_code)

            # Handle HTTP 429 code rate limit error
            if resp.status_code == 429:
                wait = 5 * attempt
                print(f"Got 429 Too Many Requests. Waiting {wait} seconds before retry...")
                time.sleep(wait)
                continue

            if resp.status_code in (500, 502, 503, 504):
                wait = 3 * attempt
                time.sleep(wait)
                continue

            # Raise for other non-2xx HTTP codes
            resp.raise_for_status()

            # Try to parse JSON
            try:
                data = resp.json()
            except Exception:
                print("Could not parse JSON, raw text:")
                print(resp.text[:1000])
                raise

            # Handle provider-level errors.
            if "error" in data:
                err = data["error"]
                msg = str(err.get("message", ""))
                code = err.get("code", None)
                print("Provider error from OpenRouter JSON:", err)

                # Decide if this error is retryable
                retryable = False
                if isinstance(code, int) and code >= 500:
                    retryable = True
                if "network" in msg.lower():
                    retryable = True

                if retryable and attempt < max_attempts:
                    wait = 3 * attempt
                    print(f"Retryable provider error (attempt {attempt}/{max_attempts}). "
                          f"Waiting {wait} seconds before retry...")
                    time.sleep(wait)
                    continue
                else:
                    raise RuntimeError(f"Non-retryable provider error from OpenRouter: {err}")

            # Normal success path: expect "choices"
            if "choices" not in data or not data["choices"]:
                print("Unexpected JSON structure:")
                print(json.dumps(data, indent=2)[:1000])
                raise RuntimeError("OpenRouter response missing 'choices'")

            return data["choices"][0]["message"]["content"].strip()

        except (ChunkedEncodingError, ConnectionError, ReadTimeout) as e:
            wait = 3 * attempt
            print(f"Network error ({type(e).__name__}: {e}). "
                  f"Retrying in {wait} seconds... [attempt {attempt}/{max_attempts}]")
            time.sleep(wait)
            continue

        except requests.HTTPError as e:
            # Non-429 HTTP error: show body and bail
            print("HTTPError from OpenRouter, not retrying.")
            try:
                print("Response body:", resp.text[:1000])
            except Exception:
                pass
            raise e

    # All attempts failed
    raise RuntimeError(f"Failed to call OpenRouter after {max_attempts} attempts.")


# =========================
# SUBSECTION ASSESSMENT
# =========================

def extract_json_from_model_output(raw: str) -> str:
    """
    Try to robustly extract a JSON object from the model output.
    Handles:
    - plain JSON
    - ```json ... ``` fenced blocks
    - leading/trailing text around a JSON object
    """
    text = raw.strip()

    # 1) Remove markdown fences if present
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    # 2) If it's still not clean JSON, try to extract the first {...} block
    if not text.lstrip().startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]

    return text.strip()

def sanitize_json_control_chars(s: str) -> str:
    """
    Replace bare control characters (newline, carriage return, tab) that appear
    *inside* JSON strings with escaped versions (\n, \r, \t), so json.loads won't fail.

    This does NOT try to be a full JSON parser, just a minimal state machine.
    """
    out = []
    in_string = False
    escape = False

    for ch in s:
        if escape:
            # previous char was backslash, so this char is escaped as-is
            out.append(ch)
            escape = False
            continue

        if ch == '\\':
            out.append(ch)
            escape = True
            continue

        if ch == '"':
            out.append(ch)
            in_string = not in_string  # toggle
            continue

        if in_string and ch in '\n\r\t':
            # replace control characters inside a string with escaped form
            if ch == '\n':
                out.append('\\n')
            elif ch == '\r':
                out.append('\\r')
            elif ch == '\t':
                out.append('\\t')
        else:
            out.append(ch)

    return ''.join(out)


def assess_subsection(policy_section_text: str, full_json: dict, subsection: dict) -> dict:
    """
    Calls the LLM for just one subsection, using ONLY the provided policy_section_text.
    `subsection` is a small dict (e.g. {"health_data": {...}}).
    Returns an updated version of that dict.
    """
    subsection_schema = json.dumps(subsection, indent=2)

    user_prompt = SECTION_PROMPT_TEMPLATE.format(
        policy_section=policy_section_text,
        subsection_schema=subsection_schema
    )

    # 1) First attempt: normal generation
    raw = call_openrouter(system_prompt, user_prompt)
    clean = extract_json_from_model_output(raw)
    clean = sanitize_json_control_chars(clean)

    try:
        parsed = json.loads(clean)
        return parsed
    except json.JSONDecodeError:
        print("Failed to parse JSON for subsection on first attempt.")
        print("Raw model output:")
        print(raw)
        print("\nCleaned candidate JSON string:")
        print(clean)

    # 2) Second attempt: repair using a dedicated prompt
    repair_user_prompt = REPAIR_PROMPT_TEMPLATE.format(
        subsection_schema=subsection_schema,
        invalid_json=clean
    )

    print("\n--- Attempting JSON repair for this subsection ---")
    repaired_raw = call_openrouter(REPAIR_SYSTEM_PROMPT, repair_user_prompt)
    repaired_clean = extract_json_from_model_output(repaired_raw)
    repaired_clean = sanitize_json_control_chars(repaired_clean)

    try:
        parsed_repaired = json.loads(repaired_clean)
        return parsed_repaired
    except json.JSONDecodeError as e:
        print("JSON repair attempt also failed.")
        print("Repaired raw output:")
        print(repaired_raw)
        print("\nRepaired cleaned candidate JSON:")
        print(repaired_clean)
        raise e


# =========================
# ASSESS A SINGLE POLICY
# =========================

def assess_single_policy(policy_text: str) -> dict:
    result = deepcopy(BASE_JSON_TEMPLATE)

    # 1) Meta
    meta_subsection = {
        "organization_name": result["organization_name"],
        "policy_date": result["policy_date"],
        "products_covered": result["products_covered"]
    }
    updated_meta = assess_subsection(policy_text, result, meta_subsection)
    result["organization_name"] = updated_meta["organization_name"]
    result["policy_date"] = updated_meta["policy_date"]
    result["products_covered"] = updated_meta["products_covered"]

    # 2) Data categories: one call per category
    data_cats = ["biometric_data", "health_data", "physiological_data", "physical_data", "behavioral_data"]
    for cat in data_cats:
        subsection = {cat: result["data_categories"][cat]}
        updated = assess_subsection(policy_text, result, subsection)
        result["data_categories"][cat] = updated[cat]

    return result


# =========================
# MAIN: PROCESS ALL POLICIES SEQUENTIALLY
# =========================

def main():
    if not os.path.isdir(POLICIES_DIR):
        raise RuntimeError(f"Policies folder '{POLICIES_DIR}' does not exist.")

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Recursively collect all .txt files inside policies/ and subfolders
    policy_files = []
    for root, dirs, files in os.walk(POLICIES_DIR):
        for f in files:
            if f.lower().endswith(".txt"):
                policy_files.append(os.path.join(root, f))

    if not policy_files:
        print(f"No .txt policy files found in '{POLICIES_DIR}' or its subfolders.")
        return

    print(f"Found {len(policy_files)} policy files to assess.")

    for policy_path in policy_files:
        filename = os.path.basename(policy_path)
        base_name, _ = os.path.splitext(filename)

        print(f"\n=== Assessing policy: {filename} ===")

        with open(policy_path, "r", encoding="utf-8") as f:
            policy_text = f.read()

        try:
           
            result_json = assess_single_policy(policy_text)

            # Save JSON using same base filename (but .json)
            out_path = os.path.join(RESULTS_DIR, f"{base_name}.json")
            with open(out_path, "w", encoding="utf-8") as out_f:
                json.dump(result_json, out_f, indent=2, ensure_ascii=False)

            print(f"Saved full JSON assessment to: {out_path}")

            # -------------------------
            # Save reproducibility metadata
            # -------------------------
            meta = {
                "timestamp_utc": utc_now_iso(),
                "model": MODEL_NAME,
                "temperature": 0,
                "policy_sha256": sha256_text(policy_text),
                "system_prompt_sha256": sha256_text(system_prompt),
                "section_prompt_template_sha256": sha256_text(SECTION_PROMPT_TEMPLATE),
                "openrouter_url": OPENROUTER_API_URL,
                "policy_path": policy_path,
            }

            meta_out_path = os.path.join(RESULTS_DIR, f"{base_name}_meta.json")
            with open(meta_out_path, "w", encoding="utf-8") as mf:
                json.dump(meta, mf, indent=2, ensure_ascii=False)

            print(f"Saved metadata to: {meta_out_path}")


        except Exception as e:
            # Do not kill the whole run, just log + optionally dump an error file
            print(f"!! Error while assessing policy '{filename}': {repr(e)}")
            error_out_path = os.path.join(RESULTS_DIR, f"{base_name}_ERROR.txt")
            try:
                with open(error_out_path, "w", encoding="utf-8") as err_f:
                    err_f.write(f"Error while assessing {filename}:\n{repr(e)}\n")
            except Exception as write_err:
                print(f"!! Additionally failed to write error file: {write_err}")
            # then continue with the next policy
            continue


if __name__ == "__main__":
    main()
