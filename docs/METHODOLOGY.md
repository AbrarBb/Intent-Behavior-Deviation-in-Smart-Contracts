# Methodology: Intent–Behavior Deviation Detection in Smart Contracts

This document describes the **end-to-end methodology** implemented in this repository for researching **rug-pull–style detection** via **intent** (natural language from contract source) vs **behavior** (static-analysis-oriented and heuristic signals from the same Solidity). It is written so you can adapt paragraphs directly into a Q1 journal **Methods** section, with explicit links to scripts and artifacts.

---

## 1. Research objective

**Central question.** For a given Ethereum smart contract with verified source, can we represent (1) what the **developers claim** the contract does (intent, from comments / NatSpec) and (2) what the **code structure suggests** it allows (behavior proxies), then train a model to separate **malicious** from **benign** instances at the corpus level—consistent with **intent–behavior deviation** as a working hypothesis?

**Scope.** Ethereum **mainnet** addresses, **verified** Solidity where available. Binary labels at the master-manifest level come from an external rug-pull list (malicious arm) and a SmartBugs Wild–style benign pool; **pilot-level** human labels are documented separately ([`ANNOTATION_PROTOCOL.md`](ANNOTATION_PROTOCOL.md)).

---

## 2. Notation and terminology

| Symbol / term | Meaning |
|---------------|---------|
| **Intent** | Textual signal extracted from Solidity source (NatSpec, `//`, `/* */`), embedded with a sentence transformer. |
| **Behavior** | Tabular features encoding privileged-flow / risk proxies (regex heuristics ± Slither detectors when enabled). |
| **Hybrid model** | Classifier trained on **concatenated** intent embeddings and behavior features. |
| **Verified-source cohort** | Contracts for which non-empty source was retrieved and stored locally (Etherscan verification path successful in our pipeline). |
| **`label` / `target`** | Malicious = **1**, benign = **0** in large-scale training; pilot manual `final_label` uses **`rugpull` / `safe`** then mapped to 0/1 in Phase 7. |

---

## 3. Data sources

### 3.1 Malicious pool (rug pulls)

- **File:** `rugpull_full_dataset_new (1).csv` (project-specific curated list).  
- **Filter:** rows with **`Chain == "ETH"`** only.  
- **Key column:** `address`.  
- **Role:** defines the **malicious arm** at the **address-list** stage.

### 3.2 Benign pool (SmartBugs-style baseline)

- **File:** `all_contract.csv` (no header).  
- **Columns:** address (col 0), transaction count (col 1).  
- **Role:** reservoir from which we **subsample** benign addresses to match the ETH rug-pull count for a **balanced master manifest**.

**Threat:** These labels are **external weak supervision**; they are not individually re-audited unless you complete [`ANNOTATION_PROTOCOL.md`](ANNOTATION_PROTOCOL.md).

---

## 4. Phase 1 — Balanced master address list

**Script:** [`01_build_master_dataset.py`](../01_build_master_dataset.py)

**Steps.**

1. Load the rug-pull CSV; keep **ETH** rows; retain `address`; assign **`label = 1`**.  
2. Load `all_contract.csv` with `header=None`; rename to `address`, `tx_count`; drop null addresses.  
3. Let **N** = number of valid ETH rug-pull rows. Randomly sample **exactly N** benign rows with fixed seed **`random_state=42`**. Assign **`label = 0`**.  
4. Concatenate **only** `address`, `label`; shuffle the union with **`random_state=42`**.  
5. Write **`master_dataset.csv`** (no index).

**Interpretation.** The result is **50/50 at the address level** by construction. This does **not** imply 50/50 **after** downloading source: many addresses will lack verified Solidity.

---

## 5. Phase 2 — Verified source acquisition (Etherscan)

**Script:** [`02_download_contracts.py`](../02_download_contracts.py)

**API.** Etherscan **API V2** (`https://api.etherscan.io/v2/api`) with **`chainid=1`** (Ethereum mainnet) and module **`contract`**, action **`getsourcecode`**. API key via environment variable **`ETHERSCAN_API_KEY`**.

**Procedure (per address).**

