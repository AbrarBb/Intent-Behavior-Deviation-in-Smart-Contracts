#!/usr/bin/env python3
"""
Verified-source cohorts for paper-grade reporting (Phase 10)
==========================================================
Reads ``dataset_manifest.csv`` and:

1. Writes ``verified_manifest.csv`` — all rows with ``has_verified_source == 1``
   (true class counts; use this for the *core* code/NLP/Slither claim).

2. Writes ``verified_manifest_balanced_seed42.csv`` — stratified subsample
   with min(label=0, label=1) rows **per class**, shuffled (``random_state=42``).
   Use for fair head-to-head model comparisons or a "50/50 verified" narrative.

3. Writes ``verified_cohort_report.txt`` — human-readable counts for both cohorts
   (supplementary material / copy into Methods).

Run after ``03_build_dataset_manifest.py``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_CSV = SCRIPT_DIR / "dataset_manifest.csv"
VERIFIED_FULL = SCRIPT_DIR / "verified_manifest.csv"
VERIFIED_BALANCED = SCRIPT_DIR / "verified_manifest_balanced_seed42.csv"
REPORT_TXT = SCRIPT_DIR / "verified_cohort_report.txt"
RANDOM_STATE = 42


def main() -> None:
    if not MANIFEST_CSV.is_file():
        raise SystemExit(f"Missing {MANIFEST_CSV.name}. Run 03_build_dataset_manifest.py first.")

    df = pd.read_csv(MANIFEST_CSV)
    if "has_verified_source" not in df.columns or "label" not in df.columns:
        raise SystemExit("dataset_manifest.csv must include has_verified_source and label")

    total_rows = len(df)
    with_src = df[df["has_verified_source"] == 1].copy()
    n_verified = len(with_src)

    c0 = int((with_src["label"] == 0).sum())
    c1 = int((with_src["label"] == 1).sum())

    lines: list[str] = []
    lines.append("Verified-source cohort report")
    lines.append("=" * 60)
    lines.append("")
    lines.append("All addresses (from dataset_manifest.csv):")
    lines.append(f"  Total rows:                      {total_rows}")
    lines.append(f"  With verified source on disk:   {n_verified}")
    lines.append(f"  Without source:                 {total_rows - n_verified}")
    lines.append("")
    lines.append("FULL verified cohort (true class counts - use for primary reporting):")
    lines.append(f"  label=0 (benign arm):           {c0}")
    lines.append(f"  label=1 (malicious arm):       {c1}")
    lines.append(f"  Total analyzable:              {n_verified}")
    if c0 > 0 and c1 > 0:
        ratio = max(c0, c1) / min(c0, c1)
        lines.append(f"  Imbalance ratio (max/min):     {ratio:.4f}")
    lines.append("")
    lines.append(f"Output: {VERIFIED_FULL.name}")

    with_src.to_csv(VERIFIED_FULL, index=False)

    n_each = min(c0, c1) if c0 > 0 and c1 > 0 else 0
    if n_each == 0:
        lines.append("")
        lines.append(
            "BALANCED verified cohort: SKIPPED (one class has zero verified contracts)."
        )
        VERIFIED_BALANCED.unlink(missing_ok=True)
    else:
        s0 = with_src[with_src["label"] == 0].sample(n=n_each, random_state=RANDOM_STATE)
        s1 = with_src[with_src["label"] == 1].sample(n=n_each, random_state=RANDOM_STATE)
        bal = pd.concat([s0, s1], ignore_index=True)
        bal = bal.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)
        bal.to_csv(VERIFIED_BALANCED, index=False)

        lines.append("")
        lines.append(
            f"BALANCED verified cohort (seed={RANDOM_STATE}, n per class = {n_each}):"
        )
        lines.append(f"  label=0:                         {n_each}")
        lines.append(f"  label=1:                         {n_each}")
        lines.append(f"  Total rows:                      {len(bal)}")
        lines.append(f"Output: {VERIFIED_BALANCED.name}")
        lines.append("")
        lines.append(
            "Note: balanced file drops abs(c0-c1) contracts from the majority class; "
            "report both tables in the paper."
        )

    text = "\n".join(lines) + "\n"
    REPORT_TXT.write_text(text, encoding="utf-8")

    print(text)
    print(f"Written: {REPORT_TXT}")


if __name__ == "__main__":
    main()
