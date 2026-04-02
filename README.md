# Intent–Behavior Deviation in Smart Contracts

Reproducible data preparation and research utilities for studying **rug-pull–style mismatches** between **claimed intent** (natural language in comments and documentation) and **observable behavior** (static analysis, heuristics). This repository supports a Q1-style methodology pipeline: balanced Ethereum corpora, verified source acquisition, manifest construction, pilot cohort layout, hybrid NLP + program-analysis features, model training, and a Streamlit prototype.

---

## Table of contents

1. [Research framing](#research-framing)
2. [Prerequisites](#prerequisites)
3. [Repository layout](#repository-layout)
4. [Input data (you provide)](#input-data-you-provide)
5. [Pipeline overview](#pipeline-overview)
6. [Phase-by-phase usage](#phase-by-phase-usage)
7. [Etherscan API (V2)](#etherscan-api-v2)
8. [Outputs and artifacts](#outputs-and-artifacts)
9. [Reproducibility](#reproducibility)
10. [Limitations and disclosure](#limitations-and-disclosure)
11. [Security notes](#security-notes)

---

## Research framing

- **Intent:** Textual signals (NatSpec, comments) about what users are told the contract does.
- **Behavior:** What the bytecode-level / analysis-level story allows (Slither detectors, regex heuristics for privileged flows).
- **Task:** Binary characterization (e.g. malicious vs benign at the *dataset* level, plus pilot **rugpull** vs **safe** after manual review).

The **master** split is label-balanced by construction; **verified source** availability on Etherscan is not guaranteed for every address, so downstream analyses should report both **manifest size** and **labeled-with-source** counts.

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
| `solidity_extract.py` | Shared comment / function extraction and regex flags. |
| `streamlit_app.py` | Prototype scorer (intent + code paste). |
| `manual_annotations.template.csv` | Schema example for human annotations. |
| `pilot_data/` | Standardized per-contract folders (after Phase 4). |
| `raw_data/` | Downloaded `.sol` trees (after Phase 2). |
| `artifacts/` | Embeddings, behavior CSVs, NPZ/CSV ML tables, trained model. |

---

## Input data (you provide)

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

## Outputs and artifacts

| Output | Description |
|--------|-------------|
| `master_dataset.csv` | All candidate addresses; balanced 0/1 labels. |
| `raw_data/` | Per-address verified Solidity (when available). |
| `dataset_manifest.csv` | Address, label, path, source flag. |
| `pilot_data/` | 100-contract standardized layout. |
| `manual_annotations_seed.csv` | Starter labels; refine into `manual_annotations.csv`. |
| `artifacts/behavior_features.csv` | Slither + regex behavior columns. |
| `artifacts/ml_dataset.npz` | Training matrix `X`, labels `y`, `contract_id`, feature names. |
| `artifacts/ml_dataset.csv` | Flat export for external notebooks. |
| `artifacts/best_model.joblib` | Serialized best baseline (by hold-out F1). |

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