1. Create `raw_data/<address>/`.  
2. If **`SourceCode`** is non-empty, write `raw_data/<address>/<ContractName>.sol` (fallback `Contract.sol`).  
3. **`time.sleep(0.25)`** after **each** HTTP call (rate limit).  
4. On failure or empty source: log warning and **continue** (no crash).

**Outputs.** Directory tree under `raw_data/`; success is **per-address**, not guaranteed for all master rows.

---

## 6. Phase 3 — Join labels to on-disk source

**Script:** [`03_build_dataset_manifest.py`](../03_build_dataset_manifest.py)

For each `address` in `master_dataset.csv`:

- If at least one `*.sol` exists under `raw_data/<address>/`, set **`has_verified_source = 1`** and record relative `sol_path` to the first sorted `.sol` file.  
- Else **`has_verified_source = 0`** and empty path.

**Artifact:** `dataset_manifest.csv` — use this to report **how many contracts are actually analyzable**.

---

## 7. Phase 10 — Verified-only cohorts (honest reporting)

**Script:** [`10_verified_source_cohorts.py`](../10_verified_source_cohorts.py)

**Artifacts.**

- **`verified_manifest.csv`:** all rows with `has_verified_source == 1` — **true class counts** among contracts with source.  
- **`verified_manifest_balanced_seed42.csv`:** stratified **50/50 among verified only** (`random_state=42`); surplus majority-class rows dropped — use for **fair model comparison** while disclosing drop count.  
- **`verified_cohort_report.txt`:** printable summary for the paper.

**Methodological rule.** Report **both** the full verified distribution and any balanced subset used for experiments.

**Reference table (frozen example):** [`COHORT_TABLES.md`](COHORT_TABLES.md).

---

## 8. Pilot cohort (100 contracts) — standardized folders

**Script:** [`04_prepare_pilot_100.py`](../04_prepare_pilot_100.py)

From rows with verified source, sample up to **50/50** per class (seed **42**), then for each selected contract copy code into:

```
pilot_data/contract_XXX/code.sol
pilot_data/contract_XXX/text.txt   # extracted comments / NatSpec
pilot_data/contract_XXX/functions.txt
```

**Optional inputs:** `--from-verified-full`, `--from-verified-balanced`, or `--manifest path` so pilot sampling aligns with the cohort you describe in the paper.

**Human labels:** `manual_annotations.csv` per [`ANNOTATION_PROTOCOL.md`](ANNOTATION_PROTOCOL.md).

---

## 9. Intent representation (NLP pillar)

### 9.1 Text extraction

**Module:** [`solidity_extract.py`](../solidity_extract.py)

**Rule (high level).** After stripping string literals to reduce noise, collect:

- NatSpec blocks `/** ... */`, lines `/// ...`, and line comments `// ...` (excluding `///` already captured).  
- If no text remains, a fallback placeholder may concatenate **function names** so the embedding model receives non-empty input (pilot / full-dataset builders).

### 9.2 Embedding model

**Model:** `sentence-transformers/all-MiniLM-L6-v2` — **384-dimensional** dense vectors.

**Pilot path:** [`05_embed_intent.py`](../05_embed_intent.py) → `artifacts/intent_embeddings.npy` + `artifacts/intent_contract_ids.json`.

**Full verified-source path:** [`12_build_verified_full_ml_dataset.py`](../12_build_verified_full_ml_dataset.py) embeds intent for **all rows** in `verified_manifest.csv`.

**Paper wording.** Intent is **not** logical entailment of safety; it is a **semantic embedding** of surface text associated with the contract file.

---

## 10. Behavior representation (static-analysis / heuristic pillar)

### 10.1 Regex / structural heuristics

**Module:** [`solidity_extract.py`](../solidity_extract.py) — `regex_behavior_flags`

**Examples (non-exhaustive).**

- **Privileged withdraw signal:** presence of modifiers like `onlyOwner` / `onlyRole` combined with withdraw-like naming.  
- **Emergency path:** “emergency” in function names or body.  
- **Mint surface:** `function ... mint` signatures that appear `public`/`external` without obvious gating on the signature head.

