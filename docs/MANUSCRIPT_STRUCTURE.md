# Manuscript structure and venue shortlist

## Suggested paper outline (IEEE/ACM-style)

1. **Abstract** (150–250 words): problem, gap (paired intent–behavior), method, key metric, limitation.
2. **Introduction**: motivation (rug pulls); contributions (numbered, match `docs/CONTRIBUTIONS.md`).
3. **Related work**: NLP on contracts; static analysis; rug-pull / DeFi scam detection; **gap statement**.
4. **Background**: Ethereum contracts, Etherscan verification, intent vs behavior terminology.
5. **Method**:
   - Data construction (Phases 1–3, 10) — cite cohort tables.
   - Intent extraction and embedding (Phase 5).
   - Behavior features (Phase 6) — regex vs Slither.
   - Classification and ablations (Phases 8, 11).
6. **Experiments**:
   - Datasets and statistics (`docs/COHORT_TABLES.md`).
   - Baselines: hybrid vs intent-only vs behavior-only vs hybrid without Slither (`artifacts/ablation_report.md`).
   - Metrics: Precision, Recall, F1 per class; confusion matrices.
   - Error analysis: qualitative cases from `pilot_data/`.
7. **Discussion**: when the method fails; ethics; no financial advice.
8. **Threats to validity** (`docs/THREATS_TO_VALIDITY.md`).
9. **Conclusion** and future work (multi-chain, richer NL, formal alignment).
10. **Acknowledgments / funding**.
11. **References**.

## Supplementary material

- `docs/ANNOTATION_PROTOCOL.md` (full guidelines).
- `artifacts/ablation_results.json` (raw metrics).
- Hyperparameters (fixed in `08_train_models.py` / `11_run_ablation_experiments.py`).
- Optional: annotation spreadsheet (anonymized).

## Venue shortlist (illustrative — verify Q1 status in your institution’s catalog)

| Type | Examples (verify recency and scope) |
|------|-------------------------------------|
| Security / blockchain | IEEE TIFS, IEEE TDSC, journals in blockchain security (check SJR/SCImago Q1). |
| Software engineering | IEEE TSE, ACM TOSEM, EMSE. |
| Applied ML + systems | IEEE TKDE (if ML framing dominates). |

**Conference alternative (often faster review):** IEEE S&P, USENIX Security, CCS, NDSS (security); ICSE, FSE, ASE (SE)—**not** Q1 journals but top venues.

**Action:** Pick **one** target and download the **author kit** (LaTeX template, page limit, anonymization rules).

## Formatting checklist

- [ ] Page limit and anonymization (double-blind if required).
- [ ] Reference style (IEEE, ACM, APA).
- [ ] Figure resolution (vector PDF preferred).
- [ ] Data/code availability statement.
- [ ] Conflict of interest / AI disclosure.

## One-sentence positioning (reuse in cover letter)

> We present the first systematic pipeline to pair **intent embeddings** with **static-analysis behavior features** on the same Ethereum contracts, with **transparent verified-source cohorts** and **human-auditable** labels for rug-pull–style deviation detection.
