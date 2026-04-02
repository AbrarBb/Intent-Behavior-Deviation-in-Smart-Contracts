#!/usr/bin/env python3
"""
Behavior layer: Slither JSON (when available) + regex heuristics from code.sol.

Requires ``slither-analyzer`` on PATH and a working solc setup for analyzed pragmas.
If Slither fails, regex columns still populate and ``slither_ok=0``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from solidity_extract import regex_behavior_flags, extract_function_names

SCRIPT_DIR = Path(__file__).resolve().parent
PILOT_ROOT = SCRIPT_DIR / "pilot_data"
OUT_CSV = SCRIPT_DIR / "artifacts" / "behavior_features.csv"

# Slither checks often indicative of privileged fund movement / dangerous control flow
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


def run_slither_json(sol_file: Path) -> tuple[dict | None, str | None]:
    jpath = sol_file.parent / "_slither_out.json"
    if shutil.which("slither"):
        cmd = ["slither", str(sol_file), "--json", str(jpath)]
    else:
        cmd = [sys.executable, "-m", "slither", str(sol_file), "--json", str(jpath)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(sol_file.parent),
            capture_output=True,
            text=True,
            timeout=180,
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
    if not PILOT_ROOT.is_dir():
        raise SystemExit("pilot_data/ missing — run 04_prepare_pilot_100.py first.")

    dirs = sorted(p for p in PILOT_ROOT.iterdir() if p.is_dir() and p.name.startswith("contract_"))
    rows: list[dict] = []

    for d in dirs:
        cid = d.name
        code = d / "code.sol"
        funcs_path = d / "functions.txt"
        if not code.is_file():
            continue

        src = code.read_text(encoding="utf-8", errors="replace")
        funcs = (
            funcs_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if funcs_path.is_file()
            else extract_function_names(src)
        )
        rx = regex_behavior_flags(src, funcs)

        data, err = run_slither_json(code)
        if data is None:
            sf = parse_slither_flags({"results": {"detectors": []}})
            slither_ok = 0
            slither_err = err or "unknown"
        else:
            sf = parse_slither_flags(data)
            slither_ok = 1
            slither_err = ""

        emergency_fn = int(
            bool(re.search(r"emergency", " ".join(funcs), re.I))
            or bool(re.search(r"emergency", src, re.I))
        )

        owner_withdraw = int(
            rx["regex_owner_withdraw"] or sf["slither_arbitrary_send"] or sf["slither_ownerish_any"]
        )
        emergency_withdraw = int(rx["regex_emergency_withdraw"] or emergency_fn)
        unrestricted_mint = int(rx["regex_unrestricted_mint"])

        row = {
            "contract_id": cid,
            "slither_ok": slither_ok,
            "slither_error": slither_err,
            **rx,
            **sf,
            "owner_withdraw": owner_withdraw,
            "emergency_withdraw": emergency_withdraw,
            "unrestricted_mint": unrestricted_mint,
        }
        rows.append(row)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    ok_n = sum(r["slither_ok"] for r in rows)
    print(f"Wrote {OUT_CSV}  (rows={len(rows)}, slither_ok={ok_n})")


if __name__ == "__main__":
    main()
