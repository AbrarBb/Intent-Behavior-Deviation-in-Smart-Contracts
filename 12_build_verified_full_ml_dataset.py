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
     With ``--enable-slither``, Slither runs per file using ``--solc-solcs-select``:
     exact pragma chains (e.g. 0.8.13 → 0.8.13, 0.8.20, 0.8.28) then line fallbacks
     (0.4.26 … 0.8.28). Extra 0.8.x compilers are installed via solc-select when needed.
     On first run, ``solc-select install`` is invoked for those versions unless
     ``--slither-skip-solc-install`` is passed. The pip ``Scripts`` directory is
     prepended to PATH so ``solc`` resolves.
     Optional ``--enable-enriched-features`` appends regex heuristics from
     ``06b_extract_enriched_behavior_features.py`` to the behavior vector.
  5) Creating `X = [intent_embedding | behavior_features]` and `y = label`.
  6) Saving (default stem ``ml_dataset_verified_full.*``; use ``--output-tag`` for
     smoke tests so you do not overwrite a finished Stage-2 corpus):
       - `artifacts/ml_dataset_verified_full.npz` (primary, for training)
       - `artifacts/ml_dataset_verified_full.csv` (inspection / Kaggle-style)

Outputs are ignored by git because `artifacts/` is excluded in `.gitignore`.
"""

from __future__ import annotations

import argparse
import importlib.util
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

# Base tabular behavior block (regex + Slither schema); must match `07_build_ml_dataset.py`.
BASE_FEATURE_COLS = [
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


def _sanitize_output_tag(raw: str | None) -> str | None:
    """Allow only safe filename tokens; return None to use default stem."""
    if raw is None or not str(raw).strip():
        return None
    t = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(raw).strip()).strip("_")
    if not t:
        return None
    return t[:64]


def _load_enriched_behavior_module():
    """Load ``06b_extract_enriched_behavior_features.py`` (filename not importable as a package)."""
    path = SCRIPT_DIR / "06b_extract_enriched_behavior_features.py"
    if not path.is_file():
        raise SystemExit(f"Missing {path.name} (required for --enable-enriched-features).")
    spec = importlib.util.spec_from_file_location("enriched_behavior_features", path)
    if spec is None or spec.loader is None:
        raise SystemExit("Could not load enriched behavior module.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    8: "0.8.28",  # default fallback for unknown 0.8.x
}

# Exact ``X.Y.Z`` pragmas: try these first (left = highest priority), then line-based fallbacks.
PRAGMA_SOLC_CHAINS: dict[str, list[str]] = {
    "0.8.13": ["0.8.13", "0.8.20", "0.8.28"],
    "0.8.20": ["0.8.20", "0.8.28"],
    "0.8.0": ["0.8.28", "0.8.20", "0.8.13"],  # e.g. ^0.8.0
}


def _merged_solc_versions_for_install() -> tuple[str, ...]:
    s: set[str] = set(SOLC_LINE_TO_VERSION.values())
    for chain in PRAGMA_SOLC_CHAINS.values():
        s.update(chain)
    return tuple(sorted(s, key=lambda v: tuple(int(x) for x in v.split("."))))


SOLC_VERSIONS_FOR_INSTALL: tuple[str, ...] = _merged_solc_versions_for_install()

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


def _line_ordered_solc_versions(prag_spec: str | None) -> list[str]:
    """Line-based order (one compiler per 0.4–0.8 line), pragma minor first."""
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
    return out


def infer_solc_chain(prag_spec: str | None) -> list[str]:
    """Ordered solc versions: pragma-specific chain first, then line-based fallbacks (deduped)."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(v: str) -> None:
        if v not in seen:
            seen.add(v)
            ordered.append(v)

    if prag_spec:
        for m in re.finditer(r"\b(0\.\d+\.\d+)\b", prag_spec):
            key = m.group(1)
            if key in PRAGMA_SOLC_CHAINS:
                for v in PRAGMA_SOLC_CHAINS[key]:
                    add(v)
                break

    for v in _line_ordered_solc_versions(prag_spec):
        add(v)

    return ordered


