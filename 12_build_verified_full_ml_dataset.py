#!/usr/bin/env python3
"""
Build the largest feasible “single ML dataset” for this project.
=====================================================================

Motivation (paper + ML training):
- Your pilot labels (`manual_annotations.csv`) are limited to ~100 contracts.
- For stronger quantitative scores, we can leverage the verified-source pool
  (Etherscan “has verified source code”), which is the largest analyzable set
  available in this repo: `verified_manifest.csv` (3324 rows).

This script creates ONE training dataset by:
  1) Loading `verified_manifest.csv` (address, label, sol_path).
  2) Extracting intent text from each Solidity source file (NatSpec/comments).
  3) Computing Sentence-BERT embeddings for intent text.
  4) Extracting behavior features via regex heuristics (fast, always works).
     Slither detector columns are included but set to 0 by default because
     full Slither runs over thousands of contracts are expensive.
     (If you later enable Slither, keep the same column schema.)
  5) Creating `X = [intent_embedding | behavior_features]` and `y = label`.
  6) Saving:
       - `artifacts/ml_dataset_verified_full.npz` (primary, for training)
       - `artifacts/ml_dataset_verified_full.csv` (inspection / Kaggle-style)

Outputs are ignored by git because `artifacts/` is excluded in `.gitignore`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from solidity_extract import extract_function_names, extract_nat_spec_and_comments, regex_behavior_flags

SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_CSV = SCRIPT_DIR / "verified_manifest.csv"
ARTIFACTS_DIR = SCRIPT_DIR / "artifacts"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMB_DIM = 384

# Must match the training feature ordering in `07_build_ml_dataset.py`.
FEATURE_COLS = [
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


SLITHER_OWNERISH = frozenset(
    {
        "arbitrary-send-eth",
        "arbitrary-send-erc20",
        "unchecked-lowlevel",
        "unchecked-send",
        "suicidal",
        "controlled-delegatecall",
        "delegatecall-loop",
    }
)

# One representative patch per 0.4–0.8 line for solc-select / Slither --solc-solcs-select.
SOLC_LINE_TO_VERSION = {
    4: "0.4.26",
    5: "0.5.17",
    6: "0.6.12",
    7: "0.7.6",
    8: "0.8.28",
}
SOLC_VERSIONS_FOR_INSTALL: tuple[str, ...] = tuple(SOLC_LINE_TO_VERSION.values())

PRAGMA_SOLIDITY_RE = re.compile(
    r"pragma\s+solidity\s+([^;]+);",
    re.IGNORECASE | re.MULTILINE,
)


def _scripts_dir() -> Path | None:
    """User-site Scripts (Windows) or bin (Unix) next to ``sys.executable``."""
    parent = Path(sys.executable).resolve().parent
    for name in ("Scripts", "bin"):
        d = parent / name
        if d.is_dir():
            return d
    return None


def prepend_compiler_tools_to_path() -> None:
    """Ensure ``solc`` / ``slither`` wrappers from pip are discoverable."""
    sd = _scripts_dir()
    if sd is None:
        return
    os.environ["PATH"] = str(sd) + os.pathsep + os.environ.get("PATH", "")


def extract_pragma_solidity_spec(src: str) -> str | None:
    m = PRAGMA_SOLIDITY_RE.search(src[:12000])
    return m.group(1).strip() if m else None


def infer_solc_minor_line(spec: str | None) -> int:
    """Map a pragma solidity specifier to a 0.4–0.8 ``minor`` line for ordering solcs."""
    if not spec:
        return 8
    s = spec.strip()
    m = re.search(r"\^0\.(\d+)\.", s)
    if m:
        v = int(m.group(1))
        return max(4, min(8, v))
    for m in re.finditer(r"0\.(\d+)\.", s):
        v = int(m.group(1))
        if 4 <= v <= 8:
            return v
    m = re.search(r"\b0\.(\d+)\b", s)
    if m:
        v = int(m.group(1))
        if 4 <= v <= 8:
            return v
    return 8


def build_solc_solcs_select_arg(prag_spec: str | None) -> str:
    """Comma-separated list for Slither ``--solc-solcs-select`` (try pragma line first)."""
    line = infer_solc_minor_line(prag_spec)
    upward = list(range(line, 9))
    downward = list(range(line - 1, 3, -1))
    order = upward + downward
    seen: set[str] = set()
    out: list[str] = []
    for ln in order:
        ver = SOLC_LINE_TO_VERSION.get(ln)
        if ver and ver not in seen:
            seen.add(ver)
            out.append(ver)
    return ",".join(out)


def _solc_select_cmd() -> list[str] | None:
    """Command prefix to run ``solc-select`` (pip Scripts entrypoint, not ``python -m``)."""
    sd = _scripts_dir()
    if sd:
        for name in ("solc-select.exe", "solc-select"):
            p = sd / name
            if p.is_file():
                return [str(p)]
    w = shutil.which("solc-select")
    if w:
        return [w]
    return None


def ensure_solc_versions_installed(versions: tuple[str, ...], timeout_s: int = 600) -> None:
    """Best-effort install of solc binaries via solc-select (idempotent)."""
    base = _solc_select_cmd()
    if not base:
        print("WARN: solc-select not found; Slither may fail until compilers are installed.", flush=True)
        return
    for ver in versions:
        try:
            r = subprocess.run(
                [*base, "install", ver],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            if r.returncode == 0:
                print(r.stdout.strip(), flush=True) if r.stdout else None
            else:
                tail = (r.stderr or r.stdout or "")[-500:]
                print(f"[solc-select install {ver}] failed: {tail!s}", flush=True)
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            print(f"[solc-select install {ver}] skipped/failed: {exc}", flush=True)


def run_slither_json(
    sol_file: Path,
    timeout_s: int,
    *,
    solc_solcs_select: str,
) -> tuple[dict | None, str | None]:
    jpath = sol_file.parent / "_slither_out.json"
    if jpath.is_file():
        try:
            jpath.unlink()
        except OSError:
            pass

    if shutil.which("slither"):
        cmd = [
            "slither",
            str(sol_file),
            "--solc-solcs-select",
            solc_solcs_select,
            "--json",
            str(jpath),
        ]
    else:
        cmd = [
            sys.executable,
            "-m",
            "slither",
            str(sol_file),
            "--solc-solcs-select",
            solc_solcs_select,
            "--json",
            str(jpath),
        ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(sol_file.parent),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return None, "slither_timeout"
    except FileNotFoundError:
        return None, "slither_not_found"
    except OSError as exc:
        return None, f"os_error:{exc}"

    if not jpath.is_file():
        tail = (proc.stderr or proc.stdout or "")[-500:]
        return None, f"no_json:{tail}"

    try:
        data = json.loads(jpath.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return None, f"json_decode:{exc}"

    return data, None


def parse_slither_flags(data: dict) -> dict[str, int]:
    detectors = []
    res = data.get("results")
    if isinstance(res, dict):
        detectors = res.get("detectors") or []
    checks = {str(d.get("check", "")) for d in detectors if isinstance(d, dict)}
    high = sum(
        1
        for d in detectors
        if isinstance(d, dict) and str(d.get("impact", "")).lower() == "high"
    )

    return {
        "slither_high_count": min(high, 255),
        "slither_arbitrary_send": int(
            "arbitrary-send-eth" in checks or "arbitrary-send-erc20" in checks
        ),
        "slither_suicidal": int("suicidal" in checks),
        "slither_unchecked_lowlevel": int("unchecked-lowlevel" in checks),
        "slither_controlled_delegatecall": int("controlled-delegatecall" in checks),
        "slither_delegatecall_loop": int("delegatecall-loop" in checks),
        "slither_ownerish_any": int(bool(checks & SLITHER_OWNERISH)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-intent-chars", type=int, default=8000)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Pass through to SentenceTransformer; use 'cuda' if available.",
    )
    ap.add_argument(
        "--no-csv",
        action="store_true",
        help="Only write NPZ + meta (skips large CSV export).",
    )
    ap.add_argument(
        "--enable-slither",
        action="store_true",
        help="Run Slither per contract to populate slither_* columns (slow).",
    )
    ap.add_argument(
        "--slither-timeout",
        type=int,
        default=180,
        help="Per-contract Slither timeout in seconds when --enable-slither is set.",
    )
    ap.add_argument(
        "--slither-skip-solc-install",
        action="store_true",
        help="Do not run solc-select install (assumes solc versions are already installed).",
    )
    args = ap.parse_args()

    if not MANIFEST_CSV.is_file():
        raise SystemExit(f"Missing {MANIFEST_CSV.name}. Run 10_verified_source_cohorts.py first.")

    df = pd.read_csv(MANIFEST_CSV)
    if df.empty:
        raise SystemExit("verified_manifest.csv is empty.")

    # Defensive columns check.
    for col in ["address", "label", "sol_path"]:
        if col not in df.columns:
            raise SystemExit(f"verified_manifest.csv must include column: {col}")

    addresses = df["address"].astype(str).str.strip().tolist()
    labels = df["label"].astype(int).to_numpy()
    sol_paths = df["sol_path"].astype(str).tolist()

    n = len(addresses)
    print(f"Verified-source full dataset: N={n}")
    if args.enable_slither:
        prepend_compiler_tools_to_path()
        print(f"Slither mode: enabled (timeout={args.slither_timeout}s per contract)", flush=True)
        if not args.slither_skip_solc_install:
            print(
                "Installing solc versions via solc-select (one-time; may download): "
                + ", ".join(SOLC_VERSIONS_FOR_INSTALL),
                flush=True,
            )
            ensure_solc_versions_installed(SOLC_VERSIONS_FOR_INSTALL)
        else:
            print("Skipping solc-select install (--slither-skip-solc-install).", flush=True)
    else:
        print("Slither mode: disabled (slither_* columns will be 0)", flush=True)

    # 1) Extract intent_text and behavior features.
    intent_texts: list[str] = []
    beh_rows: list[list[float]] = []
    slither_ok_n = 0
    slither_fail_n = 0

    for i, (addr, sol_rel) in enumerate(zip(addresses, sol_paths), start=1):
        code_path = (SCRIPT_DIR / Path(sol_rel)).resolve()
        if not code_path.is_file():
            # This should not happen if verified_manifest was built correctly.
            print(f"[{i}/{n}] WARN {addr}: missing code file -> skipping")
            continue

        src = code_path.read_text(encoding="utf-8", errors="replace")
        intent = extract_nat_spec_and_comments(src)
        intent = (intent or "").strip()
        if not intent:
            # Keep a stable, non-empty input for embedding.
            funcs = extract_function_names(src)
            intent = f"(no NatSpec/comments extracted) functions: {', '.join(funcs[:20])}"

        intent = intent[: args.max_intent_chars]
        funcs = extract_function_names(src)
        rx = regex_behavior_flags(src, funcs)

        sf = {
            "slither_high_count": 0,
            "slither_arbitrary_send": 0,
            "slither_suicidal": 0,
            "slither_unchecked_lowlevel": 0,
            "slither_controlled_delegatecall": 0,
            "slither_delegatecall_loop": 0,
            "slither_ownerish_any": 0,
        }
        slither_ok = 0
        if args.enable_slither:
            prag = extract_pragma_solidity_spec(src)
            solcs_arg = build_solc_solcs_select_arg(prag)
            data, err = run_slither_json(
                code_path,
                timeout_s=args.slither_timeout,
                solc_solcs_select=solcs_arg,
            )
            if data is not None:
                sf = parse_slither_flags(data)
                slither_ok = 1
                slither_ok_n += 1
            else:
                slither_fail_n += 1
                if slither_fail_n <= 5:
                    print(f"[{i}/{n}] WARN {addr}: Slither failed ({err or 'unknown'})")

        # Merged flags: with Slither, owner_withdraw includes slither ownerish/arbitrary-send.
        owner_withdraw = int(
            rx["regex_owner_withdraw"] or sf["slither_arbitrary_send"] or sf["slither_ownerish_any"]
        )
        emergency_withdraw = int(rx["regex_emergency_withdraw"])
        unrestricted_mint = int(rx["regex_unrestricted_mint"])

        beh_rows.append(
            [
                owner_withdraw,
                emergency_withdraw,
                unrestricted_mint,
                int(rx["regex_owner_withdraw"]),
                int(rx["regex_emergency_withdraw"]),
                int(rx["regex_unrestricted_mint"]),
                slither_ok,
                sf["slither_high_count"],
                sf["slither_arbitrary_send"],
                sf["slither_suicidal"],
                sf["slither_unchecked_lowlevel"],
                sf["slither_controlled_delegatecall"],
                sf["slither_delegatecall_loop"],
                sf["slither_ownerish_any"],
            ]
        )
        intent_texts.append(intent)

        if i % 100 == 0:
            print(f"  extracted {i}/{n}")

    # If any were skipped (should be rare), align arrays.
    if len(intent_texts) != len(beh_rows):
        raise SystemExit("Internal mismatch: extracted intent_texts and behavior rows differ.")

    X_beh = np.asarray(beh_rows, dtype=np.float32)
    y = labels[: len(intent_texts)].astype(np.int64)
    cids = addresses[: len(intent_texts)]
    sol_paths_kept = sol_paths[: len(intent_texts)]

    # 2) Embeddings.
    print("Computing Sentence-BERT embeddings...")
    model = SentenceTransformer(MODEL_NAME, device=args.device)
    emb = model.encode(
        intent_texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )

    if emb.shape[1] != EMB_DIM:
        raise SystemExit(f"Unexpected embedding dim: {emb.shape[1]} (expected {EMB_DIM})")

    emb = emb.astype(np.float32)
    X = np.hstack([emb, X_beh]).astype(np.float32)

    # 3) Save artifacts.
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    npz_path = ARTIFACTS_DIR / "ml_dataset_verified_full.npz"
    np.savez_compressed(
        npz_path,
        X=X,
        y=y,
        contract_id=np.asarray(cids, dtype=object),
        feature_cols=np.asarray(FEATURE_COLS, dtype=object),
        emb_dim=np.asarray([EMB_DIM], dtype=np.int64),
    )

    # Meta file: compact schema without embeddings to keep it readable.
    meta = pd.DataFrame(
        {
            "address": cids,
            "target": y,
            "target_label": np.where(y == 1, "rugpull", "safe"),
            "sol_path": sol_paths_kept,
        }
    )
    for idx, c in enumerate(FEATURE_COLS):
        meta[c] = X_beh[:, idx].astype(int)
    meta_path = ARTIFACTS_DIR / "ml_dataset_verified_full_meta.csv"
    meta.to_csv(meta_path, index=False)

    print(f"Saved NPZ: {npz_path}")
    print(f"Saved meta CSV: {meta_path}")
    if args.enable_slither:
        print(f"Slither summary: ok={slither_ok_n}, failed={slither_fail_n}")

    if not args.no_csv:
        # Kaggle-style flat dataset: embedding columns + behavior + target.
        emb_cols = [f"emb_{i:03d}" for i in range(EMB_DIM)]
        emb_df = pd.DataFrame(emb, columns=emb_cols)
        beh_df = pd.DataFrame(X_beh, columns=FEATURE_COLS)
        out = pd.concat(
            [
                meta[["address", "target", "target_label", "sol_path"]].reset_index(drop=True),
                emb_df,
                beh_df.reset_index(drop=True),
            ],
            axis=1,
        )
        csv_path = ARTIFACTS_DIR / "ml_dataset_verified_full.csv"
        out.to_csv(csv_path, index=False, float_format="%.6f")
        print(f"Saved full CSV: {csv_path} (columns={len(out.columns)})")

    # Save config for reproducibility.
    cfg_path = ARTIFACTS_DIR / "ml_dataset_verified_full_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "manifest": MANIFEST_CSV.name,
                "n_contracts": n,
                "kept_contracts": len(cids),
                "embedding_model": MODEL_NAME,
                "emb_dim": EMB_DIM,
                "max_intent_chars": args.max_intent_chars,
                "batch_size": args.batch_size,
                "device": args.device,
                "feature_cols": FEATURE_COLS,
                "slither_enabled": bool(args.enable_slither),
                "slither_timeout_sec": int(args.slither_timeout),
                "slither_ok_count": int(slither_ok_n),
                "slither_fail_count": int(slither_fail_n),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

