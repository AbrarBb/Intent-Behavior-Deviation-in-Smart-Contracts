# Reproducibility and third-party artifacts

## Environment

1. Python 3.10+ (3.14 used in development).
2. Install dependencies:

```bash
pip install pandas
pip install -r requirements-research.txt
```

3. Optional: frozen lock from a machine that completed training:

```bash
pip freeze > requirements-frozen.txt
```

Commit `requirements-frozen.txt` when you freeze a paper artifact snapshot.

## Data availability

| Asset | Source |
|-------|--------|
| Rug-pull addresses | Your curated CSV (`rugpull_full_dataset_new (1).csv`) — cite original incident databases / papers as applicable. |
| Benign pool | SmartBugs Wild–style `all_contract.csv` — cite ICSE 2020 SmartBugs. |
| On-chain source | Ethereum via **Etherscan API** — cite Etherscan terms of use. |

### Zenodo / institutional archive

- Upload a **snapshot** of: `master_dataset.csv`, `dataset_manifest.csv`, `verified_manifest.csv`, `verified_cohort_report.txt`, pilot `manual_annotations.csv` (if ethics allow), and `artifacts/` from a tagged run.
- **DOI placeholder:** `10.5281/zenodo.XXXXXXX` (replace after upload).

## Code availability

- Point reviewers to the **public Git repository** (commit hash) used for the paper’s experiments.
- Tag a release: e.g. `v1.0-paper`.

## Tool citations (examples)

- **Slither:** Feist et al., “Slither: A Static Analysis Framework For Smart Contracts,” WETSEB 2019.
- **Sentence Transformers / MiniLM:** Reimers & Gurevych, “Sentence-BERT,” EMNLP 2019; sentence-transformers library.
- **scikit-learn:** Pedregosa et al., JMLR 2011.
- **Etherscan:** API documentation and attribution per [etherscan.io](https://etherscan.io) terms.

## Reproduction checklist

1. `python 01_build_master_dataset.py`
2. Set `ETHERSCAN_API_KEY`, run `python 02_download_contracts.py`
3. `python 03_build_dataset_manifest.py`
4. `python 10_verified_source_cohorts.py`
5. `python 04_prepare_pilot_100.py` (optional `--from-verified-balanced`)
6. Edit `manual_annotations.csv` per `docs/ANNOTATION_PROTOCOL.md`
7. `python 05_embed_intent.py` … `python 08_train_models.py`
8. `python 11_run_ablation_experiments.py`

Record **Git commit**, **Python version**, and **`pip freeze`** output in supplementary material.
