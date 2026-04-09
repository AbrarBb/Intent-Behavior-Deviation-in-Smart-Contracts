# Paper narrative (chosen arc)

This file records the **editorial choice** for how the manuscript tells the story, aligned with [`STAGE2_WORKFLOW.md`](STAGE2_WORKFLOW.md) paths A–C.

## Chosen story: **Path A** (Slither-backed corpus + ablation-first evidence)

**Path A** means: the paper’s main quantitative thread is built on the **canonical verified-full Stage 2 build** with **Slither-enabled** behavior columns (`--enable-slither`), followed by **formal modality ablation** and **post-hoc diagnostics**, without requiring a full **enrichment** rebuild for the core claims.

### Why not B or C as the *primary* story?

| Path | Role in this project |
| --- | --- |
| **A** | **Primary narrative:** reproducible N≈3324 corpus, ~93% Slither success, intent vs behavior vs hybrid under identical CV—this is the defensible contribution test. |
| **B** | **Optional extension:** Slither + **enriched** behavior features on a **full** rebuild—worth it only if enrichment changes conclusions or fills a clear gap (see [`NEXT_PHASE.md`](NEXT_PHASE.md)). |
| **C** | **Sampling / preview:** tagged small runs (e.g. `--output-tag enrich_preview_100`) to inspect column behavior without overwriting canonical artifacts. |

### Key findings to anchor the manuscript

1. **Coverage:** Slither succeeds on **~93%** of contracts; **~7%** fail compilation/analysis—report honestly and optionally bucket failures (see [`ERROR_ANALYSIS_TODO.md`](ERROR_ANALYSIS_TODO.md)).

2. **Formal ablation (primary):** On 5-fold stratified CV (verified-full, Slither-enabled CSV), **intent-only** sits at a **high ceiling** (F1 ≈ **0.985**, AUC ≈ **0.995**). **Behavior-only** is **strong** after Stage 2 (F1 ≈ **0.953**, AUC ≈ **0.964**), versus the historical **regex-only / zero-Slither** behavior-only baseline (~**0.69** F1). **Hybrid** tracks **intent** on F1 (~**0.985**)—do **not** oversell hybrid lift; emphasize **honest modality comparison** and **Slither’s impact on the behavior block**.

3. **MDI (secondary):** Mean decrease in impurity still concentrates on **embedding dimensions** (~99.8% intent mass vs ~0.2% behavior in aggregate)—expected with many continuous dims vs few flags. **Cite ablation for “does behavior matter?”**; use MDI only as qualitative introspection, per [`METHODOLOGY.md`](METHODOLOGY.md).

4. **Framing:** Position the work as a **reproducible intent+behavior pipeline** with **explicit limitations** (weak labels, verification bias, Slither gaps), not as “hybrid always wins on every metric.”

### Cross-references

- Numbers and tables: [`PROJECT_EXECUTION_REPORT.md`](PROJECT_EXECUTION_REPORT.md) §5, [`METHODOLOGY.md`](METHODOLOGY.md) §12–13.
- Workflow and backups: [`STAGE2_WORKFLOW.md`](STAGE2_WORKFLOW.md), `docs/paper_evidence/`.