These are **transparent, auditable proxies**—not sound proofs of exploitability.

### 10.2 Slither (optional, pilot-oriented)

**Script:** [`06_extract_behavior_features.py`](../06_extract_behavior_features.py)

When Slither runs successfully, selected detector families populate columns such as `slither_arbitrary_send`, `slither_suicidal`, etc., and are merged with heuristics into **`owner_withdraw`**, **`emergency_withdraw`**, **`unrestricted_mint`** where applicable.

**Full-scale note.** [`12_build_verified_full_ml_dataset.py`](../12_build_verified_full_ml_dataset.py) currently keeps **Slither-derived columns at zero** by default for scale; behavior mass is then **regex + merged flags**. The **column schema** remains fixed for comparability if you later run Slither on subsets.

### 10.3 Fixed 14-column behavior block (order matters)

Used consistently in `07_*`, `12_*`, and exports:

1. `owner_withdraw`  
2. `emergency_withdraw`  
3. `unrestricted_mint`  
4. `regex_owner_withdraw`  
5. `regex_emergency_withdraw`  
6. `regex_unrestricted_mint`  
7. `slither_ok`  
8. `slither_high_count`  
9. `slither_arbitrary_send`  
10. `slither_suicidal`  
11. `slither_unchecked_lowlevel`  
12. `slither_controlled_delegatecall`  
13. `slither_delegatecall_loop`  
14. `slither_ownerish_any`  

---

## 11. Training matrices

### 11.1 Pilot hybrid dataset (manual labels)

**Merge:** [`07_build_ml_dataset.py`](../07_build_ml_dataset.py)

- Join `manual_annotations.csv` (or seed) with `artifacts/behavior_features.csv` on `contract_id`.  
- Align embeddings to row order.  
- **`X`:** `hstack(embedding[384], behavior[14])` → shape **(N, 398)**.  
- **`y`:** `1` if `final_label == rugpull`, else `0`.

### 11.2 Full verified-source dataset (weak labels)

**Build:** [`12_build_verified_full_ml_dataset.py`](../12_build_verified_full_ml_dataset.py)

- Iterate `verified_manifest.csv`; read `sol_path`; extract intent text; compute **384-d** embedding; compute **14** behavior features.  
- **`y`:** `label` from manifest (weak supervision).  
- **Outputs:**  
  - `artifacts/ml_dataset_verified_full.npz` — primary for training (`X`, `y`, metadata).  
  - `artifacts/ml_dataset_verified_full.csv` — flat table: `address`, `target`, `target_label`, `sol_path`, `emb_*`, 14 behavior columns.  
  - `artifacts/ml_dataset_verified_full_meta.csv` — no embedding columns (compact).  
  - `artifacts/ml_dataset_verified_full_config.json` — build metadata.

---

## 12. Classifiers and evaluation protocol

### 12.1 Baselines (pilot scale)

**Script:** [`08_train_models.py`](../08_train_models.py)

- **Split:** stratified **75% / 25%** train–test, `random_state=42`.  
- **Models:** logistic regression (with `StandardScaler`), random forest, linear SVM (scaled).  
- **Imbalance:** `class_weight='balanced'`.  
- **Selection:** best hold-out **F1** for positive class (rugpull).  
- **Reporting:** 5-fold stratified CV F1 (same seed).

### 12.2 Verified-full training (large scale)

**Script:** [`13_train_verified_full_models.py`](../13_train_verified_full_models.py)

Same family of models; RF uses **`n_estimators=300`** in that script—document the exact values you report in the paper.

### 12.3 Ablations — pilot cohort (Phases 5–7)

**Script:** [`11_run_ablation_experiments.py`](../11_run_ablation_experiments.py)

Operates on **`artifacts/ml_dataset.npz`** built from the **pilot** (`manual_annotations` + `behavior_features`). Modes include **hybrid**, **intent-only**, **behavior-only**, **hybrid without Slither detector block** (when Slither columns are present). Outputs: `artifacts/ablation_report.md` and `ablation_results.json`.

**Use in paper.** Supplementary or secondary analysis when the **human-reviewed pilot** is the emphasis.

