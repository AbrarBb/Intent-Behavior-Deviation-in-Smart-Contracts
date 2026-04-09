# Error analysis — Q1: which contracts do modalities miss?

**Question:** For which contracts do **intent-only** and **behavior-only** models disagree on **false negatives** (missed rugpulls) and **false positives** (safe flagged as rugpull), under the same setup as the formal ablation?

---

## How this was computed

- **Script:** [`tools/paper_diagnostic_bundle.py`](../tools/paper_diagnostic_bundle.py) (modality disagreement section).
- **Data:** `artifacts/ml_dataset_verified_full.csv`; label column `target` (1 = rugpull); id column `address`.
- **Models:** `RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)` — same as [`15_ablation_study.py`](../15_ablation_study.py).
- **CV:** `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`; each row appears in exactly one test fold; predictions are **hard** labels (`predict`, threshold 0.5).
- **Behavior columns:** 14 features from `ml_dataset_verified_full_config.json` (`feature_cols`), not only `slither_*` / `regex_*`.

**Corpus counts:** rugpull **2302**, safe **1022** (verified-full Stage 2 build).

---

## Table 1 — False negatives (predicted safe, actual rugpull)

Unique contracts aggregated across the five test folds (sets are disjoint per fold; union counts each contract at most once).

| Category | Count | % of union FN (73) | % of all rugpulls (2302) |
| --- | ---: | ---: | ---: |
| **Both** modalities miss | 0 | 0.0% | 0.0% |
| **Only intent** misses (behavior correct on that contract) | 6 | 8.2% | 0.3% |
| **Only behavior** misses (intent correct) | 67 | 91.8% | 2.9% |
| **Union** (any modality FN) | 73 | 100% | 3.2% |

**Reading:** There are **no** rugpulls where **both** single-modality models fail at once in this CV snapshot. Most disagreement is **behavior-only** false negatives (**67**), while intent-only misses **6** rugpulls that behavior-only gets right. Intent is the stronger single-modality signal on **FN** here; behavior-only errors dominate the union count.

---

## Table 2 — False positives (predicted rugpull, actual safe)

| Category | Count | % of union FP (161) | % of all safe (1022) |
| --- | ---: | ---: | ---: |
| **Both** modalities flag | 54 | 33.5% | 5.3% |
| **Only intent** flags | 8 | 5.0% | 0.8% |
| **Only behavior** flags | 99 | 61.5% | 9.7% |
| **Union** (either modality FP) | 161 | 100% | 15.8% |

**Reading:** **Behavior-only** contributes more unique false positives (**99**) than intent-only (**8**); **54** safes are flagged by **both**. For a “robust safe” story, behavior-only is noisier on FP than intent-only in this setup.

---

## Complementarity (FN)

- **Share of union FN where both miss:** **0%** (no overlap bucket).
- **Interpretation:** On missed rugpulls, intent and behavior fail on **different** subsets; there is **no** shared “hard core” of double-misses in this run. That does **not** imply hybrid beats intent on F1 (see ablation: hybrid ~ intent): fixing behavior’s FN may not move the fused model if intent already dominates probability mass.

---

## Sample addresses (first 5) for manual follow-up

**Only intent misses (6 total):** e.g. `0x2bba3cf6de6058cc1b4457ce00deb359e2703d7f`, `0x650e3e3feab7736181b1a23953f3af6c0462e5f4`, …

**Only behavior misses (67 total):** e.g. `0x9e7ce36dbd1a9a6c6e80d08e38077745855edd3a`, `0xeac8976401037b0f1a706d915285d442423b9b3c`, …

*(Full console log: [`paper_evidence/paper_diagnostic_bundle.txt`](paper_evidence/paper_diagnostic_bundle.txt).)*

---

## Still TODO

- [ ] **Hybrid** bucket (same CV): FN/FP for hybrid vs intent-only vs behavior-only for direct “who fixes whom” stories.
- [ ] Stratify FN/FP by **`slither_ok`** and Slither failure rows (~7% of corpus).
- [ ] Optional **manual review** of a small sample (`manual_annotations.csv` protocol).
- [ ] Short qualitative appendix (3–5 examples) if venue allows.

---

*Last updated: 2026-04-09 — Table 1–2 filled from `tools/paper_diagnostic_bundle.py`.*
