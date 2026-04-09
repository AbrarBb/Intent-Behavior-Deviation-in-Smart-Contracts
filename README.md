# Intent–Behavior Deviation in Smart Contracts

Reproducible data preparation and research utilities for studying **rug-pull–style mismatches** between **claimed intent** (natural language in comments and documentation) and **observable behavior** (static analysis, heuristics). This repository supports a Q1-style methodology pipeline: balanced Ethereum corpora, verified source acquisition, manifest construction, pilot cohort layout, hybrid NLP + program-analysis features, model training, and a Streamlit prototype.

---

## Table of contents

1. [Research framing](#research-framing)
2. [Contribution and novelty](#contribution-and-novelty)
3. [Prerequisites](#prerequisites)
4. [Repository layout](#repository-layout)
5. [Input data](#input-data-you-provide)
6. [Pipeline overview](#pipeline-overview)
7. [Phase-by-phase usage](#phase-by-phase-usage)
8. [Etherscan API (V2)](#etherscan-api-v2)
9. [Outputs and artifacts (summary table)](#outputs-and-artifacts-summary-table)
10. [Output schemas (columns and how they help)](#output-schemas-columns-and-how-they-help)
11. [Training and evaluation (how to train models)](#training-and-evaluation-how-to-train-models)
12. [Reproducibility](#reproducibility)
13. [Limitations and disclosure](#limitations-and-disclosure)
14. [Security notes](#security-notes)
15. [License and citation](#license-and-citation)

16. [Paper completion package (Q1)](#paper-completion-package-q1)

---

## Paper completion package (Q1)

Structured materials for writing and submission (see the roadmap in `docs/`):

| Document | Purpose |
|----------|---------|
| [docs/CONTRIBUTIONS.md](docs/CONTRIBUTIONS.md) | Contribution bullets and gap vs. related work |
| [docs/ANNOTATION_PROTOCOL.md](docs/ANNOTATION_PROTOCOL.md) | Ground-truth labeling, inter-rater workflow |
| [docs/COHORT_TABLES.md](docs/COHORT_TABLES.md) | Frozen verified vs balanced cohort statistics |
| [docs/THREATS_TO_VALIDITY.md](docs/THREATS_TO_VALIDITY.md) | Threats, limitations, ethics |
| [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) | Environment, citations, Zenodo placeholder |
| [docs/MANUSCRIPT_STRUCTURE.md](docs/MANUSCRIPT_STRUCTURE.md) | Section outline and venue shortlist |
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | Full methodology (Methods section) with script and artifact mapping |
| [requirements-frozen.txt](requirements-frozen.txt) | Pinned dependencies from `pip freeze` (regenerate before archive) |
| [11_run_ablation_experiments.py](11_run_ablation_experiments.py) | Hybrid / intent / behavior / no-Slither ablations → `artifacts/ablation_report.md` |

`manual_annotations.csv` is the working annotation file (initialized from the seed); replace labels after human review per `docs/ANNOTATION_PROTOCOL.md`.

**Phase 4** optional flags: `--from-verified-full`, `--from-verified-balanced`, or `--manifest path/to.csv`.

---

## Research framing

- **Intent:** Textual signals (NatSpec, comments) about what users are told the contract does.
- **Behavior:** What the bytecode-level / analysis-level story allows (Slither detectors, regex heuristics for privileged flows).
- **Task:** Binary characterization (e.g. malicious vs benign at the *dataset* level, plus pilot **rugpull** vs **safe** after manual review).

The **master** split is label-balanced by construction; **verified source** availability on Etherscan is not guaranteed for every address, so downstream analyses should report both **manifest size** and **labeled-with-source** counts. After Phase 3, run **`10_verified_source_cohorts.py`** to emit **`verified_manifest.csv`** (all analyzable contracts with **true** class counts), **`verified_manifest_balanced_seed42.csv`** (fair 50/50 among verified only), and **`verified_cohort_report.txt`** for the paper.

---

## Contribution and novelty

Many prior works treat **natural language** (comments, documentation) and **code analysis** (static analyzers, auditors) as **separate** tracks. This repository supports a **hybrid, paired** view on the **same contract instance**:

| Layer | What it captures | Typical use in related work |
|-------|------------------|-----------------------------|
| **Intent** | Dense embedding of NatSpec / comments (`intent_text`) | NLP on specs or forums, often **without** executable grounding |
| **Behavior** | Privileged-flow heuristics + Slither detector signals | Vulnerability catalogs, often **without** the user-facing claims |

**What is distinctive for a Q1-style claim:** you can define **intent–behavior deviation** operationally—for example, textual assurances of user custody or fairness **coexisting with** indicators of owner-only withdrawal, unconstrained mint surfaces, or Slither flags associated with dangerous value transfer—then **learn** a boundary from data instead of relying solely on hand-crafted rules.

**How the outputs help you argue novelty:**

1. **`dataset_manifest.csv`**, **`verified_manifest.csv`**, and **`verified_cohort_report.txt`** let you report **exactly** how many contracts are analyzable end-to-end and the **real** benign vs malicious ratio among verified contracts, plus an optional balanced verified subset for model comparisons.
2. **`manual_annotations.csv`** (your reviewed copy) is the **audit trail** reviewers trust: you fixed an explicit protocol (intent vs behavior categories) and produced **ground truth** independent of the automated features.
3. **`ml_dataset.npz` / `ml_dataset.csv`** show the model consumes **both** semantic intent (384-d MiniLM) **and** behavioral structure (tabular flags)—not text alone and not bytecode-only tools alone.
4. **Ablations** you can report in the paper: embeddings-only vs behavior-only vs hybrid; with vs without Slither columns; manual vs seed labels—each supported by re-running Phases 5–8 with toggled columns (after a small edit to `07_build_ml_dataset.py` if you want to drop feature groups).

---

## Prerequisites

- **Python** 3.10+ recommended (3.14 has been used successfully in this project).
- **Core data phase:** `pandas` (install with `pip install pandas` if needed).
- **Research phase (optional):** see [`requirements-research.txt`](requirements-research.txt) for `sentence-transformers`, `scikit-learn`, `streamlit`, `slither-analyzer`, etc.

All scripts resolve paths relative to **the directory containing the script**, so you may run them from any working directory.

---

## Repository layout

| Item | Description |
|------|--------------|
| `rugpull_full_dataset_new (1).csv` | Malicious / incident contracts (must include `Chain`, `address`). |
| `all_contract.csv` | Benign addresses, **no header**; column 0 = address, column 1 = tx count. |
| `01_build_master_dataset.py` | Phase 1: balanced `master_dataset.csv`. |
| `02_download_contracts.py` | Phase 2: Etherscan verified source → `raw_data/<address>/`. |
| `03_build_dataset_manifest.py` | Phase 3: join labels + paths → `dataset_manifest.csv`. |
| `04_prepare_pilot_100.py` | Pilot: 100 contracts, `code.sol` / `text.txt` / `functions.txt`. |
| `05_embed_intent.py` | Sentence-BERT embeddings for intent text. |
| `06_extract_behavior_features.py` | Slither JSON + regex behavior features. |
| `07_build_ml_dataset.py` | Merge embeddings + features + labels → `ml_dataset.npz`. |
| `08_train_models.py` | Sklearn baselines; saves `best_model.joblib`. |
| `09_export_kaggle_csvs.py` | Flat CSVs for Kaggle / supplementary material. |
| `10_verified_source_cohorts.py` | Full verified CSV + seed-42 balanced verified CSV + cohort report. |
| `11_run_ablation_experiments.py` | Ablation metrics → `artifacts/ablation_report.md`, `ablation_results.json`. |
| `docs/*.md` | Paper: contributions, protocol, cohorts, threats, reproducibility, outline. |
| `solidity_extract.py` | Shared comment / function extraction and regex flags. |
| `streamlit_app.py` | Prototype scorer (intent + code paste). |
| `manual_annotations.template.csv` | Schema example for human annotations. |
| `pilot_data/` | Standardized per-contract folders (after Phase 4). |
| `raw_data/` | Downloaded `.sol` trees (after Phase 2). |
| `artifacts/` | Embeddings, behavior CSVs, NPZ/CSV ML tables, trained model. |

---

## Input data (collected)

1. **`rugpull_full_dataset_new (1).csv`**  
   - Header row required.  
   - Filter in Phase 1: **`Chain == "ETH"`** only.  
   - Uses column **`address`**; malicious rows receive **`label = 1`**.

2. **`all_contract.csv`**  
   - **No header.**  
   - Column 0 renamed to **`address`**, column 1 to **`tx_count`**.  
   - Sampled benign set receives **`label = 0`**, size matched to ETH rug-pull count.

If benign rows are insufficient, Phase 1 raises a clear error.

---

## Pipeline overview

```text
[Raw CSVs] --> 01 master_dataset.csv
           --> 02 raw_data/<address>/*.sol
           --> 03 dataset_manifest.csv
           --> 10 verified_manifest.csv + verified_manifest_balanced_seed42.csv + report
           --> 04 pilot_data/ + manual_annotations_seed.csv
           --> 05 intent embeddings
           --> 06 behavior_features.csv
           --> 07 ml_dataset.npz (+ meta CSV)
           --> 09 ml_dataset.csv + intent_vectors.csv (optional)
           --> 08 trained model
           --> streamlit_app.py (demo)
```

---

## Phase-by-phase usage

### Phase 1: Data balancing

```bash
python 01_build_master_dataset.py
```

**Behavior:**

- Keeps **Ethereum** rug pulls only (`Chain == "ETH"`).  
- Samples the **same number** of benign rows from `all_contract.csv` with `random_state=42`.  
- Concatenates **`address`** + **`label`** only, shuffles with **`random_state=42`**.  
- Writes **`master_dataset.csv`** (no index).

**Console:** prints counts for malicious, safe, and total.

---

### Phase 2: Data acquisition (Etherscan)

1. Set your API key as an environment variable (recommended):

```powershell
# Windows PowerShell (current session)
$env:ETHERSCAN_API_KEY = "your_key_here"
```

```bash
# macOS / Linux
export ETHERSCAN_API_KEY="your_key_here"
```

`02_download_contracts.py` reads **`ETHERSCAN_API_KEY`** and defaults to **`YOUR_KEY_HERE`** if unset. See [Security notes](#security-notes).

2. Run:

```bash
python 02_download_contracts.py
```

**Behavior:**

- Reads **`master_dataset.csv`**.  
- Creates **`raw_data/`**.  
- For each address: **`getsourcecode`** via **Etherscan API V2** (see below).  
- On success with non-empty **`SourceCode`**: writes `raw_data/<address>/<ContractName>.sol` (or **`Contract.sol`** if name missing).  
- **`time.sleep(0.25)`** after **every** HTTP call (≤ 4 calls/s).  
- Exceptions and empty/unverified sources: **warning + continue** (no crash).  
- Progress: **`[i/N] Fetched 0x... successfully -> ...`** with **`flush=True`**.

**Duration:** For thousands of addresses, expect **tens of minutes to well over an hour** depending on network and API behavior.

---

### Phase 3: Dataset manifest

```bash
python 03_build_dataset_manifest.py
```

Joins **`master_dataset.csv`** with **`raw_data/<address>/*.sol`**: produces **`dataset_manifest.csv`** with `address`, `label`, `sol_path`, `has_verified_source`.

Use this table to report **how many contracts have analyzable source** vs listed-only.

---

### Phase 10: Verified-source cohorts (true counts + balanced subset)

```bash
python 10_verified_source_cohorts.py
```

**Inputs:** `dataset_manifest.csv`  
**Outputs:**

| File | Purpose |
|------|---------|
| `verified_manifest.csv` | All rows with `has_verified_source == 1`. **True** benign (`label=0`) vs malicious (`label=1`) counts—use this for the **core** analyzable-corpus claim. |
| `verified_manifest_balanced_seed42.csv` | Exactly **min(n_benign, n_malicious)** rows **per class**, sampled with `random_state=42`, then shuffled (same seed). Use for **fair model comparisons** or a “50/50 among verified” experimental setting. **Drops** the surplus rows from the majority class; disclose **how many** (see `verified_cohort_report.txt`). |
| `verified_cohort_report.txt` | Copy-ready counts, imbalance ratio, and file names for Methods / appendix. |

**Paper workflow:** Report **Table A** (full verified cohort counts) and optionally **Table B** (balanced verified subsample size). Primary descriptive statistics and threat discussion should reference **Table A**; head-to-head baselines may use **Table B** plus `class_weight` on Table A as a sensitivity analysis.

---

### Phase 4: Pilot cohort (100 contracts, paper layout)

```bash
python 04_prepare_pilot_100.py
```

- Samples up to **50/50** verified contracts (from `dataset_manifest.csv` where `has_verified_source == 1`).  
- Writes **`pilot_data/contract_XXX/{code.sol,text.txt,functions.txt}`**.  
- Writes **`pilot_manifest.csv`** and **`manual_annotations_seed.csv`**.

**Ground truth for publication:** Copy the seed to **`manual_annotations.csv`**, fill **`intent_label`**, **`behavior_label`**, and **`final_label`** (`rugpull` | `safe`) from your protocol; the seed’s **`final_label`** is only a bootstrap from the master binary label.

---

### Phase 5: Intent embeddings (Sentence Transformers)

```bash
python 05_embed_intent.py
# or, before manual_annotations.csv exists:
python 05_embed_intent.py --use-seed
```

Uses **`all-MiniLM-L6-v2`** (384 dimensions). Outputs under **`artifacts/`**: `intent_embeddings.npy`, `intent_contract_ids.json`.

---

### Phase 6: Behavior features (Slither + regex)

```bash
python 06_extract_behavior_features.py
```

Requires **`pilot_data/`** and (for full value) **`slither`** on `PATH` plus matching **`solc`** for contract pragmas. On failure, **`slither_ok=0`** but regex-based columns still populate.

---

### Phase 7: Merged ML matrix (NPZ)

```bash
python 07_build_ml_dataset.py --use-seed
# After you finalize manual annotations:
python 07_build_ml_dataset.py
```

Writes **`artifacts/ml_dataset.npz`** and **`artifacts/ml_dataset_meta.csv`**. Expects **`final_label`** ∈ {`rugpull`, `safe`}.

---

### Phase 8: Model training

```bash
python 08_train_models.py
```

Trains logistic regression, random forest, and linear SVM; reports hold-out and 5-fold F1; saves **`artifacts/best_model.joblib`**.

---

### Phase 9: Kaggle / flat CSV export

```bash
python 09_export_kaggle_csvs.py
python 09_export_kaggle_csvs.py --intent-json-column
```

Writes **`artifacts/intent_vectors.csv`** and **`artifacts/ml_dataset.csv`** (wide embedding columns + behavior + `target` / `target_label`).

---

### Prototype UI

```bash
python -m streamlit run streamlit_app.py
```

Uses the saved **`best_model.joblib`** and the same embedding model name as Phase 5. Slither-derived features are **not** run inside the app by default (aligned with offline feature design).

---

## Etherscan API (V2)

Legacy **V1** URLs (`https://api.etherscan.io/api` without `chainid`) return a deprecation error. This project uses:

- **Base URL:** `https://api.etherscan.io/v2/api`
- **Parameter:** `chainid=1` (Ethereum mainnet)

See Etherscan’s [V2 migration](https://docs.etherscan.io/v2-migration) documentation for details.

---

## Outputs and artifacts (summary table)

| Output | Description |
|--------|-------------|
| `master_dataset.csv` | Balanced Ethereum addresses; binary `label` for corpus construction. |
| `raw_data/<address>/` | Fetched verified `.sol` (filename from Etherscan `ContractName` when present). |
| `dataset_manifest.csv` | Join of labels + whether source exists + relative path to primary `.sol`. |
| `verified_manifest.csv` | **All** verified-source rows only; **true** class distribution (imbalance expected). |
| `verified_manifest_balanced_seed42.csv` | 50/50 subsample **among verified** only (`random_state=42`). |
| `verified_cohort_report.txt` | Printed summary of both cohorts for the paper. |
| `pilot_manifest.csv` | Stable `contract_id`, link to pilot folder, weak master label snapshot. |
| `pilot_data/contract_XXX/` | `code.sol`, `text.txt` (comments), `functions.txt` (names). |
| `manual_annotations_seed.csv` | Bootstrap CSV for annotation UI; **replace** with reviewed `manual_annotations.csv`. |
| `artifacts/intent_embeddings.npy` | Float32 matrix **N × 384** (Sentence-BERT). |
| `artifacts/intent_contract_ids.json` | List of `contract_id` strings, **row order matches** embeddings. |
| `artifacts/behavior_features.csv` | One row per pilot contract; Slither + regex + merged rug-pull proxies. |
| `artifacts/ml_dataset_meta.csv` | Human-readable merged features + `final_label` (no embedding columns). |
| `artifacts/ml_dataset.npz` | Primary training bundle: `X`, `y`, `contract_id`, `feature_cols`. |
| `artifacts/intent_vectors.csv` | Wide CSV: `contract_id` + `emb_000`…`emb_383` (+ optional JSON column). |
| `artifacts/ml_dataset.csv` | Kaggle-friendly flat table: embeddings + behavior + `target` / `target_label`. |
| `artifacts/best_model.joblib` | `{"model": fitted_estimator, "name": str}` chosen by hold-out F1. |
| `artifacts/ablation_report.md` | Ablation F1 / CV / confusion matrices (Phase 11). |
| `artifacts/ablation_results.json` | Machine-readable ablation results. |

---

## Output schemas (columns and how they help)

### `master_dataset.csv`

| Column | Type | Role |
|--------|------|------|
| `address` | string | Checksummed or lowercase Ethereum contract address from upstream CSVs. |
| `label` | int | **1** = malicious arm (ETH rug-pull list), **0** = subsampled benign (SmartBugs-style pool). **Purpose:** enforce a **50/50 address-level** manifest before download; it does **not** mean every address has verified source. |

**Use in paper:** report **N addresses** per class; separately report **verified-source rate** from the manifest.

---

### `dataset_manifest.csv`

| Column | Type | Role |
|--------|------|------|
| `address` | string | Same key as `master_dataset.csv`. |
| `label` | int | Copied from master (corpus label). |
| `sol_path` | string | Relative POSIX path to first `*.sol` under `raw_data/<address>/`, or empty. |
| `has_verified_source` | int | **1** if at least one `.sol` was stored; **0** if Etherscan had no usable source. |

**Use in paper:** define your **analyzable subset** (for example rows with `has_verified_source == 1` where you run Slither and NLP); discuss **selection bias** (unverified contracts may skew toward scams or dead deployments—justify empirically if you can).

---

### `verified_manifest.csv` (Phase 10)

Same columns as `dataset_manifest.csv`, but **only** rows with `has_verified_source == 1`. Class counts reflect **Etherscan verification**, not the original 50/50 address list.

---

### `verified_manifest_balanced_seed42.csv` (Phase 10)

Same schema as `verified_manifest.csv`. Built by sampling **`min(count label=0, count label=1)`** from each class with **`random_state=42`**, then shuffling with **`random_state=42`**. Use when you need **equal n per class** among contracts that actually have source; always report **how many** contracts were excluded relative to `verified_manifest.csv`.

---

### `verified_cohort_report.txt` (Phase 10)

Plain-text summary: total addresses, verified vs missing source, full verified counts per label, imbalance ratio, balanced subsample size, and a reminder to report both.

---

### `pilot_manifest.csv`

| Column | Type | Role |
|--------|------|------|
| `contract_id` | string | Stable id `contract_001` … for pilot. |
| `address` | string | On-chain address. |
| `label_master_binary` | int | Snapshot of master `label` at pilot creation (for traceability only). |
| `pilot_dir` | string | Path to `pilot_data/contract_XXX`. |
| `code_sol` | string | Path to canonical `code.sol` inside the pilot folder. |

**Use in paper:** supplementary table linking **public address**, **pilot id**, and **annotation file** row.

---

### `manual_annotations.csv` (or `manual_annotations_seed.csv`)

| Column | Type | Role |
|--------|------|------|
| `contract_id` | string | Join key to pilot + behavior CSV. |
| `intent_text` | string | Text fed to Sentence-BERT; usually derived from `text.txt` or your paraphrase of claims. |
| `intent_label` | string | Your **compact** intent code (e.g. `safe_withdraw`, `community_fair`)—for stratified error analysis. |
| `behavior_label` | string | Your **compact** behavior code (e.g. `owner_withdraw`) from reading code + optional Slither. |
| `final_label` | string | **Ground truth** for training: **`rugpull`** or **`safe`** (must match Phase 7). |
| `reviewer_notes` | string | Audit trail / adjudication notes. |

**Use in paper:** this is your **IRB-grade** (or CS ethics) traceable label; the seed file is **not** sufficient for publication without review.

---

### `artifacts/behavior_features.csv`

| Column | Meaning | How it helps |
|--------|---------|--------------|
| `contract_id` | Pilot id | Join to annotations. |
| `slither_ok` | 1 if Slither produced parseable JSON | Separates “tool ran” vs regex-only rows. |
| `slither_error` | Short error tail | Debugging coverage in methodology appendix. |
| `regex_owner_withdraw` | Heuristic: privileged modifier + withdraw-like surface | **Behavior proxy** when Slither unavailable. |
| `regex_emergency_withdraw` | Emergency-style naming / patterns | Flags “escape hatch” narratives vs real user control. |
| `regex_unrestricted_mint` | Public/external `mint` without obvious gating on signature | Proxy for **supply manipulation** risk. |
| `slither_high_count` | Count of High-impact findings (capped) | Summary severity signal. |
| `slither_arbitrary_send` | Union of arbitrary-send detectors | Evidence of **unrestricted ETH/ERC20** routing. |
| `slither_suicidal` / `slither_unchecked_lowlevel` / `slither_controlled_delegatecall` / `slither_delegatecall_loop` | Specific Slither checks | Fine-grained behavior story for case studies. |
| `slither_ownerish_any` | Any check in a curated “privileged flow / dangerous transfer” set | **Robust scalar** when individual detectors are sparse. |
| `owner_withdraw` | **Merged** flag (regex ∪ Slither owner-ish signals) | Matches paper narrative: *can privileged actors extract value?* |
| `emergency_withdraw` | **Merged** emergency signal | Distinguishes legitimate emergency exits from scams. |
| `unrestricted_mint` | **Merged** mint risk (here aligned with regex mint heuristic) | Supply-side rug-pull indicator. |

**Use in paper:** report **Sparsity** (how often each flag fires); **correlation** with `final_label`; **ablation** by zeroing Slither columns when `slither_ok=0`.

---

### `artifacts/ml_dataset.npz` (primary training file)

Loaded in Python as:

```python
import numpy as np
pack = np.load("artifacts/ml_dataset.npz", allow_pickle=True)
X = pack["X"]              # shape (N, 384 + 14): embeddings + behavior block
y = pack["y"]             # 0 = safe, 1 = rugpull (positive class)
ids = pack["contract_id"] # string array
names = pack["feature_cols"]  # 14 tabular column names (see below)
```

The **last 14 columns** of `X` correspond to `feature_cols`, in order:

`owner_withdraw`, `emergency_withdraw`, `unrestricted_mint`, `regex_owner_withdraw`, `regex_emergency_withdraw`, `regex_unrestricted_mint`, `slither_ok`, `slither_high_count`, `slither_arbitrary_send`, `slither_suicidal`, `slither_unchecked_lowlevel`, `slither_controlled_delegatecall`, `slither_delegatecall_loop`, `slither_ownerish_any`.

**Use in paper:** explicit **vector layout** for replication; cite MiniLM embedding dimension **384** and total hybrid dimension **398**.

---

### `artifacts/ml_dataset.csv` and `intent_vectors.csv` (Phase 9)

- **`intent_vectors.csv`:** `contract_id`, then **`emb_000` … `emb_383`**. Optional `intent_vector` JSON column if you run Phase 9 with `--intent-json-column`.
- **`ml_dataset.csv`:** same wide embedding columns **plus** the 14 behavior columns **plus** `target` (0/1) **plus** `target_label` (`safe` / `rugpull`).

**Use in paper:** upload to **Kaggle**, **Colab**, or institutional HPC without Python NPZ tooling; reviewers can eyeball feature columns directly.

---

### `artifacts/best_model.joblib`

A dictionary: `{"model": sklearn_estimator, "name": "logistic_regression" | "random_forest" | "linear_svc"}`. The estimator is the **winner** on **hold-out F1** among the three baselines in `08_train_models.py`.

**Use in paper:** freeze this artifact with a Zenodo DOI next to the dataset snapshot.

---

## Training and evaluation (how to train models)

### 1. Environment

```bash
pip install pandas
pip install -r requirements-research.txt
```

Install **Slither** and a compatible **solc** if you want non-zero Slither columns (optional but strengthens the “behavior” side of the hybrid).

### 2. End-to-end order (research track)

Run from the repository root:

| Step | Command | Produces |
|------|---------|----------|
| Balance | `python 01_build_master_dataset.py` | `master_dataset.csv` |
| Download | `$env:ETHERSCAN_API_KEY="..."` then `python 02_download_contracts.py` | `raw_data/` |
| Manifest | `python 03_build_dataset_manifest.py` | `dataset_manifest.csv` |
| Verified cohorts | `python 10_verified_source_cohorts.py` | `verified_manifest.csv`, `verified_manifest_balanced_seed42.csv`, `verified_cohort_report.txt` |
| Pilot | `python 04_prepare_pilot_100.py` | `pilot_data/`, `manual_annotations_seed.csv` |
| **Annotate** | Copy seed → `manual_annotations.csv`, fill columns | Human ground truth |
| Embed | `python 05_embed_intent.py` (or `python 05_embed_intent.py --use-seed` until `manual_annotations.csv` exists) | `artifacts/intent_embeddings.npy`, `intent_contract_ids.json` |
| Behavior | `python 06_extract_behavior_features.py` | `artifacts/behavior_features.csv` |
| Merge | `python 07_build_ml_dataset.py` (add `--use-seed` if still using only the seed file) | `artifacts/ml_dataset.npz`, `ml_dataset_meta.csv` |
| Export (optional) | `python 09_export_kaggle_csvs.py` | `ml_dataset.csv`, `intent_vectors.csv` |
| Train | `python 08_train_models.py` | `artifacts/best_model.joblib`, console metrics |
| Ablations | `python 11_run_ablation_experiments.py` | `artifacts/ablation_report.md`, `ablation_results.json` |

### 3. What the trainer does (for Methods section)

- **Split:** stratified 75% / 25% train–test, `random_state=42`, positive class = **rugpull** (`y=1`).
- **Models:**
  - **Logistic regression** and **linear SVM:** preceded by **`StandardScaler`** on the full `X` (embeddings + tabular).
  - **Random forest:** no scaler (tree splits on raw `X`).
- **Class imbalance:** **`class_weight="balanced"`** on all three.
- **Selection:** best **hold-out F1** (rugpull = positive).
- **Extra reporting:** **5-fold stratified CV F1** printed for each model (same folds, shuffled with `random_state=42`).

### 4. What to report in the paper

- **Table:** Precision, Recall, F1 for class **rugpull** and **safe** (per model), plus **macro** / **weighted** if space allows.
- **Hybrid vs ablation:** retrain after modifying `07_build_ml_dataset.py` to drop embedding or behavior slices; compare F1 and calibration.
- **Leakage check:** ensure train/test do not share **near-duplicate** contracts or **cloned** code without grouping (extend with a dedup or project-level split if needed).
- **External validation:** hold out a fresh time slice or a second source list not used in master construction.

### 5. Prototype (inference only)

After training:

```bash
python -m streamlit run streamlit_app.py
```

The app encodes **user intent text** with the **same** MiniLM checkpoint and applies **regex behavior flags** only (Slither flags zeroed) unless you extend it—document that gap in the demo section.

---

## Reproducibility

- **Phase 1 balance and shuffle:** `random_state=42` (pandas).  
- **Phase 4 pilot sampling:** `RNG = 42`.  
- **Phase 8 train/test split:** `random_state=42`, stratified.

Document Python version, package versions (`pip freeze`), and the **exact commit** of this repository in supplementary material.

---

## Limitations and disclosure

- **Labels in the master CSV** come from your external rug-pull list and SmartBugs-style benign list; they are **not** re-verified by this repo.  
- **Verified source** may be missing for some addresses; Slither may fail without a compatible **solc**.  
- **Pilot seed labels** must be replaced with **manual, protocol-driven** annotations for a defensible Q1 claim.  
- High accuracy on small pilots can reflect **weak supervision leakage** or **distribution shift**; report confidence intervals, ablations, and external validation where possible.

---

## Security notes

- **API keys:** Prefer storing keys in environment variables or a local secrets file that is **not** committed. If a key is ever committed or shared publicly, **rotate it** in the Etherscan dashboard.  
- **Do not** commit API keys to public repositories or shared archives.

---

## License and citation

If you publish this pipeline, cite your data sources (rug-pull corpus, SmartBugs Wild / ICSE 2020 baseline) and tools (Etherscan, Slither, Sentence Transformers, scikit-learn) according to their respective terms and citation guidelines.

For questions about methodology wording (“intent–behavior deviation”), align figure and table captions with the **manual annotation protocol** and the **exact feature definitions** in `06_extract_behavior_features.py` and `solidity_extract.py`.
