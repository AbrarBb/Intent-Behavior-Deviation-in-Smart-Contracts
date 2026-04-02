#!/usr/bin/env python3
"""
Merge intent embeddings + behavior features + ``final_label`` → artifacts/ml_dataset.npz

Also writes artifacts/ml_dataset_meta.csv for inspection (no huge vectors in CSV).

For Kaggle-style flat tables, run 09_export_kaggle_csvs.py after this step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR / "artifacts"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--use-seed", action="store_true")
    args = ap.parse_args()

    ann_path = SCRIPT_DIR / "manual_annotations.csv"
    if args.use_seed or not ann_path.is_file():
        ann_path = SCRIPT_DIR / "manual_annotations_seed.csv"
    if not ann_path.is_file():
        raise SystemExit("Need manual_annotations.csv or manual_annotations_seed.csv")

    beh_path = ARTIFACTS / "behavior_features.csv"
    if not beh_path.is_file():
        raise SystemExit("Run 06_extract_behavior_features.py first.")

    emb_path = ARTIFACTS / "intent_embeddings.npy"
    ids_path = ARTIFACTS / "intent_contract_ids.json"
    if not emb_path.is_file() or not ids_path.is_file():
        raise SystemExit("Run 05_embed_intent.py first.")

    ann = pd.read_csv(ann_path)
    beh = pd.read_csv(beh_path)
    merged = ann.merge(beh, on="contract_id", how="inner")

    ids_order = json.loads(ids_path.read_text(encoding="utf-8"))
    id_to_row = {cid: i for i, cid in enumerate(ids_order)}
    keep_idx = [id_to_row[c] for c in merged["contract_id"].astype(str) if c in id_to_row]
    keep_mask = merged["contract_id"].astype(str).isin(id_to_row)
    merged = merged.loc[keep_mask].copy()
    merged["_ord"] = merged["contract_id"].map(id_to_row)
    merged = merged.sort_values("_ord").drop(columns=["_ord"])

    emb = np.load(emb_path)
    idx = [id_to_row[c] for c in merged["contract_id"].astype(str)]
    emb_aligned = emb[idx].astype(np.float32)

    feat_cols = [
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
    for c in feat_cols:
        if c not in merged.columns:
            merged[c] = 0
    X_num = merged[feat_cols].fillna(0).to_numpy(dtype=np.float32)
    X = np.hstack([emb_aligned, X_num])

    y_raw = merged["final_label"].astype(str).str.lower().str.strip()
    if not y_raw.isin(["rugpull", "safe"]).all():
        bad = merged.loc[~y_raw.isin(["rugpull", "safe"]), "final_label"].unique()[:5]
        raise SystemExit(f"final_label must be rugpull|safe. Found: {list(bad)}")
    y = (y_raw == "rugpull").astype(np.int64)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        ARTIFACTS / "ml_dataset.npz",
        X=X,
        y=y,
        contract_id=merged["contract_id"].astype(str).to_numpy(),
        feature_cols=np.array(feat_cols, dtype=object),
    )
    meta = merged[["contract_id", "final_label"] + feat_cols].copy()
    meta.to_csv(ARTIFACTS / "ml_dataset_meta.csv", index=False)
    print(f"Saved {ARTIFACTS / 'ml_dataset.npz'}  shape X={X.shape}  positives={int(y.sum())}")


if __name__ == "__main__":
    main()
