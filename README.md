# Privacy Policy Analysis Framework

This repository contains the code and annotation data for a master's thesis investigating whether general purpose large language models (LLMs) can perform structured privacy policy assessment, with a focus on high-risk and sensitive data practices. 
The framework combines a predefined JSON assessment schema, a strict complementary system prompt, and a tri-state classification outcome (`true`, `false`, or `ambiguous`) rather than a binary one to assess how sensitive data categories are disclosed and governed within privacy policies.

---

## Repository Structure

```
my_master_scripts/
├── scripts/
│   ├── multi_step_policies_9.py          # Main pipeline script
│   ├── excel_to_json.py                  # Converts human annotations from Excel to JSON
│   └── evaluation_and_analysis_scripts/  # Evaluation and analysis scripts
│
├── policies_main_experiment/             # Privacy policy .txt files used in the study
├── policies/                             # Additional policy files
│
├── results/                              # Model output JSONs, organised by run and model
├── expert_annotation/                    # Human researcher annotations
│   └── completed/                        # Finalised annotations in JSON format
│
├── analysis_out/                         # All analysis and evaluation outputs
│   ├── consistency_out/                  # Outputs from consistency analysis
│   ├── evaluation_out/                   # Outputs from evaluation runs
│   ├── human_comparison_out/             # Model vs. human comparison outputs
│   └── output_csv/                       # CSV exports of results
│
├── .env                                  # API key - not committed
├── .gitignore
└── README.md
```

---

## How It Works

The pipeline splits each policy into six sequential model calls, one for metadata and one for each of the five sensitive data categories. All calls are made at temperature 0 to minimise output variation and support reproducibility.

Each call receives the full policy text and the specific JSON subsection to fill. Output passes through a two-stage validation process: first a sanitization step attempts to parse the response, then if that fails, a dedicated repair prompt is sent to the model. If both stages fail, the subsection is logged as an error and the pipeline moves on.

The five data categories assessed are:
F
*Defined in alignment with GDPR definitions:*
- Biometric data
- Health data

*Broader categories capturing sensitive data practices that may fall outside GDPR's stricter definitions:*
- Physiological data
- Physical data
- Behavioral data

For each category, the schema captures whether the data is collected, stored, shared, subject to a retention or deletion policy, and whether data minimization is adequately described. All fields use tri-state classification: `true`, `false`, or `ambiguous`.

---

## Requirements

Python 3.9 or later is recommended. Install the only required external dependency with:

```bash
pip install requests
```

---

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/vud017/Tri-state-evaluation-framework-for-privacy-policies.git
cd Tri-state-evaluation-framework-for-privacy-policies
```

**2. Set your OpenRouter API key**

You need an [OpenRouter](https://openrouter.ai) account and API key. It is recommended to store it in a `.env` file in the project root:

```
OPENROUTER_API_KEY=your_api_key_here
```

**3. Add your privacy policy files**

Use the existing policy txt files or place plain text `.txt` privacy policy files folder. `policies_main_experiment/` was used in this experiment. The pipeline will recursively find all `.txt` files in that folder and any subfolders.

---

## Running the Pipeline

Configure the following variables near the top of `scripts/multi_step_policies_9.py`:

```python
MODEL_NAME   = "anthropic/claude-sonnet-4-6"  # OpenRouter model identifier
POLICIES_DIR = "policies_main_experiment"       # Folder containing policy .txt files
RUN_ID       = "run_1"                          # Label for this run
```

Then run from the project root:

```bash
python scripts/multi_step_policies_9.py
```

Results are saved to `results/{RUN_ID}/{model_name}/`. Each policy produces two files:

- `{policy_name}.json` - the structured annotation output
- `{policy_name}_meta.json` - reproducibility metadata including model name, temperature, timestamp, and SHA-256 hashes of the policy text and prompt components

If a policy fails to process, an error file is written and the pipeline continues with the remaining policies.

---

## Human Annotation

Researcher annotations are stored in `expert_annotation/completed/` as JSON files. These were produced using a structured Excel template and converted to JSON using `scripts/excel_to_json.py`. The annotations follow the same schema as the model outputs, enabling direct comparison.

---

## Note

- **Results folder**: The `results/` folder is included for confirmation and comparison purposes. It can be safely deleted after cloning if you only intend to run the pipeline yourself.

