#!/usr/bin/env python3
"""
Phase 2 — Data Acquisition (Verified Solidity Source via Etherscan)
====================================================================
Consumes master_dataset.csv from Phase 1 and retrieves on-chain verified
source code for each Ethereum address using the public Etherscan HTTP API.

Design notes for replication:
- Fixed per-request delay enforces ≤4 calls/s, safely under the free-tier
  guidance of 5 calls/s.
- Failures are non-fatal: the loop continues so long runs are robust to
  throttling, unverified contracts, or transient network errors.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "YOUR_KEY_HERE")
# V1 api.etherscan.io/api was deprecated (2025-08); V2 requires chainid (1 = Ethereum mainnet).
ETHERSCAN_API_URL = "https://api.etherscan.io/v2/api"
ETHEREUM_CHAIN_ID = "1"
REQUEST_DELAY_SEC = 0.25  # Free tier: max ~5 calls/s; 0.25 s → 4 calls/s ceiling

SCRIPT_DIR = Path(__file__).resolve().parent
MASTER_CSV = SCRIPT_DIR / "master_dataset.csv"
RAW_DATA_DIR = SCRIPT_DIR / "raw_data"


def _safe_filename(name: str, fallback: str = "Contract.sol") -> str:
    """
    Produce a single-file .sol name suitable for cross-platform storage.
    Strips path components and replaces characters invalid on Windows/macOS/Linux.
    """
    name = (name or "").strip()
    if not name:
        return fallback if fallback.endswith(".sol") else f"{fallback}.sol"
    base = Path(name).name
    base = re.sub(r'[<>:"/\\|?*]', "_", base)
    base = base.strip(" .") or "Contract"
    return base if base.lower().endswith(".sol") else f"{base}.sol"


def fetch_sourcecode(address: str) -> tuple[dict | None, str | None]:
    """
    Query getsourcecode for one address.

    Returns (result_dict, error_message). On success, error_message is None
    and result_dict is the first element of the API ``result`` list.
    """
    params = {
        "chainid": ETHEREUM_CHAIN_ID,
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": ETHERSCAN_API_KEY,
    }
    url = f"{ETHERSCAN_API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "AcademicResearch/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return None, f"URL error: {exc.reason}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in response: {exc}"
    except TimeoutError:
        return None, "Request timed out"
    except OSError as exc:
        return None, f"Network/OS error: {exc}"

    status = str(payload.get("status", ""))
    message = str(payload.get("message", ""))
    result = payload.get("result")

    if isinstance(result, str):
        snippet = result.strip()
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        return None, f"API status={status!r} message={message!r}: {snippet}"

    if not isinstance(result, list) or not result:
        return None, "Empty or malformed `result` list"

    if status != "1":
        return None, f"API status={status!r} message={message!r}"

    row = result[0]
    if not isinstance(row, dict):
        return None, "Unexpected `result[0]` type"
    return row, None


def main() -> None:
    if ETHERSCAN_API_KEY in ("", "YOUR_KEY_HERE"):
        print(
            "[WARNING] Set ETHERSCAN_API_KEY to a valid Etherscan API key "
            "before large-scale downloads."
        )

    addresses = pd.read_csv(MASTER_CSV)["address"].astype(str).str.strip().tolist()
    total = len(addresses)
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0
    skip_count = 0

    for idx, address in enumerate(addresses, start=1):
        if not address:
            print(f"[{idx}/{total}] SKIP: empty address", flush=True)
            skip_count += 1
            continue

        row, err = fetch_sourcecode(address)
        time.sleep(REQUEST_DELAY_SEC)

        if err:
            print(f"[{idx}/{total}] WARN {address}: {err}", flush=True)
            skip_count += 1
            continue

        source = row.get("SourceCode")
        if source is None or str(source).strip() == "":
            print(f"[{idx}/{total}] WARN {address}: no verified source code", flush=True)
            skip_count += 1
            continue

        contract_name = str(row.get("ContractName") or "").strip()
        filename = _safe_filename(contract_name)

        out_dir = RAW_DATA_DIR / address
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / filename
            out_path.write_text(str(source), encoding="utf-8", errors="strict")
        except OSError as exc:
            print(f"[{idx}/{total}] WARN {address}: could not write file ({exc})", flush=True)
            skip_count += 1
            continue

        success_count += 1
        rel = out_path.relative_to(SCRIPT_DIR)
        print(f"[{idx}/{total}] Fetched {address} successfully -> {rel}", flush=True)

    print("-" * 60)
    print(
        f"Acquisition complete. Success: {success_count}, "
        f"skipped/failed: {skip_count}, total rows: {total}"
    )
    print(f"Output root: {RAW_DATA_DIR}")
    print("-" * 60)


if __name__ == "__main__":
    main()
