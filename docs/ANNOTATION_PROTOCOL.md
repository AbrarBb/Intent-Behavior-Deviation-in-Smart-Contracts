# Manual annotation protocol (ground truth)

## Purpose

`manual_annotations.csv` holds **human-adjudicated** labels for the pilot cohort (`contract_001` …). These labels support the **core scientific claim** that a model can detect **intent–behavior deviation**; weak labels copied only from external rug/benign lists are **not** sufficient as sole ground truth for a Q1 submission.

## Files

| File | Role |
|------|------|
| `manual_annotations_seed.csv` | Automated bootstrap from master binary labels (for pipeline testing only). |
| `manual_annotations.csv` | **Authoritative** file for Phases 5–8; must be reviewed before publication. |

**Current state:** `manual_annotations.csv` is initialized as a copy of the seed. **Replace** `final_label`, `intent_label`, and `behavior_label` after independent review.

## Columns

| Column | Description |
|--------|-------------|
| `contract_id` | Stable id (`contract_001` …); join key to `behavior_features.csv` and pilot folders. |
| `intent_text` | Text used for Sentence-BERT (typically from `pilot_data/.../text.txt` or your summary of claims). |
| `intent_label` | Short controlled vocabulary for **what the text claims** (e.g. `user_custody`, `fair_launch`, `safe_withdraw`). |
| `behavior_label` | Short code for **what the code allows** per protocol (e.g. `owner_withdraw`, `unrestricted_mint`, `user_control`). |
| `final_label` | **`rugpull`** or **`safe`** — **binary ground truth** for training (`07_build_ml_dataset.py`). |
| `reviewer_notes` | Rationale, citations to lines/functions, adjudication notes. |

## Review questions (yes/no → then label)

Answer per contract using `text.txt`, `functions.txt`, optional Slither output, and `code.sol`:

1. Does the text **promise** user safety, non-custodial control, or fair rules?
2. Is there **owner-only** or **privileged** withdrawal / rescue / mint without clear user consent?
3. Is there **emergency** or **backdoor**-style extraction?
4. **Decision rule (example):** if (1) is yes and (2) or (3) is yes → candidate **mismatch** → often **`rugpull`** for this task definition; refine per your IRB/ethics scope.

Document exact rules in your paper’s appendix; adjust for **benign** centralized admin patterns vs scams.

## Inter-rater agreement (recommended)

1. **Two annotators** independently fill `intent_label`, `behavior_label`, `final_label` on the **same** subset (e.g. 30–50 contracts).
2. Compute **Cohen’s κ** on `final_label` (binary or nominal agreement).
3. **Adjudication:** third reader or consensus meeting for disagreements; update `reviewer_notes`.

**Reporting:** κ value, % agreement, number of adjudicated cases.

## Data statement

- Store annotator IDs as initials or numeric codes in a **separate** non-public sheet if required by your institution.
- Do not put personally identifiable information in public CSVs.

## Sync with code

After editing `manual_annotations.csv`, re-run:

```text
python 05_embed_intent.py
python 06_extract_behavior_features.py
python 07_build_ml_dataset.py
python 08_train_models.py
python 11_run_ablation_experiments.py
```

Use `--use-seed` on Phases 5–7 only when intentionally testing automation without human labels.
