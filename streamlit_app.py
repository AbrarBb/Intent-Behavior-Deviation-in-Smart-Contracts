#!/usr/bin/env python3
"""
Prototype: paste Solidity + intent text → hybrid features → trained sklearn model.

Slither is optional offline; this demo uses the same regex behavior flags as training.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer

from solidity_extract import extract_function_names, regex_behavior_flags

SCRIPT_DIR = Path(__file__).resolve().parent
ARTIFACTS = SCRIPT_DIR / "artifacts"
MODEL_PATH = ARTIFACTS / "best_model.joblib"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@st.cache_resource
def load_embedder():
    return SentenceTransformer(MODEL_NAME)


@st.cache_resource
def load_clf():
    if not MODEL_PATH.is_file():
        return None
    bundle = joblib.load(MODEL_PATH)
    return bundle["model"], bundle.get("name", "model")


def build_vector(intent_text: str, code: str) -> np.ndarray:
    emb = load_embedder().encode([intent_text], convert_to_numpy=True).astype(np.float32)
    funcs = extract_function_names(code)
    rx = regex_behavior_flags(code, funcs)
    # No Slither in-app: match 06 when slither_ok=0 (merged flags == regex-only path).
    ow = float(rx["regex_owner_withdraw"])
    ew = float(rx["regex_emergency_withdraw"])
    um = float(rx["regex_unrestricted_mint"])
    num = np.array(
        [
            ow,
            ew,
            um,
            float(rx["regex_owner_withdraw"]),
            float(rx["regex_emergency_withdraw"]),
            float(rx["regex_unrestricted_mint"]),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ],
        dtype=np.float32,
    )
    return np.hstack([emb[0], num]).reshape(1, -1)


def main() -> None:
    st.set_page_config(page_title="Intent–Behavior Prototype", layout="wide")
    st.title("Intent vs. behavior (prototype)")
    st.caption(
        "Hybrid BERT + heuristic behavior features. Train with 05–08 first; "
        "Slither-derived flags are zeroed here unless you extend the app."
    )

    intent = st.text_area("Intent text (comments / claims)", height=160)
    code = st.text_area("Solidity source", height=320)

    loaded = load_clf()
    if loaded is None:
        st.error(f"Missing {MODEL_PATH.name}. Run 08_train_models.py.")
        return
    clf, mname = loaded

    if st.button("Predict"):
        if not code.strip():
            st.warning("Paste Solidity code.")
            return
        it = intent.strip() or "(no intent text provided)"
        x = build_vector(it, code)
        proba = None
        if hasattr(clf, "predict_proba"):
            proba = clf.predict_proba(x)[0]
        pred = int(clf.predict(x)[0])
        label = "rugpull (predicted)" if pred == 1 else "safe (predicted)"
        st.subheader(label)
        st.write(f"Model: `{mname}`")
        if proba is not None:
            st.write(f"Estimated P(rugpull) = {proba[1]:.3f}" if len(proba) > 1 else proba)
        fx = extract_function_names(code)
        st.write("Heuristic flags from code:", regex_behavior_flags(code, fx))


if __name__ == "__main__":
    main()
