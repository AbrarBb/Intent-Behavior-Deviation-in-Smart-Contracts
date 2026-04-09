# Next phase — Q2: is enrichment worth a full rebuild?

**Question:** Should we run a **full-corpus** rebuild with **`--enable-enriched-features`** (optionally still with Slither), given time and risk of overwriting canonical artifacts?

This doc combines the **decision checklist** with **diagnostic outputs** from [`tools/paper_diagnostic_bundle.py`](../tools/paper_diagnostic_bundle.py) (behavior-only MDI + enrichment preview). See [`STAGE2_WORKFLOW.md`](STAGE2_WORKFLOW.md) Path B vs Path C.

---

## What enrichment adds

- Extra behavior columns from [`06b_extract_enriched_behavior_features.py`](../06b_extract_enriched_behavior_features.py) (binary enriched features), appended when `12_build_verified_full_ml_dataset.py` is run with **`--enable-enriched-features`**.
- **Preview without overwriting:** use **`--output-tag`** (e.g. `enrich_preview_100`) and optionally **`--max-contracts`** (Path C–style).

---

## Diagnostic A — Behavior-only MDI (full fit, behavior columns only)

Trained on **all rows** (not CV): same 14 `feature_cols` as Stage 2. **MDI** is descriptive; use with ablation, not as causal attribution.

### Top 10 behavior features (MDI)

| Rank | Feature | MDI |
| ---: | --- | ---: |
| 1 | `slither_ownerish_any` | 0.214 |
| 2 | `owner_withdraw` | 0.209 |
| 3 | `slither_high_count` | 0.196 |
| 4 | `slither_controlled_delegatecall` | 0.126 |
| 5 | `regex_unrestricted_mint` | 0.087 |
| 6 | `unrestricted_mint` | 0.061 |
| 7 | `slither_unchecked_lowlevel` | 0.054 |
| 8 | `slither_arbitrary_send` | 0.016 |
| 9 | `regex_owner_withdraw` | 0.013 |
| 10 | `emergency_withdraw` | 0.009 |

### Aggregate MDI mass (within behavior block)

| Group | Share |
| --- | ---: |
| `slither_*` | 61.4% |
| `regex_*` | 10.7% |
| Heuristics (`owner_withdraw`, `emergency_withdraw`, `unrestricted_mint`) | 27.9% |

**Takeaway:** Slither-backed columns and the three heuristic flags together carry most of the **behavior-only** MDI; regex overlays are non-negligible (~11%).

---

## Diagnostic B — Enrichment preview (`enrich_preview_100`)

**File:** `artifacts/ml_dataset_verified_full_enrich_preview_100.csv` (n=100; Slither was off in that preview run by design — see [`STAGE2_WORKFLOW.md`](STAGE2_WORKFLOW.md)).

**Mean non-zero rate** across the 10 enriched columns: **4.70%**.

Per-column non-zero rates (highest first): `has_selfdestruct_or_delegatecall` **30%**; `has_fallback` **8%**; others mostly sparse on this slice.

**Copilot-style threshold (informal):** mean &lt;5% → treat as **sparse** on this sample; full Path B rebuild is **not** clearly justified by prevalence alone unless you revise patterns or need appendix sensitivity numbers.

---

## When a full rebuild (Path B) is justified

Consider **yes** if most of the following apply:

- [ ] Enrichment columns show **non-trivial activation** on a preview run and are not redundant with existing Slither/regex flags. *(Preview n=100: **sparse** mean rate; one column is active on 30% of rows.)*
- [ ] You need **paper numbers** (ablation, MDI) on the **same stem** as “final” behavior definition—including enriched dims—or reviewers expect **full N** statistics.
- [ ] You have **1–3+ hours** (or more with Slither) and have **backed up** `artifacts/ml_dataset_verified_full*` before replacing the default stem.

Consider **defer or tag-only** if:

- [x] Preview shows **sparse** signal on average (mean non-zero **4.7%** on 100-contract preview).
- [x] Core claims already rest on **Path A** ablation ([`PAPER_NARRATIVE.md`](PAPER_NARRATIVE.md)); enrichment would be a **sensitivity** appendix, not a new main claim.
- [ ] You prefer to spend effort on **Slither failure** remediation or **hybrid** error analysis first ([`ERROR_ANALYSIS_TODO.md`](ERROR_ANALYSIS_TODO.md)).

---

## Safe workflow if you proceed

1. **Backup:** `.\tools\backup_verified_full_artifacts.ps1`
2. **Either** replace canonical stem deliberately **or** use `--output-tag full_enrich_YYYYMMDD` until metrics are frozen.
3. Re-run **`15_ablation_study.py`**, **`14_feature_importance.py`**, **`tools/post_stage2_diagnostics.py`** on the new CSV/NPZ.
4. Update [`PROJECT_EXECUTION_REPORT.md`](PROJECT_EXECUTION_REPORT.md) §5 and `docs/paper_evidence/` snapshots.

---

## Decision

| Field | Value |
| --- | --- |
| **Decision** | **Defer** full canonical Path B rebuild; optional **tagged** full run later if enrichment heuristics are improved or a supplementary table is required. |
| **Date** | 2026-04-09 |
| **Rationale** | Enrichment preview shows **low average activation** (4.7% mean across 10 columns on n=100); Stage 2 **Path A** evidence is already decision-ready. Revisit after Slither-failure fixes or enriched-pattern redesign. |

---

*Linked narrative choice: [`PAPER_NARRATIVE.md`](PAPER_NARRATIVE.md). Regenerate diagnostics: `python tools/paper_diagnostic_bundle.py`.*
