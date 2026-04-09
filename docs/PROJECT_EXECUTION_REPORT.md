# Project Execution Report

This document explains the full execution story of the intent-behavior rug-pull detection project: what was done, how it was done, why each decision was made, what has been found, and what should happen next.

---

## 1) Objective and Research Framing

The project goal is to build and evaluate a practical ML pipeline for detecting likely rug-pull contracts by combining:

- **Intent signals** from human-readable descriptions (NLP embeddings)
- **Behavior signals** from Solidity static patterns and Slither-style indicators

The central research claim is not "NLP only" or "behavior only", but whether a **hybrid intent+behavior view** provides better and more defensible evidence than either modality alone.

---

## 2) What Was Done (End-to-End)

### Phase A: Dataset foundation and source retrieval

- Built master dataset records with labels/metadata (`01_build_master_dataset.py`).
- Downloaded Solidity source code from Etherscan (`02_download_contracts.py`), updated to V2 endpoint and `chainid=1`, with API key from env var (`ETHERSCAN_API_KEY`).
- Built manifest linking contracts, labels, and source availability (`03_build_dataset_manifest.py`).

**Why:** Reliable source availability is a hard prerequisite for static behavior extraction and reproducible ML features.

### Phase B: Verified-source cohort construction

- Added verified-source cohort tooling (`10_verified_source_cohorts.py`) to explicitly separate:
  - full verified cohort
  - optional balanced verified cohort (seed-fixed)

**Why:** Class balance and source-verification filtering materially affect model behavior and publication credibility.

### Phase C: Pilot cohort and annotation path

- Built pilot sample generation (`04_prepare_pilot_100.py`) with options to draw from verified-full or verified-balanced inputs.
- Established pilot annotation path via `manual_annotations.csv`.

**Why:** Pilot cohort enables closer human review and methods sanity checks before scaling conclusions to the full verified corpus.

### Phase D: Feature extraction

- Intent embeddings from annotation text (`05_embed_intent.py`), including pilot contract-id traceability artifact (`artifacts/intent_contract_ids.json`).
- Behavior features from Solidity patterns and Slither schema (`06_extract_behavior_features.py`).
- Merged intent+behavior into ML-ready artifacts (`07_build_ml_dataset.py`).

**Why:** The research question requires side-by-side modality evaluation and fusion under one shared target.

### Phase E: Baseline training and pilot ablations

- Baseline model training (`08_train_models.py`) with stratification and class balancing.
- Pilot ablations (`11_run_ablation_experiments.py`) on pilot-derived `ml_dataset.npz`.

**Why:** Pilot ablations are development evidence and help detect gross issues in feature engineering and label behavior.

### Phase F: Verified-full large-scale training package

- Built largest training dataset from verified-full manifest (`12_build_verified_full_ml_dataset.py`) producing:
  - `artifacts/ml_dataset_verified_full.csv`
  - `artifacts/ml_dataset_verified_full.npz`
- Trained verified-full models (`13_train_verified_full_models.py`).

**Why:** Q1-facing claims should prioritize the largest reproducible verified cohort, not only a small pilot.

### Phase G: Formal analysis for paper claims

- Feature importance analysis (`14_feature_importance.py`): top features + aggregated intent-vs-behavior MDI share.
- Formal ablation study (`15_ablation_study.py`): 5-fold stratified CV on verified-full with:
  - Intent-only
  - Behavior-only
  - Hybrid

**Why:** MDI alone can be biased; formal modality ablation on same folds is the stronger contribution test.

### Phase H: Documentation and publication package

- Expanded methodology and publication docs:
  - `docs/METHODOLOGY.md`
  - `docs/CONTRIBUTIONS.md`
  - `docs/ANNOTATION_PROTOCOL.md`
  - `docs/COHORT_TABLES.md`
  - `docs/THREATS_TO_VALIDITY.md`
  - `docs/REPRODUCIBILITY.md`
  - `docs/MANUSCRIPT_STRUCTURE.md`
- Updated README to reflect paper package and method traceability.
- Added `.gitignore` handling for large/generated artifacts.

**Why:** Reproducibility and clear methods reporting are required for credible peer-review outcomes.

---

## 3) How It Was Done (Method Logic)

### Data logic

- Restrict the main "formal" evaluation to contracts with verified Solidity source.
- Preserve optional balanced cohorts for sensitivity analysis.
- Keep fixed seeds where applicable to ensure reproducible splits and comparisons.

### Feature logic

- Intent represented by dense 384-d embedding columns (`emb_000` to `emb_383`).
- Behavior represented by 14 curated static columns (regex and Slither-schema style indicators).
- Hybrid formed by column-wise concatenation of intent and behavior.

### Evaluation logic

- Use stratified CV to reduce class-imbalance distortions.
- Compare modality blocks under identical folds and target labels.
- Report both F1 (positive class) and ROC-AUC, while prioritizing F1 for practical minority-class quality.

### Interpretation logic

- Treat MDI as descriptive introspection, not causal explanation.
- Use ablation as primary modality evidence.
- Report weak-label limitations and verification bias explicitly.

---

## 4) Why These Choices Were Made

- **Verified-source focus:** without source, behavior extraction quality degrades and comparisons become noisy.
- **Pilot + verified-full split:** pilot supports qualitative/human-grounded checks; verified-full supports scale and statistical stability.
- **Ablation-first claims:** avoids over-claiming from feature-importance artifacts.
- **Doc-heavy structure:** helps make methods auditable and directly transferable into manuscript sections.

---

## 5) Current Findings