### 12.4 Formal ablation study — verified-full dataset (Results / MDI bias)

**Script:** [`15_ablation_study.py`](../15_ablation_study.py)

Addresses **Random Forest mean decrease in impurity (MDI)** bias: per-feature importances on **hybrid** `X` tend to favor **many continuous embedding dimensions** over a **small set of sparse binary** behavior columns, which can **overstate** the “NLP pillar” in a single forest fit **even when** behavior carries signal under controlled conditions.

**Procedure (fixed for replication).**

1. Load **`artifacts/ml_dataset_verified_full.csv`**.  
2. Define three disjoint feature sets on the **same** rows and **`target`**:  
   - **`X_intent`:** columns **`emb_000` … `emb_383`** (384).  
   - **`X_behavior`:** the **14** behavior / regex / Slither-schema columns (§10.3).  
   - **`X_hybrid`:** **concatenation** → **398** columns.  
3. **Stratified 5-fold cross-validation**, `shuffle=True`, **`random_state=42`**.  
4. On each fold, train **`RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)`** (fresh estimator per fold).  
5. Report **mean F1-score** for the **positive class** (**rugpull**, `target=1`) and **mean ROC-AUC** (from `predict_proba` vs `target`) **averaged across folds**, for **Intent-Only**, **Behavior-Only**, and **Hybrid (Proposed)**.

**Printed output.** A Markdown table plus **relative % change** of Hybrid mean F1 vs Intent-Only (may be negative if embeddings already saturate performance).

**Interpretation for Q1 writing.**

- If **Behavior-Only** underperforms **Intent-Only** but you still claim a **hybrid** contribution, argue **complementarity** (different error modes), **robustness checks**, or **pilot human labels**—not raw MDI shares alone.  
- If **Hybrid** ≈ **Intent-Only** on F1, state explicitly: behavior features add **limited lift** under current weak labels and sparse Slither columns in the full build—then tighten behavior with Slither-on-subset or richer static features.

### Example replication snapshot (replace after any data refresh)

The table below is **one** run of [`15_ablation_study.py`](../15_ablation_study.py) on the authors’ local `artifacts/ml_dataset_verified_full.csv` (2026-04-03). **Re-run the script** after regenerating the CSV and paste updated figures into the paper; do not treat these as fixed constants across environments.

| Model | Mean F1 (rugpull) | Mean ROC-AUC |
| --- | ---: | ---: |
| Intent-Only | 0.9852 | 0.9952 |
| Behavior-Only | 0.6945 | 0.7628 |
| Hybrid (Proposed) | 0.9846 | 0.9954 |

**Hybrid vs Intent-Only (mean F1):** about **−0.07%** relative (hybrid slightly below intent-only in this snapshot). **Mean ROC-AUC** was **+0.02%** relative—useful as a secondary ranking metric, not a substitute for reporting F1/practical error tradeoffs.

**Reading this snapshot:** Behavior-only lags intent-only strongly; hybrid matches intent-only within fold noise, which aligns with the §12.4 narrative (embedding-dominant setup; sparse behavior signal at full scale).

---

## 13. Feature importance (MDI) vs formal ablation

### 13.1 MDI importances (descriptive only)

**Script:** [`14_feature_importance.py`](../14_feature_importance.py)

Retrains a **random forest** (`n_estimators=100`, `class_weight='balanced'`, `random_state=42`) on **`ml_dataset_verified_full.csv`** using the **full 398-d** feature space, then:

1. Ranks **per-dimension** importances (e.g. top 20).  
2. Aggregates **sum of importances** over all **`emb_*`** (“Total NLP Intent Importance”) vs the **14** behavior columns (“Total Static Behavior Importance”) as **percentages** of their combined mass.

**Caveat (Methods / Limitations).** sklearn **MDI** is **not causal** and is **biased** toward **high-cardinality / continuous** inputs (here, 384 embedding dimensions). **Do not** equate aggregated MDI percentages with “% of security explanation.”

### Example replication snapshot ([`14_feature_importance.py`](../14_feature_importance.py))

One run on the authors’ local `artifacts/ml_dataset_verified_full.csv` (2026-04-03), **single** RF fit on all rows (not cross-validated). **Re-run** after regenerating the CSV; numbers are **illustrative** only.