def build_solc_solcs_select_arg(prag_spec: str | None) -> str:
    """Comma-separated list for Slither ``--solc-solcs-select``."""
    return ",".join(infer_solc_chain(prag_spec))


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
                if r.stdout and r.stdout.strip():
                    print(r.stdout.strip(), flush=True)
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

    # Slither often exits non-zero when detectors report findings; JSON is still valid.
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
    ap.add_argument(
        "--max-contracts",
        type=int,
        default=0,
        help="If >0, only the first N rows of the manifest are processed (smoke test / Stage 1).",
    )
    ap.add_argument(
        "--enable-enriched-features",
        action="store_true",
        help="Append heuristic columns from 06b_extract_enriched_behavior_features.py to behavior block.",
    )
    ap.add_argument(
        "--output-tag",
        type=str,
        default="",
        help="Write artifacts/ml_dataset_verified_full_<tag>.* instead of default stem (avoids overwriting full builds).",
    )
    args = ap.parse_args()

    _ot = (args.output_tag or "").strip()
    _tag = _sanitize_output_tag(_ot) if _ot else None
    output_stem = "ml_dataset_verified_full" + (f"_{_tag}" if _tag else "")
    if _tag:
        print(
            f"Output stem: {output_stem} (use default stem for canonical Stage 2 / paper artifacts)",
            flush=True,
        )

    enriched_mod = _load_enriched_behavior_module() if args.enable_enriched_features else None
    feature_cols: list[str] = list(BASE_FEATURE_COLS)
    if args.enable_enriched_features:
        feature_cols = list(BASE_FEATURE_COLS) + list(enriched_mod.ENRICHED_FEATURE_NAMES)

    if not MANIFEST_CSV.is_file():
        raise SystemExit(f"Missing {MANIFEST_CSV.name}. Run 10_verified_source_cohorts.py first.")

    df = pd.read_csv(MANIFEST_CSV)
    if df.empty:
        raise SystemExit("verified_manifest.csv is empty.")

    # Defensive columns check.
    for col in ["address", "label", "sol_path"]:
        if col not in df.columns:
            raise SystemExit(f"verified_manifest.csv must include column: {col}")

    if args.max_contracts and args.max_contracts > 0:
        df = df.head(int(args.max_contracts)).copy()
        print(f"Limiting to first {len(df)} manifest row(s) (--max-contracts).", flush=True)

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
    if args.enable_enriched_features:
        print(
            f"Enriched behavior features: enabled (+{len(enriched_mod.ENRICHED_FEATURE_NAMES)} columns)",
            flush=True,
        )

    # 1) Extract intent_text and behavior features.
    intent_texts: list[str] = []
    beh_rows: list[list[float]] = []
    kept_labels: list[int] = []
    kept_addresses: list[str] = []
    kept_sol_paths: list[str] = []
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

        row = [
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
        if args.enable_enriched_features:
            assert enriched_mod is not None
            row.extend(enriched_mod.extract_enriched_vector(src))
        beh_rows.append(row)
        intent_texts.append(intent)
        kept_labels.append(int(labels[i - 1]))
        kept_addresses.append(addr)
        kept_sol_paths.append(sol_rel)

        if i % 100 == 0:
            print(f"  extracted {i}/{n}")

    # If any were skipped (should be rare), align arrays.
    if len(intent_texts) != len(beh_rows):
        raise SystemExit("Internal mismatch: extracted intent_texts and behavior rows differ.")

    X_beh = np.asarray(beh_rows, dtype=np.float32)
    y = np.asarray(kept_labels, dtype=np.int64)
    cids = kept_addresses
    sol_paths_kept = kept_sol_paths

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
    npz_path = ARTIFACTS_DIR / f"{output_stem}.npz"
    np.savez_compressed(
        npz_path,
        X=X,
        y=y,
        contract_id=np.asarray(cids, dtype=object),
        feature_cols=np.asarray(feature_cols, dtype=object),
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
    for idx, c in enumerate(feature_cols):
        meta[c] = X_beh[:, idx].astype(int)
    meta_path = ARTIFACTS_DIR / f"{output_stem}_meta.csv"
    meta.to_csv(meta_path, index=False)

    print(f"Saved NPZ: {npz_path}")
    print(f"Saved meta CSV: {meta_path}")
    if args.enable_slither:
        print(f"Slither summary: ok={slither_ok_n}, failed={slither_fail_n}")

    if not args.no_csv:
        # Kaggle-style flat dataset: embedding columns + behavior + target.
        emb_cols = [f"emb_{i:03d}" for i in range(EMB_DIM)]
        emb_df = pd.DataFrame(emb, columns=emb_cols)
        beh_df = pd.DataFrame(X_beh, columns=feature_cols)
        out = pd.concat(
            [
                meta[["address", "target", "target_label", "sol_path"]].reset_index(drop=True),
                emb_df,
                beh_df.reset_index(drop=True),
            ],
            axis=1,
        )
        csv_path = ARTIFACTS_DIR / f"{output_stem}.csv"
        out.to_csv(csv_path, index=False, float_format="%.6f")
        print(f"Saved full CSV: {csv_path} (columns={len(out.columns)})")

    # Save config for reproducibility.
    cfg_path = ARTIFACTS_DIR / f"{output_stem}_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "manifest": MANIFEST_CSV.name,
                "output_stem": output_stem,
                "n_contracts": n,
                "kept_contracts": len(cids),
                "total_contracts": len(cids),
                "embedding_model": MODEL_NAME,
                "emb_dim": EMB_DIM,
                "max_intent_chars": args.max_intent_chars,
                "batch_size": args.batch_size,
                "device": args.device,
                "feature_cols": feature_cols,
                "base_feature_cols": list(BASE_FEATURE_COLS),
                "enriched_features_enabled": bool(args.enable_enriched_features),
                "slither_enabled": bool(args.enable_slither),
                "slither_timeout_sec": int(args.slither_timeout),
                "slither_skip_solc_install": bool(args.slither_skip_solc_install),
                "solc_select_versions": list(SOLC_VERSIONS_FOR_INSTALL),
                "pragma_solc_chains": {k: v for k, v in PRAGMA_SOLC_CHAINS.items()},
                "slither_ok_count": int(slither_ok_n),
                "slither_fail_count": int(slither_fail_n),
                "max_contracts_cap": int(args.max_contracts),
                "output_tag": _tag or "",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

