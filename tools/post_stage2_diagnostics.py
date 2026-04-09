#!/usr/bin/env python3
"""
Path A diagnostics: Slither coverage from build config + non-zero rates on CSV.

Usage:
  python tools/post_stage2_diagnostics.py
  python tools/post_stage2_diagnostics.py --csv artifacts/ml_dataset_verified_full.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        type=Path,
        default=SCRIPT_DIR / "artifacts" / "ml_dataset_verified_full.csv",
        help="Flat dataset CSV (default: artifacts/ml_dataset_verified_full.csv).",
    )
    args = ap.parse_args()
    csv_path = args.csv.resolve()
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import pandas as pd
    except ImportError:
        print("Requires pandas.", file=sys.stderr)
        sys.exit(1)

    cfg_path = csv_path.parent / f"{csv_path.stem}_config.json"
    if not cfg_path.is_file():
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    total = int(cfg.get("total_contracts") or cfg.get("kept_contracts") or 0)
    ok = int(cfg.get("slither_ok_count", 0))
    failed = int(cfg.get("slither_fail_count", 0))

    df = pd.read_csv(csv_path)
    n = len(df)

    print("=" * 60)
    print("BUILD CONFIG SUMMARY")
    print("=" * 60)
    print(f"Config:              {cfg_path.name}")
    print(f"Output stem:         {cfg.get('output_stem', csv_path.stem)}")
    print(f"Rows in CSV:         {n}")
    print(f"Slither enabled:     {cfg.get('slither_enabled')}")
    print(f"Enriched enabled:    {cfg.get('enriched_features_enabled')}")
    print(f"Behavior columns:    {len(cfg.get('feature_cols') or [])}")
    print()

    print("=" * 60)
    print("SLITHER COVERAGE (from config)")
    print("=" * 60)
    if total > 0:
        print(f"Total contracts (kept): {total}")
        print(f"Slither OK:             {ok} ({100.0 * ok / total:.1f}%)")
        print(f"Slither failed:         {failed} ({100.0 * failed / total:.1f}%)")
    else:
        print("(total_contracts is 0 or missing — check build.)")
    print()

    slither_cols = [
        "slither_ok",
        "slither_high_count",
        "slither_arbitrary_send",
        "slither_suicidal",
        "slither_unchecked_lowlevel",
        "slither_controlled_delegatecall",
        "slither_delegatecall_loop",
        "slither_ownerish_any",
    ]

    print("=" * 60)
    print("BEHAVIOR COLUMN NON-ZERO RATES (Slither-related)")
    print("=" * 60)
    for col in slither_cols:
        if col not in df.columns:
            print(f"{col:35s}: (missing)")
            continue
        s = pd.to_numeric(df[col], errors="coerce").fillna(0)
        nz = int((s > 0).sum())
        pct = 100.0 * nz / n if n else 0.0
        print(f"{col:35s}: {pct:6.2f}% ({nz:5d}/{n:5d})")

    enriched_cols = [
        "approve_restricted_to_owner",
        "transfer_restricted",
        "burn_restricted",
        "liquidity_removal_guarded",
        "unguarded_public_state_mutation",
        "owner_hardcoded",
        "has_selfdestruct_or_delegatecall",
        "asymmetric_liquidity_flow",
        "has_fallback",
        "liquidity_asymmetric_no_remove",
    ]
    if any(c in df.columns for c in enriched_cols):
        print()
        print("=" * 60)
        print("ENRICHMENT COLUMN NON-ZERO RATES (if present)")
        print("=" * 60)
        for col in enriched_cols:
            if col not in df.columns:
                continue
            s = pd.to_numeric(df[col], errors="coerce").fillna(0)
            nz = int((s > 0).sum())
            pct = 100.0 * nz / n if n else 0.0
            print(f"{col:40s}: {pct:6.2f}% ({nz:5d}/{n:5d})")

    print()
    if n < 1000:
        print(
            "NOTE: Row count is small — this may be a smoke test artifact, not full Stage 2.",
        )
        print("      Re-run 12_build without --max-contracts (and without clobbering backups).")
    print()


if __name__ == "__main__":
    main()
