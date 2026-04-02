#!/usr/bin/env python3
"""
Sentence-BERT embeddings for ``intent_text`` (all-MiniLM-L6-v2, 384-d).

Input:  manual_annotations.csv  (or manual_annotations_seed.csv if you pass --seed)
Output: artifacts/intent_embeddings.npy
        artifacts/intent_contract_ids.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR / "artifacts"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--annotations",
        type=Path,
        default=SCRIPT_DIR / "manual_annotations.csv",
        help="CSV with contract_id and intent_text",
    )
    ap.add_argument(
        "--use-seed",
        action="store_true",
        help="Use manual_annotations_seed.csv if you have not created manual_annotations.csv yet",
    )
    args = ap.parse_args()

    csv_path = args.annotations
    if args.use_seed or not csv_path.is_file():
        seed = SCRIPT_DIR / "manual_annotations_seed.csv"
        if seed.is_file():
            csv_path = seed
        elif not csv_path.is_file():
            raise SystemExit(f"Missing {args.annotations}; run 04 or pass --use-seed.")

    df = pd.read_csv(csv_path)
    if "contract_id" not in df.columns or "intent_text" not in df.columns:
        raise SystemExit("annotations CSV must include contract_id and intent_text")

    texts = df["contract_id"].astype(str).tolist()
    bodies = df["intent_text"].fillna("").astype(str).tolist()
    model = SentenceTransformer(MODEL_NAME)
    emb = model.encode(bodies, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=False)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    np.save(ARTIFACTS / "intent_embeddings.npy", emb.astype(np.float32))
    (ARTIFACTS / "intent_contract_ids.json").write_text(
        json.dumps(texts, indent=2),
        encoding="utf-8",
    )
    print(f"Saved embeddings shape {emb.shape} to {ARTIFACTS / 'intent_embeddings.npy'}")


if __name__ == "__main__":
    main()
