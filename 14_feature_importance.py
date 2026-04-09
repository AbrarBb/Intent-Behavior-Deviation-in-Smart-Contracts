#!/usr/bin/env python3
"""
Feature importance for the verified-full Random Forest (paper narrative).
Loads ``artifacts/ml_dataset_verified_full.csv``, retrains RF with fixed params,
reports Top 20 features and aggregate Intent (embeddings) vs Behavior shares.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = SCRIPT_DIR / "artifacts" / "ml_dataset_verified_full.csv"

# Default if ``ml_dataset_verified_full_config.json`` has no ``feature_cols``.
BEHAVIOR_COLS_FALLBACK = [
    "owner_withdraw",
    "emergency_withdraw",
    "unrestricted_mint",
    "regex_owner_withdraw",
    "regex_emergency_withdraw",
    "regex_unrestricted_mint",
    "slither_ok",
    "slither_high_count",
    "slither_arbitrary_send",
    "slither_suicidal",
    "slither_unchecked_lowlevel",
    "slither_controlled_delegatecall",
    "slither_delegatecall_loop",
    "slither_ownerish_any",
]


def _behavior_columns_for_csv(csv_path: Path) -> list[str]:
    cfg_path = csv_path.parent / f"{csv_path.stem}_config.json"
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            cols = data.get("feature_cols")
            if isinstance(cols, list) and cols and all(isinstance(c, str) for c in cols):
                return cols
        except (OSError, json.JSONDecodeError):
            pass
    return list(BEHAVIOR_COLS_FALLBACK)


def _emb_columns(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if c.startswith("emb_") and c[4:].isdigit()]
    return sorted(cols, key=lambda x: int(x.split("_")[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to ml_dataset_verified_full.csv")
    args = ap.parse_args()

    if not args.csv.is_file():
        raise SystemExit(f"Dataset not found: {args.csv}")

    df = pd.read_csv(args.csv)
    if "target" not in df.columns:
        raise SystemExit("Expected column 'target' in dataset.")

    emb_cols = _emb_columns(df)
    if len(emb_cols) != 384:
        raise SystemExit(f"Expected 384 emb_* columns, found {len(emb_cols)}")

    behavior_cols = _behavior_columns_for_csv(args.csv)
    missing = [c for c in behavior_cols if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing behavior columns: {missing}")

    y = df["target"].astype(int).to_numpy()
    X = df[emb_cols + behavior_cols].to_numpy(dtype=np.float32)

    clf = RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X, y)

    names = emb_cols + behavior_cols
    imp = pd.DataFrame({"feature": names, "importance": clf.feature_importances_})
    imp = imp.sort_values("importance", ascending=False).reset_index(drop=True)

    print("=" * 60)
    print("Output 1: Top 20 individual features (by importance)")
    print("=" * 60)
    print(imp.head(20).to_string(index=False))
    print()

    mask_emb = imp["feature"].str.startswith("emb_")
    mask_beh = imp["feature"].isin(behavior_cols)

    total_nlp = float(imp.loc[mask_emb, "importance"].sum())
    total_beh = float(imp.loc[mask_beh, "importance"].sum())
    denom = total_nlp + total_beh
    if denom <= 0:
        raise SystemExit("Non-positive total importance (unexpected).")

    pct_nlp = 100.0 * total_nlp / denom
    pct_beh = 100.0 * total_beh / denom

    print("=" * 60)
    print("Output 2: Aggregated pillar importance (percent of Intent+Behavior mass)")
    print("=" * 60)
    print(f"  Total NLP Intent Importance:        {pct_nlp:.2f}%  (raw sum {total_nlp:.6f})")
    print(f"  Total Static Behavior Importance:   {pct_beh:.2f}%  (raw sum {total_beh:.6f})")
    print(f"  (Sanity: sklearn importances sum to {float(imp['importance'].sum()):.6f} over all {len(imp)} features)")
    print("=" * 60)


if __name__ == "__main__":
    main()
