#!/usr/bin/env python3
"""
One-shot diagnostics for manuscript tables: modality disagreement (CV), behavior-only
MDI split (Slither vs regex vs heuristic), enrichment preview coverage.

Uses the same column logic as ``15_ablation_study.py`` (``target``, ``address``,
``feature_cols`` from ``*_config.json`` next to CSV).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

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

RANDOM_STATE = 42
N_SPLITS = 5
POS_LABEL = 1


def _emb_columns(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if c.startswith("emb_") and c[4:].isdigit()]
    return sorted(cols, key=lambda x: int(x.split("_")[1]))


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


def run_modality_disagreement(csv_path: Path) -> None:
    df = pd.read_csv(csv_path)
    if "target" not in df.columns:
        raise SystemExit("Expected column 'target'.")
    id_col = "address" if "address" in df.columns else None

    emb_cols = _emb_columns(df)
    behavior_cols = _behavior_columns_for_csv(csv_path)
    for c in behavior_cols:
        if c not in df.columns:
            raise SystemExit(f"Missing behavior column: {c}")

    y = df["target"].astype(int).to_numpy()
    n_pos = int((y == POS_LABEL).sum())
    n_neg = int((y != POS_LABEL).sum())

    X_intent = df[emb_cols].to_numpy(dtype=np.float32)
    X_behavior = df[behavior_cols].to_numpy(dtype=np.float32)

    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)

    intent_fn_ids: list = []
    behavior_fn_ids: list = []
    intent_fp_ids: list = []
    behavior_fp_ids: list = []

    for train_idx, test_idx in skf.split(X_intent, y):
        y_train, y_test = y[train_idx], y[test_idx]
        rf_i = RandomForestClassifier(
            n_estimators=100,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            n_jobs=-1,
        )
        rf_b = RandomForestClassifier(
            n_estimators=100,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            n_jobs=-1,
        )
        rf_i.fit(X_intent[train_idx], y_train)
        rf_b.fit(X_behavior[train_idx], y_train)
        pred_i = rf_i.predict(X_intent[test_idx])
        pred_b = rf_b.predict(X_behavior[test_idx])

        if id_col:
            test_ids = df.iloc[test_idx][id_col].values
        else:
            test_ids = test_idx

        fn_mask = (pred_i == 0) & (y_test == POS_LABEL)
        fn_mask_b = (pred_b == 0) & (y_test == POS_LABEL)
        fp_mask = (pred_i == 1) & (y_test != POS_LABEL)
        fp_mask_b = (pred_b == 1) & (y_test != POS_LABEL)

        intent_fn_ids.extend(test_ids[fn_mask])
        behavior_fn_ids.extend(test_ids[fn_mask_b])
        intent_fp_ids.extend(test_ids[fp_mask])
        behavior_fp_ids.extend(test_ids[fp_mask_b])

    intent_fn_set = set(intent_fn_ids)
    behavior_fn_set = set(behavior_fn_ids)
    intent_fp_set = set(intent_fp_ids)
    behavior_fp_set = set(behavior_fp_ids)

    both_miss_fn = intent_fn_set & behavior_fn_set
    only_intent_miss_fn = intent_fn_set - behavior_fn_set
    only_behavior_miss_fn = behavior_fn_set - intent_fn_set
    union_fn = intent_fn_set | behavior_fn_set

    both_miss_fp = intent_fp_set & behavior_fp_set
    only_intent_miss_fp = intent_fp_set - behavior_fp_set
    only_behavior_miss_fp = behavior_fp_set - intent_fp_set
    union_fp = intent_fp_set | behavior_fp_set

    def pct(part: int, whole: int) -> float:
        return 100.0 * part / whole if whole else 0.0

    print("=" * 80)
    print("ERROR ANALYSIS: MODALITY DISAGREEMENT (5-fold CV, threshold 0.5)")
    print("=" * 80)
    print(f"Dataset: {csv_path.name}")
    print(f"Positive class (rugpull): {n_pos} | Negative (safe): {n_neg}")
    print()

    print("FALSE NEGATIVES (predicted safe, actual rugpull)")
    print("-" * 80)
    ufn = len(union_fn)
    print(f"Both modalities miss:         {len(both_miss_fn):5d}  ({pct(len(both_miss_fn), ufn):5.1f}% of union FN | {pct(len(both_miss_fn), n_pos):5.1f}% of all rugpulls)")
    print(f"Only intent misses:           {len(only_intent_miss_fn):5d}  ({pct(len(only_intent_miss_fn), ufn):5.1f}% of union FN | {pct(len(only_intent_miss_fn), n_pos):5.1f}% of all rugpulls)")
    print(f"Only behavior misses:         {len(only_behavior_miss_fn):5d}  ({pct(len(only_behavior_miss_fn), ufn):5.1f}% of union FN | {pct(len(only_behavior_miss_fn), n_pos):5.1f}% of all rugpulls)")
    print(f"Total unique FN (union):      {ufn:5d}")
    print()

    print("FALSE POSITIVES (predicted rugpull, actual safe)")
    print("-" * 80)
    ufp = len(union_fp)
    print(f"Both modalities flag:         {len(both_miss_fp):5d}  ({pct(len(both_miss_fp), ufp):5.1f}% of union FP | {pct(len(both_miss_fp), n_neg):5.1f}% of all safe)")
    print(f"Only intent flags:            {len(only_intent_miss_fp):5d}  ({pct(len(only_intent_miss_fp), ufp):5.1f}% of union FP | {pct(len(only_intent_miss_fp), n_neg):5.1f}% of all safe)")
    print(f"Only behavior flags:          {len(only_behavior_miss_fp):5d}  ({pct(len(only_behavior_miss_fp), ufp):5.1f}% of union FP | {pct(len(only_behavior_miss_fp), n_neg):5.1f}% of all safe)")
    print(f"Total unique FP (union):      {ufp:5d}")
    print()

    overlap_fn = pct(len(both_miss_fn), ufn) if ufn else 0.0
    print("COMPLEMENTARITY (FN union)")
    print("-" * 80)
    print(f"Share of union FN where BOTH miss: {overlap_fn:.1f}%")
    if ufn and overlap_fn >= 80:
        print("Interpretation: high overlap on FN -> modalities largely redundant on misses.")
    elif ufn and overlap_fn < 50:
        print("Interpretation: lower overlap -> each modality misses different rugpulls (complementarity).")
    else:
        print("Interpretation: moderate overlap -> partial complementarity.")
    print()
    print("Sample addresses (first 5 per category, FN):")
    print(f"  Both miss:          {list(both_miss_fn)[:5]}")
    print(f"  Only intent misses: {list(only_intent_miss_fn)[:5]}")
    print(f"  Only behavior miss: {list(only_behavior_miss_fn)[:5]}")
    print()


def run_behavior_mdi(csv_path: Path, top_n: int) -> None:
    df = pd.read_csv(csv_path)
    if "target" not in df.columns:
        raise SystemExit("Expected column 'target'.")
    behavior_cols = _behavior_columns_for_csv(csv_path)
    X = df[behavior_cols].to_numpy(dtype=np.float32)
    y = df["target"].astype(int).to_numpy()

    rf = RandomForestClassifier(
        n_estimators=100,
        random_state=RANDOM_STATE,
        class_weight="balanced",
        n_jobs=-1,
    )
    rf.fit(X, y)
    importances = rf.feature_importances_
    order = np.argsort(importances)[::-1]

    print("=" * 80)
    print("BEHAVIOR-ONLY FEATURE IMPORTANCE (MDI, full fit)")
    print("=" * 80)
    print(f"Top {top_n}:")
    for rank, idx in enumerate(order[:top_n], 1):
        col = behavior_cols[int(idx)]
        print(f"  {rank:2d}. {col:42s} {importances[idx]:.6f}")

    slither_sum = sum(
        importances[i] for i, c in enumerate(behavior_cols) if c.startswith("slither_")
    )
    regex_sum = sum(
        importances[i] for i, c in enumerate(behavior_cols) if c.startswith("regex_")
    )
    heuristic_sum = sum(
        importances[i]
        for i, c in enumerate(behavior_cols)
        if not c.startswith("slither_") and not c.startswith("regex_")
    )
    total = slither_sum + regex_sum + heuristic_sum
    print()
    print("Aggregate MDI mass (behavior block)")
    print("-" * 80)
    if total > 0:
        print(f"  slither_* :     {100 * slither_sum / total:5.1f}%")
        print(f"  regex_* :       {100 * regex_sum / total:5.1f}%")
        print(f"  heuristics:     {100 * heuristic_sum / total:5.1f}%  (owner_withdraw, emergency_withdraw, unrestricted_mint)")
    print()


ENRICHED_FEATURE_NAMES: tuple[str, ...] = (
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
)


def run_enrichment_preview(csv_path: Path) -> None:
    if not csv_path.is_file():
        print(f"(Skip) Enrichment preview CSV not found: {csv_path}")
        return
    df = pd.read_csv(csv_path)
    names = [n for n in ENRICHED_FEATURE_NAMES if n in df.columns]

    print("=" * 80)
    print(f"ENRICHMENT PREVIEW: {csv_path.name} (n={len(df)})")
    print("=" * 80)
    nz_pcts: list[float] = []
    for col in names:
        nz = (df[col] > 0).sum()
        p = 100.0 * nz / len(df)
        nz_pcts.append(p)
        print(f"  {col:42s}  {p:6.2f}%  ({nz}/{len(df)})")
    if nz_pcts:
        avg = float(np.mean(nz_pcts))
        print()
        print(f"Mean non-zero rate (listed columns): {avg:.2f}%")
        print("-" * 80)
        if avg >= 15:
            print("Note: relatively high average activation on this sample (threshold 15% is arbitrary).")
        elif avg >= 5:
            print("Note: moderate activation; may add marginal signal.")
        else:
            print("Note: sparse activation on this sample; enrichment may be low-yield for lift.")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        type=Path,
        default=REPO_ROOT / "artifacts" / "ml_dataset_verified_full.csv",
    )
    ap.add_argument(
        "--enrichment-csv",
        type=Path,
        default=REPO_ROOT / "artifacts" / "ml_dataset_verified_full_enrich_preview_100.csv",
    )
    ap.add_argument("--top-behavior", type=int, default=10)
    args = ap.parse_args()

    if not args.csv.is_file():
        raise SystemExit(f"Missing: {args.csv}")

    run_modality_disagreement(args.csv)
    run_behavior_mdi(args.csv, args.top_behavior)
    run_enrichment_preview(args.enrichment_csv)


if __name__ == "__main__":
    main()
