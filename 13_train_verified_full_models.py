#!/usr/bin/env python3
"""
Train baselines on the “verified-source full” dataset.
=========================================================

This uses the same model family and evaluation protocol as `08_train_models.py`,
but loads `artifacts/ml_dataset_verified_full.npz`.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR / "artifacts"
DATA = ARTIFACTS / "ml_dataset_verified_full.npz"


def main() -> None:
    if not DATA.is_file():
        raise SystemExit("Run 12_build_verified_full_ml_dataset.py first.")

    pack = np.load(DATA, allow_pickle=True)
    X = pack["X"]
    y = pack["y"]

    if len(np.unique(y)) < 2:
        raise SystemExit("Need both classes in y for training.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    models = {
        "logistic_regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "linear_svc": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LinearSVC(
                        class_weight="balanced",
                        random_state=42,
                        dual="auto",
                        max_iter=6000,
                    ),
                ),
            ]
        ),
    }

    print("=" * 60)
    print("Verified-source full hold-out evaluation (rugpull = positive class)")
    print("=" * 60)

    best_name = None
    best_f1 = -1.0
    best_est = None

    for name, est in models.items():
        est.fit(X_train, y_train)
        pred = est.predict(X_test)
        rep = classification_report(y_test, pred, digits=4, zero_division=0)
        f1 = f1_score(y_test, pred, zero_division=0)
        print(f"\n--- {name} ---")
        print(rep)
        print(f"F1 (positive=rugpull): {f1:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            best_name = name
            best_est = est

    # 5-fold stratified CV F1 on full data
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores: dict[str, list[float]] = {n: [] for n in models}
    for tr, va in skf.split(X, y):
        for name, est in models.items():
            est_clone = clone(est)
            est_clone.fit(X[tr], y[tr])
            pr = est_clone.predict(X[va])
            cv_scores[name].append(float(f1_score(y[va], pr, zero_division=0)))

    print("\n5-fold CV (mean ± std) F1:")
    for name, scores in cv_scores.items():
        print(f"  {name}: {np.mean(scores):.4f} ± {np.std(scores):.4f}")

    if best_est is not None:
        out_path = ARTIFACTS / "best_model_verified_full.joblib"
        joblib.dump({"model": best_est, "name": best_name}, out_path)
        print(f"\nSaved best model: {out_path}")

    print("=" * 60)


if __name__ == "__main__":
    main()

