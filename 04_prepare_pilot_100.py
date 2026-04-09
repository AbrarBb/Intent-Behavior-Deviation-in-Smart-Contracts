#!/usr/bin/env python3
"""
Pilot cohort (default N=100): balanced verified contracts + standardized layout.

Creates:
  pilot_data/contract_XXX/{code.sol,text.txt,functions.txt}
  pilot_manifest.csv           — ids, paths, weak label from master (for sampling only)
  manual_annotations_seed.csv  — starter rows; REPLACE final_label with human review for Q1 rigor

The seed CSV uses ``label`` from ``dataset_manifest.csv`` only to bootstrap automation.
For publication, treat ``manual_annotations.csv`` (your reviewed copy) as ground truth.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from solidity_extract import extract_nat_spec_and_comments, extract_function_names

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "dataset_manifest.csv"
VERIFIED_MANIFEST = SCRIPT_DIR / "verified_manifest.csv"
VERIFIED_BALANCED = SCRIPT_DIR / "verified_manifest_balanced_seed42.csv"
PILOT_ROOT = SCRIPT_DIR / "pilot_data"
PILOT_MANIFEST = SCRIPT_DIR / "pilot_manifest.csv"
SEED_ANNOTATIONS = SCRIPT_DIR / "manual_annotations_seed.csv"
N_PER_CLASS = 50  # 100 total; lower if insufficient verified sources
RNG = 42


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build pilot_data/ and annotation seed from a manifest CSV.",
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to manifest CSV (default: dataset_manifest.csv).",
    )
    ap.add_argument(
        "--from-verified-full",
        action="store_true",
        help=f"Use {VERIFIED_MANIFEST.name} (run 10 first).",
    )
    ap.add_argument(
        "--from-verified-balanced",
        action="store_true",
        help=f"Use {VERIFIED_BALANCED.name} (run 10 first).",
    )
    args = ap.parse_args()

    if args.from_verified_full and args.from_verified_balanced:
        raise SystemExit("Use at most one of --from-verified-full / --from-verified-balanced.")

    if args.from_verified_full:
        manifest_path = VERIFIED_MANIFEST
    elif args.from_verified_balanced:
        manifest_path = VERIFIED_BALANCED
    elif args.manifest is not None:
        manifest_path = Path(args.manifest).resolve()
    else:
        manifest_path = DEFAULT_MANIFEST

    if not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    df = pd.read_csv(manifest_path)
    ok = df[df["has_verified_source"] == 1].copy()
    if ok.empty:
        raise SystemExit("No rows with has_verified_source=1. Run Phase 2–3 first.")

    n_mal = min(N_PER_CLASS, int((ok["label"] == 1).sum()))
    n_safe = min(N_PER_CLASS, int((ok["label"] == 0).sum()))
    n_each = min(n_mal, n_safe)
    if n_each < 10:
        raise SystemExit(f"Too few verified contracts per class for pilot (need ≥10, got {n_each}).")

    mal = ok[ok["label"] == 1].sample(n=n_each, random_state=RNG)
    safe = ok[ok["label"] == 0].sample(n=n_each, random_state=RNG)
    sample = pd.concat([mal, safe], ignore_index=True).sample(frac=1.0, random_state=RNG)

    if PILOT_ROOT.exists():
        shutil.rmtree(PILOT_ROOT)
    PILOT_ROOT.mkdir(parents=True)

    rows: list[dict] = []
    ann: list[dict] = []

    for i, (_, row) in enumerate(sample.iterrows(), start=1):
        cid = f"contract_{i:03d}"
        addr = str(row["address"]).strip()
        rel_sol = str(row["sol_path"]).replace("\\", "/")
        src_path = SCRIPT_DIR / rel_sol
        if not src_path.is_file():
            continue

        out_dir = PILOT_ROOT / cid
        out_dir.mkdir(parents=True)
        shutil.copy2(src_path, out_dir / "code.sol")

        src = (out_dir / "code.sol").read_text(encoding="utf-8", errors="replace")
        (out_dir / "text.txt").write_text(extract_nat_spec_and_comments(src), encoding="utf-8")
        funcs = extract_function_names(src)
        (out_dir / "functions.txt").write_text("\n".join(funcs), encoding="utf-8")

        intent_text = (out_dir / "text.txt").read_text(encoding="utf-8").strip()
        if not intent_text:
            intent_text = (
                f"(no NatSpec/comments extracted; see functions: "
                f"{', '.join(funcs[:12])}{'...' if len(funcs) > 12 else ''})"
            )

        weak = int(row["label"])
        final = "rugpull" if weak == 1 else "safe"

        rows.append(
            {
                "contract_id": cid,
                "address": addr,
                "label_master_binary": weak,
                "pilot_dir": str(out_dir.relative_to(SCRIPT_DIR)),
                "code_sol": str((out_dir / "code.sol").relative_to(SCRIPT_DIR)),
            }
        )
        ann.append(
            {
                "contract_id": cid,
                "intent_text": intent_text[:8000],
                "intent_label": "",
                "behavior_label": "",
                "final_label": final,
                "reviewer_notes": "SEED: copied from master label — verify manually for paper.",
            }
        )

    pd.DataFrame(rows).to_csv(PILOT_MANIFEST, index=False)
    pd.DataFrame(ann).to_csv(SEED_ANNOTATIONS, index=False)

    print("=" * 60)
    print("Pilot layout prepared")
    print("=" * 60)
    print(f"  Contracts: {len(rows)}  (target up to {2 * N_PER_CLASS})")
    print(f"  Root: {PILOT_ROOT}")
    print(f"  Source manifest: {manifest_path.name}")
    print(f"  Manifest: {PILOT_MANIFEST}")
    print(f"  Annotations seed: {SEED_ANNOTATIONS}")
    print("  Next: copy seed to manual_annotations.csv, edit labels, then run 05-08.")
    print("=" * 60)


if __name__ == "__main__":
    main()
