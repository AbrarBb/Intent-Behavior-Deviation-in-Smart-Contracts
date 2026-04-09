#!/usr/bin/env python3
"""
Ablation experiments for the paper: hybrid vs intent-only vs behavior-only,
and hybrid without raw Slither detector columns (merged + regex kept).

Reads ``artifacts/ml_dataset.npz`` (run 07 first). Writes:
  artifacts/ablation_report.md
  artifacts/ablation_results.json

Also appends confusion-matrix / error-analysis snippets for qualitative case studies.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR / "artifacts"
DATA = ARTIFACTS / "ml_dataset.npz"
EMB_DIM = 384
RANDOM_STATE = 42


def slice_features(
    X: np.ndarray,
    feature_cols: np.ndarray,
    mode: str,
) -> tuple[np.ndarray, str]:
    """Return (X_sliced, description)."""
    tab = X[:, EMB_DIM:]
    fc = [str(c) for c in feature_cols]

    if mode == "hybrid":
        return X.copy(), "384-d intent + 14 behavior columns"

    if mode == "intent_only":
        return X[:, :EMB_DIM].copy(), "384-d intent only"

    if mode == "behavior_only":
        return tab.copy(), "14 behavior columns only"

    if mode == "behavior_no_slither_detectors":
        # Keep merged + regex (first 6 cols): owner_withdraw … regex_unrestricted_mint
        keep = 6
        return tab[:, :keep].copy(), "6 columns (merged + regex; no Slither detector block)"

    if mode == "hybrid_no_slither_detectors":
        tab_ns = tab[:, :6]
        return np.hstack([X[:, :EMB_DIM], tab_ns]).copy(), (
            "384-d intent + 6 (merged+regex), Slither detector block removed"
        )

    raise ValueError(f"Unknown mode: {mode}")


def train_and_eval(
    X: np.ndarray,
    y: np.ndarray,
    mode_name: str,
) -> dict:
    models = {
        "logistic_regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=2000, class_weight="balanced", random_state=RANDOM_STATE
                    ),
                ),
            ]
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        "linear_svc": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LinearSVC(
                        class_weight="balanced",
                        random_state=RANDOM_STATE,
                        dual="auto",
                        max_iter=5000,
                    ),
                ),
            ]
        ),
    }

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=RANDOM_STATE, stratify=y
    )

    out: dict = {"mode": mode_name, "n_samples": int(len(y)), "models": {}}

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    for mname, est in models.items():
        est.fit(X_train, y_train)
        pred = est.predict(X_test)
        f1 = float(f1_score(y_test, pred, zero_division=0))
        rep = classification_report(
            y_test, pred, digits=4, zero_division=0, output_dict=True
        )
        cm = confusion_matrix(y_test, pred).tolist()

        cv_scores: list[float] = []
        for tr, va in skf.split(X, y):
            clf = clone(est)
            clf.fit(X[tr], y[tr])
            pr = clf.predict(X[va])
            cv_scores.append(float(f1_score(y[va], pr, zero_division=0)))

        out["models"][mname] = {
            "holdout_f1_rugpull_positive": f1,
            "classification_report": rep,
            "confusion_matrix_test": cm,
            "cv_f1_mean": float(np.mean(cv_scores)),
            "cv_f1_std": float(np.std(cv_scores)),
        }

    # Best by hold-out F1 for RF (often strongest on tabular)
    best = max(
        out["models"].items(),
        key=lambda kv: kv[1]["holdout_f1_rugpull_positive"],
    )
    out["best_model_by_f1"] = {"name": best[0], "f1": best[1]["holdout_f1_rugpull_positive"]}

    return out


def main() -> None:
    if not DATA.is_file():
        raise SystemExit("Run 07_build_ml_dataset.py first to create ml_dataset.npz.")

    pack = np.load(DATA, allow_pickle=True)
    X_full = pack["X"]
    y = pack["y"]
    feature_cols = pack["feature_cols"]

    if len(np.unique(y)) < 2:
        raise SystemExit("Need both classes in y.")

    modes = [
        "hybrid",
        "intent_only",
        "behavior_only",
        "hybrid_no_slither_detectors",
    ]

    report_lines: list[str] = [
        "# Ablation experiment report",
        "",
        "Positive class: rugpull (y=1). Metrics from stratified hold-out (25%) and 5-fold CV.",
        "",
    ]

    all_results: dict = {}

    for mode in modes:
        X_sub, desc = slice_features(X_full, feature_cols, mode)
        report_lines.append(f"## Mode: `{mode}`")
        report_lines.append("")
        report_lines.append(f"**Description:** {desc}")
        report_lines.append(f"**Shape:** {X_sub.shape}")
        report_lines.append("")
        res = train_and_eval(X_sub, y, mode)
        all_results[mode] = res

        report_lines.append(f"**Best model (by hold-out F1):** `{res['best_model_by_f1']['name']}` "
            f"(F1={res['best_model_by_f1']['f1']:.4f})")
        report_lines.append("")
        for mname, mdata in res["models"].items():
            report_lines.append(f"### {mname}")
            report_lines.append("")
            report_lines.append(
                f"- Hold-out F1 (positive): {mdata['holdout_f1_rugpull_positive']:.4f}"
            )
            report_lines.append(
                f"- 5-fold CV F1: {mdata['cv_f1_mean']:.4f} ± {mdata['cv_f1_std']:.4f}"
            )
            report_lines.append(f"- Confusion matrix [tn fp; fn tp]: `{mdata['confusion_matrix_test']}`")
            report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    report_lines.append("## Error analysis (hybrid / best F1 model)")
    report_lines.append("")
    hybrid = all_results.get("hybrid", {})
    best_name = hybrid.get("best_model_by_f1", {}).get("name", "random_forest")
    if hybrid and best_name in hybrid["models"]:
        cm = hybrid["models"][best_name]["confusion_matrix_test"]
        report_lines.append(
            f"Use confusion matrix from **hybrid** + **{best_name}** for qualitative follow-up: "
            f"inspect false positives (benign predicted rugpull) and false negatives in `pilot_data/`."
        )
        report_lines.append(f"- Matrix: `{cm}`")
    report_lines.append("")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out_md = ARTIFACTS / "ablation_report.md"
    out_md.write_text("\n".join(report_lines), encoding="utf-8")
    out_json = ARTIFACTS / "ablation_results.json"
    out_json.write_text(json.dumps(all_results, indent=2), encoding="utf-8")

    print(f"Wrote {out_md}")
    print(f"Wrote {out_json}")


if __name__ == "__main__":
    main()