**Top 20 features** (MDI; identical hyperparameters as §13.1):

| feature | importance |
| --- | ---: |
| emb_125 | 0.069533 |
| emb_337 | 0.040080 |
| emb_193 | 0.038108 |
| emb_212 | 0.035075 |
| emb_313 | 0.034841 |
| emb_242 | 0.030957 |
| emb_378 | 0.030703 |
| emb_237 | 0.028058 |
| emb_066 | 0.026943 |
| emb_219 | 0.023234 |
| emb_321 | 0.022238 |
| emb_329 | 0.019552 |
| emb_139 | 0.018750 |
| emb_159 | 0.018697 |
| emb_095 | 0.018322 |
| emb_372 | 0.015068 |
| emb_170 | 0.013642 |
| emb_293 | 0.013613 |
| emb_349 | 0.013129 |
| emb_343 | 0.013063 |

**Aggregated pillar split** (percent of Intent + Behavior importance mass):

- **Total NLP Intent (all `emb_*`):** 99.90% (raw sum 0.999043)  
- **Total Static Behavior (14 columns):** 0.10% (raw sum 0.000957)  
- sklearn importances **sum to 1.0** over all 398 features.

**Reading this snapshot:** Every feature in the top 20 is an embedding dimension; the behavior block’s combined MDI is a **tiny** share—consistent with §13.1’s bias warning and with §12.4 (ablation), where **intent dominates** discriminative power in this build.

### 13.2 Pairing with §12.4 in the Results section

**Recommended narrative.** Present **formal ablation** (§12.4: Intent- vs Behavior- vs Hybrid F1/AUC under **identical CV**) as the **primary** evidence for **modality contribution**. Use **MDI aggregates** (§13.1) only as **qualitative** introspection of one fitted forest, and cite **MDI bias** literature or sklearn documentation as needed.

---

## 14. Prototype tool (optional)

**Script:** [`streamlit_app.py`](../streamlit_app.py)

Demo inference: user intent text + Solidity → embedding + heuristic behavior flags → trained joblib model. **Slither** is not required inside the app by default.

---

## 15. Reproducibility, ethics, and threats

- **Replication steps:** [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)  
- **Threats / limitations:** [`THREATS_TO_VALIDITY.md`](THREATS_TO_VALIDITY.md)  
- **Contributions / novelty wording:** [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md)

---

## 16. Minimal command sequence (reference)

```text
python 01_build_master_dataset.py
# set ETHERSCAN_API_KEY
python 02_download_contracts.py
python 03_build_dataset_manifest.py
python 10_verified_source_cohorts.py
python 04_prepare_pilot_100.py          # optional: --from-verified-balanced
# human review → manual_annotations.csv
python 05_embed_intent.py
python 06_extract_behavior_features.py
python 07_build_ml_dataset.py
python 08_train_models.py
python 11_run_ablation_experiments.py
# large-scale verified full:
python 12_build_verified_full_ml_dataset.py
python 13_train_verified_full_models.py
python 14_feature_importance.py
python 15_ablation_study.py
```

---

## 17. What to paste into the paper (checklist)

1. **Data:** master size, verified count, class distribution **before/after** verification ([`COHORT_TABLES.md`](COHORT_TABLES.md)).  
2. **Intent:** model name, dimension 384, extraction rules (§9).  
3. **Behavior:** list the 14 features; state whether Slither was run or zeros (§10).  
4. **ML:** train/test split, seeds, models, metrics (P/R/F1); **formal verified-full ablation** (§12.4, [`15_ablation_study.py`](../15_ablation_study.py)) with pilot ablations (§12.3) as optional.  
5. **Interpretability:** **MDI** importances (§13.1) **paired with** formal ablation (§12.4)—do not rely on MDI alone.  
6. **Honesty:** weak labels vs pilot human labels; verification bias (§7, [`THREATS_TO_VALIDITY.md`](THREATS_TO_VALIDITY.md)).

---

*Last updated to match repository scripts and docs layout. Regenerate cohort numbers after any data refresh.*
