#!/usr/bin/env python3
"""
Phase 1 — Data Balancing (Master Dataset Construction)
======================================================
Research context: Intent–Behavior Deviation Detection in Smart Contracts.

This script fuses a curated rug-pull corpus (malicious, label=1) with verified
benign contracts from the SmartBugs Wild baseline (label=0), restricted to
Ethereum mainnet addresses for the malicious arm. The benign cohort is
subsampled to match the malicious count exactly, yielding a balanced 50/50
master manifest consumed by the acquisition phase (02_download_contracts.py).

References (implicit): SmartBugs Wild / ICSE 2020 for the benign pool;
project-specific CSV for labeled rug pulls.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths (resolved relative to this script for reproducible runs from any CWD)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
RUGPULL_CSV = SCRIPT_DIR / "rugpull_full_dataset_new (1).csv"
BENIGN_CSV = SCRIPT_DIR / "all_contract.csv"
OUTPUT_CSV = SCRIPT_DIR / "master_dataset.csv"


def main() -> None:
    # --- Malicious (rug pull) subset: Ethereum only --------------------------------
    rugpull_df = pd.read_csv(RUGPULL_CSV)
    eth_malicious = rugpull_df.loc[rugpull_df["Chain"] == "ETH"].copy()
    eth_malicious = eth_malicious[["address"]].assign(label=1)

    # Drop rows without a usable address (defensive; keeps counts well-defined)
    eth_malicious = eth_malicious.dropna(subset=["address"])
    eth_malicious["address"] = eth_malicious["address"].astype(str).str.strip()
    eth_malicious = eth_malicious[eth_malicious["address"] != ""]

    n_malicious = len(eth_malicious)

    # --- Benign (SmartBugs Wild–style) pool ----------------------------------------
    benign_df = pd.read_csv(
        BENIGN_CSV,
        header=None,
        names=["address", "tx_count"],
        low_memory=False,
    )
    benign_df = benign_df.dropna(subset=["address"])
    benign_df["address"] = benign_df["address"].astype(str).str.strip()
    benign_df = benign_df[benign_df["address"] != ""]

    if n_malicious > len(benign_df):
        raise ValueError(
            f"Insufficient benign contracts: need {n_malicious} samples but only "
            f"{len(benign_df)} valid rows exist in {BENIGN_CSV.name}."
        )

    # Match malicious cardinality exactly (stratified random subsample, fixed seed)
    benign_sample = benign_df.sample(n=n_malicious, random_state=42).copy()
    benign_sample = benign_sample[["address"]].assign(label=0)

    # --- Merge and permute -----------------------------------------------------------
    master = pd.concat([eth_malicious, benign_sample], ignore_index=True)
    master = master.sample(frac=1.0, random_state=42).reset_index(drop=True)

    master.to_csv(OUTPUT_CSV, index=False)

    # --- Reporting -------------------------------------------------------------------
    n_safe = len(benign_sample)
    n_total = len(master)
    print("=" * 60)
    print("Phase 1 - Master dataset (balanced manifest)")
    print("=" * 60)
    print(f"  Malicious (ETH rug pulls, label=1): {n_malicious}")
    print(f"  Safe (subsampled benign, label=0):  {n_safe}")
    print(f"  Final dataset size (50/50):         {n_total}")
    print(f"  Written to: {OUTPUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
