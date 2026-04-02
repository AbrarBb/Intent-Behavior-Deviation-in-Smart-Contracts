#!/usr/bin/env python3
"""
Phase 3 — Dataset manifest (post-acquisition)
=============================================
Joins `master_dataset.csv` labels with files under `raw_data/<address>/` to
produce a single CSV usable for NLP (comments), Slither, and reproducible
paper tables. Run after `02_download_contracts.py` finishes.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
MASTER_CSV = SCRIPT_DIR / "master_dataset.csv"
RAW_DATA_DIR = SCRIPT_DIR / "raw_data"
OUTPUT_CSV = SCRIPT_DIR / "dataset_manifest.csv"


def main() -> None:
    master = pd.read_csv(MASTER_CSV)
    rows: list[dict] = []

    for _, rec in master.iterrows():
        addr = str(rec["address"]).strip()
        label = int(rec["label"])
        sub = RAW_DATA_DIR / addr
        sol_files = sorted(sub.glob("*.sol")) if sub.is_dir() else []
        if sol_files:
            rel = sol_files[0].relative_to(SCRIPT_DIR).as_posix()
            rows.append(
                {
                    "address": addr,
                    "label": label,
                    "sol_path": rel,
                    "has_verified_source": 1,
                }
            )
        else:
            rows.append(
                {
                    "address": addr,
                    "label": label,
                    "sol_path": "",
                    "has_verified_source": 0,
                }
            )

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_CSV, index=False)

    n_ok = int(out["has_verified_source"].sum())
    n_total = len(out)
    print("=" * 60)
    print("Phase 3 - Dataset manifest")
    print("=" * 60)
    print(f"  Rows in master:           {n_total}")
    print(f"  With .sol on disk:        {n_ok}")
    print(f"  Missing / unverified:     {n_total - n_ok}")
    print(f"  Written: {OUTPUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
