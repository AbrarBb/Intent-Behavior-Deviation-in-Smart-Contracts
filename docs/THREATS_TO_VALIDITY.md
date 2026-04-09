# Threats to validity, limitations, ethics

## Construct validity

- **Labels:** Malicious addresses come from an external rug-pull list; benign from a SmartBugs-style pool. Neither is re-audited contract-by-contract in this pipeline. **Mitigation:** manual `final_label` on a pilot subset; report agreement statistics.
- **Intent proxy:** `intent_text` is derived from comments/NatSpec extraction or short summaries; it may omit marketing claims made off-chain. **Mitigation:** state scope clearly; optional manual paraphrase field.

## Internal validity

- **Data leakage:** Random splits assume contracts are **IID**; forked or template-cloned code may leak labels across train/test. **Mitigation:** deduplicate by bytecode hash or repo, or cluster-level splits in future work.
- **Small N (pilot):** High F1 can be optimistic. **Mitigation:** cross-validation (see `11_run_ablation_experiments.py`), confidence intervals, external validation set.

## External validity

- **Ethereum mainnet only** (`chainid=1` in Etherscan API). Other chains differ in tooling and scam patterns.
- **Time:** Rug-pull lists and verification rates drift; results are snapshots.

## Verification bias

- Contracts **without** Etherscan source are excluded from code-based analysis; the missing-not-at-random pattern can bias class ratios (see `verified_cohort_report.txt`). **Mitigation:** report full vs verified cohorts.

## Tooling

- **Slither** depends on `solc` and may fail; **regex** features are heuristic and can false-positive/false-negative.
- **Sentence-BERT** encodes semantic similarity, not logical entailment between text and code.

## Ethics

- **No financial advice:** This tool is for research; deployment as a “safety guarantee” would be misleading.
- **Responsible disclosure:** Do not use the pipeline to target live contracts for harassment.
- **Data protection:** Annotator identities should follow institutional policy.

## AI disclosure (venue-dependent)

If you use LLMs for drafting, **check the target journal’s** policy on disclosure and authorship.
