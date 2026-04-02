#!/usr/bin/env python3
"""
Export flat CSVs for Kaggle / supplementary material (matches paper workflow).

Writes:
  artifacts/intent_vectors.csv   — contract_id + emb_000..emb_383 (wide numeric)
  artifacts/ml_dataset.csv       — embeddings + behavior columns + target (0/1) + target_label

Optional:
  --intent-json-column           — also write intent_vector as a single JSON array string
                                   (human-readable in STEP 4 style; wide columns still primary)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR / "artifacts"
NPZ_PATH = ARTIFACTS / "ml_dataset.npz"
EMB_DIM = 384


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--intent-json-column",
        action="store_true",
        help="Add intent_vector JSON string column to intent_vectors.csv",
    )
    args = ap.parse_args()

    if not NPZ_PATH.is_file():
        raise SystemExit("Run 07_build_ml_dataset.py first (missing ml_dataset.npz).")

    pack = np.load(NPZ_PATH, allow_pickle=True)
    X = pack["X"]
    y = pack["y"]
    cids = pack["contract_id"].astype(str)
    feat_cols = list(pack["feature_cols"])

    n_emb = X.shape[1] - len(feat_cols)
    if n_emb != EMB_DIM:
        raise SystemExit(f"Expected {EMB_DIM} embedding dims, got {n_emb}")

    emb = X[:, :n_emb].astype(np.float64)
    beh = X[:, n_emb:]

    emb_df = pd.DataFrame(emb, columns=[f"emb_{i:03d}" for i in range(n_emb)])
    out_iv = pd.DataFrame({"contract_id": cids}).join(emb_df)

    if args.intent_json_column:
        out_iv["intent_vector"] = [json.dumps(row.tolist()) for row in emb]

    out_iv.to_csv(ARTIFACTS / "intent_vectors.csv", index=False)

    beh_df = pd.DataFrame(beh, columns=feat_cols)
    ml = pd.DataFrame({"contract_id": cids}).join(emb_df).join(beh_df)
    ml["target"] = y.astype(int)
    ml["target_label"] = np.where(y == 1, "rugpull", "safe")

    ml.to_csv(ARTIFACTS / "ml_dataset.csv", index=False)

    print("Wrote:")
    print(f"  {ARTIFACTS / 'intent_vectors.csv'}  shape={out_iv.shape}")
    print(f"  {ARTIFACTS / 'ml_dataset.csv'}      shape={ml.shape}")


if __name__ == "__main__":
    main()