### 5.1 Stage 2: Slither-enabled verified-full corpus

Full-corpus build: [`12_build_verified_full_ml_dataset.py`](../12_build_verified_full_ml_dataset.py) with **`--enable-slither`**, pragma/solc-select chains, N=**3324** (see `artifacts/ml_dataset_verified_full_config.json`).

- **Slither OK:** **3095 / 3324 (93.1%)**
- **Slither failed:** **229 (6.9%)** (version/remapping/compile edge cases)

Non-zero Slither detector presence (full CSV) is non-trivial (e.g. `slither_high_count` ~45%, `slither_ownerish_any` ~34%, `slither_controlled_delegatecall` ~25%—run [`tools/post_stage2_diagnostics.py`](../tools/post_stage2_diagnostics.py) for the full table).

### 5.2 Formal verified-full ablation (Slither-enabled CSV)

From [`15_ablation_study.py`](../15_ablation_study.py) on `artifacts/ml_dataset_verified_full.csv` (**2026-04-09**):

| Setting | Mean F1 (rugpull) | Mean ROC-AUC |
| --- | ---: | ---: |
| Intent-only | **0.9852** | 0.9952 |
| Behavior-only | **0.9531** | 0.9640 |
| Hybrid | **0.9848** | 0.9951 |

**Historical comparison (regex-only / Slither columns zero-filled):** behavior-only F1 was **~0.6945**; hybrid ~intent-only. After Stage 2, **behavior-only rises to ~0.95**—static analysis signal is real under ablation, even though **hybrid** still tracks **intent-only** on F1 (small negative vs intent).

Interpretation:

- **Ablation (primary):** With Slither populated, the **behavior block is strong** vs the old zero-filled baseline; intent remains at the **ceiling**; hybrid does not beat intent in this RF+CV setup.
- Frame the paper around **modality analysis** (intent vs behavior vs hybrid) and **Slither coverage**, not “hybrid always wins on F1.”

### 5.3 Feature importance (MDI) snapshot (same Slither build)

From [`14_feature_importance.py`](../14_feature_importance.py): top-20 features remain **embedding dimensions**; aggregate MDI mass is still **~99.8% intent / ~0.2% behavior**—consistent with MDI bias (many continuous embedding dims vs 14 tabular flags). **Pair MDI with §5.2 ablation**; do not cite MDI as proof that “behavior does not matter.”

### 5.4 Practical conclusion

- The pipeline is operational: full-corpus Slither + reproducible ablation + diagnostics ([`docs/STAGE2_WORKFLOW.md`](STAGE2_WORKFLOW.md)).
- Evidence supports a **strong intent baseline**, a **strong behavior-only model after Slither**, and **hybrid ≈ intent** on F1 here—honest framing beats overstating hybrid lift.

---

## 6) Risks and Limitations (Current State)

- Weak-label dependence in large-scale data; rug/safe lists are not contract-level audit truth.
- **~7%** of contracts did not yield a successful Slither JSON (compile/remap/version issues)—failures are not random; consider reporting error buckets.
- MDI still **understates** tabular contribution vs ablation; always cite formal modality ablation for “how much behavior helps.”
- Verification filtering introduces selection bias.
- Hybrid F1 may track intent when embeddings saturate; that does not negate behavior-only strength after Slither.

---

## 7) Next Phases (Recommended Roadmap)

### Phase 1: Optional enrichment and failure analysis

- Optional: [`06b_extract_enriched_behavior_features.py`](../06b_extract_enriched_behavior_features.py) + `--enable-enriched-features` on a **tagged** rebuild (do not overwrite canonical stem without backup).
- Analyze Slither **failure** cases (229) for patterns; improve remappings / solc / multi-file project handling if needed.

### Phase 2: Tighten ground-truth quality

- Expand human-reviewed annotations beyond pilot where resources allow.
- Track annotator agreement and adjudication updates.
- Run sensitivity analysis: weak labels vs reviewed labels.

### Phase 3: Evidence strengthening for paper

- Report Stage 2 Slither coverage + ablation (§5) as primary quantitative block.
- Add confidence intervals or fold variance reporting for main metrics.
- Include targeted error analysis (false positives/false negatives by contract subgroup).

### Phase 4: Reproducibility and release polish

- Freeze requirements and environment snapshots.
- Package artifact metadata and checksums for release.
- Finalize manuscript tables from cohort + ablation outputs.

### Phase 5: Manuscript finalization

- Position contribution as: "hybrid framework + reproducible evidence + explicit limitations."
- Keep claims calibrated to current measured lift.
- Submit with transparent threats and realistic future-work commitments.

---

## 8) Deliverables Status Snapshot

- **Implemented scripts:** full-corpus Slither build, ablation, feature importance, diagnostics, backup workflow ([`STAGE2_WORKFLOW.md`](STAGE2_WORKFLOW.md)).
- **Documentation package:** methods (`METHODOLOGY.md`), this report, cohort/threats/repro docs.
- **Current quantitative story:** **93%** Slither success; **behavior-only F1 ~0.95** vs **~0.69** before Slither; hybrid ~intent; MDI still embedding-heavy—pair with ablation in the manuscript.
- **Optional next step:** enrichment features + tagged rebuild; deeper analysis of Slither failures.

---

## 9) Quick Command Reference

```text
python 12_build_verified_full_ml_dataset.py
python 13_train_verified_full_models.py
python 14_feature_importance.py
python 15_ablation_study.py
```

Use this sequence after any data refresh to regenerate the key evidence for the paper.
