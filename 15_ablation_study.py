#!/usr/bin/env python3
"""
Formal ablation study on verified-full data (addresses MDI importance bias narrative).

Trains RandomForest with stratified 5-fold CV on:
  - Intent-only (384 emb_*)
  - Behavior-only (14 tabular features)
  - Hybrid (398 = intent + behavior)

Reports mean F1 (positive class = rugpull) and mean ROC-AUC per setting.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = SCRIPT_DIR / "artifacts" / "ml_dataset_verified_full.csv"

BEHAVIOR_COLS = [
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
POS_LABEL = 1  # rugpull


def _emb_columns(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if c.startswith("emb_") and c[4:].isdigit()]
    return sorted(cols, key=lambda x: int(x.split("_")[1]))


def cv_mean_f1_auc(
    X: np.ndarray,
    y: np.ndarray,
    clf: RandomForestClassifier,
    cv: StratifiedKFold,
) -> tuple[float, float]:
    f1_scores: list[float] = []
    auc_scores: list[float] = []

    for train_idx, test_idx in cv.split(X, y):
        clf.fit(X[train_idx], y[train_idx])
        y_prob = clf.predict_proba(X[test_idx])[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)
        f1_scores.append(
            float(f1_score(y[test_idx], y_pred, pos_label=POS_LABEL, zero_division=0))
        )
        try:
            auc_scores.append(float(roc_auc_score(y[test_idx], y_prob)))
        except ValueError:
            auc_scores.append(float("nan"))

    mean_f1 = float(np.nanmean(f1_scores))
    mean_auc = float(np.nanmean(auc_scores))
    return mean_f1, mean_auc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = ap.parse_args()

    if not args.csv.is_file():
        raise SystemExit(f"Dataset not found: {args.csv}")

    df = pd.read_csv(args.csv)
    if "target" not in df.columns:
        raise SystemExit("Expected column 'target'.")

    emb_cols = _emb_columns(df)
    if len(emb_cols) != 384:
        raise SystemExit(f"Expected 384 emb_* columns, found {len(emb_cols)}")

    missing = [c for c in BEHAVIOR_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing behavior columns: {missing}")

    y = df["target"].astype(int).to_numpy()
    X_intent = df[emb_cols].to_numpy(dtype=np.float32)
    X_behavior = df[BEHAVIOR_COLS].to_numpy(dtype=np.float32)
    X_hybrid = np.hstack([X_intent, X_behavior]).astype(np.float32)

    base_clf = lambda: RandomForestClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    cv = StratifiedKFold(
        n_splits=N_SPLITS,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    intent_f1, intent_auc = cv_mean_f1_auc(X_intent, y, base_clf(), cv)
    beh_f1, beh_auc = cv_mean_f1_auc(X_behavior, y, base_clf(), cv)
    hyb_f1, hyb_auc = cv_mean_f1_auc(X_hybrid, y, base_clf(), cv)

    rows = [
        ("Intent-Only", intent_f1, intent_auc),
        ("Behavior-Only", beh_f1, beh_auc),
        ("Hybrid (Proposed)", hyb_f1, hyb_auc),
    ]

    print()
    print("## Ablation study: stratified 5-fold CV")
    print()
    print(f"- **Dataset:** `{args.csv.name}`")
    print(f"- **Classifier:** `RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state={RANDOM_STATE})`")
    print(f"- **CV:** `StratifiedKFold(n_splits={N_SPLITS}, shuffle=True, random_state={RANDOM_STATE})`")
    print(f"- **Positive class:** {POS_LABEL} (rugpull)")
    print()
    print("| Model | Mean F1 (rugpull) | Mean ROC-AUC |")
    print("|---|---:|---:|")
    for name, mf1, mauc in rows:
        auc_str = f"{mauc:.4f}" if np.isfinite(mauc) else "nan"
        print(f"| {name} | {mf1:.4f} | {auc_str} |")
    print()

    if intent_f1 > 0:
        pct = 100.0 * (hyb_f1 - intent_f1) / intent_f1
        print(
            f"**Hybrid vs Intent-Only (F1 improvement):** {pct:+.2f}% "
            f"(relative increase of hybrid mean F1 over intent-only mean F1)."
        )
    else:
        print(
            "**Hybrid vs Intent-Only (F1 improvement):** undefined (intent-only mean F1 is 0)."
        )

    if intent_auc > 0 and np.isfinite(hyb_auc) and np.isfinite(intent_auc):
        pct_auc = 100.0 * (hyb_auc - intent_auc) / intent_auc
        print(
            f"**Hybrid vs Intent-Only (ROC-AUC improvement):** {pct_auc:+.2f}% "
            f"(relative increase; diagnostic only)."
        )
    print()


if __name__ == "__main__":
    main()
