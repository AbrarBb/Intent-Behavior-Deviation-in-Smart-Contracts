#!/usr/bin/env python3
"""
Enriched behavior feature extraction for rug-pull detection.

Heuristic regex flags for honeypot-ish patterns, access control, and liquidity
asymmetry. Outputs are 0/1 (or 0/1 for counts-as-binary) for merging into ML
datasets. Not a substitute for Slither or manual audit.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

# Column order must match ``extract_enriched_vector`` output.
ENRICHED_FEATURE_NAMES: tuple[str, ...] = (
    "approve_restricted_to_owner",
    "transfer_restricted",
    "burn_restricted",
    "liquidity_removal_guarded",
    "unguarded_public_state_mutation",
    "owner_hardcoded",
    "has_selfdestruct_or_delegatecall",
    "asymmetric_liquidity_flow",
    "has_fallback",
    "liquidity_asymmetric_no_remove",
)


def _strip_solidity_comments(source_code: str) -> str:
    out = re.sub(r"//[^\n]*", "", source_code)
    out = re.sub(r"/\*.*?\*/", "", out, flags=re.DOTALL)
    return out


def extract_honeypot_patterns(source_code: str) -> Dict[str, int]:
    """Return binary (0/1) flags for each enriched pattern."""
    source_clean = _strip_solidity_comments(source_code)

    patterns: Dict[str, int] = {}

    patterns["approve_restricted_to_owner"] = int(
        bool(
            re.search(
                r"function\s+approve\s*\([^)]*\)\s*(?:public|external)?[^{]*\{[^}]{0,800}"
                r"(?:require\s*\(\s*msg\.sender\s*==\s*owner|"
                r"if\s*\(\s*msg\.sender\s*!=\s*owner\s*\)\s*(?:revert|throw))",
                source_clean,
                re.DOTALL | re.IGNORECASE,
            )
        )
    )

    patterns["transfer_restricted"] = int(
        bool(
            re.search(
                r"function\s+(?:transfer|transferFrom)\s*\([^)]*\)\s*(?:public|external)[^{]*\{[^}]{0,800}"
                r"(?:onlyOwner|onlyRole|require\s*\(\s*msg\.sender\s*==\s*owner|"
                r"_whitelist|isExcluded)",
                source_clean,
                re.DOTALL | re.IGNORECASE,
            )
        )
    )

    patterns["burn_restricted"] = int(
        bool(
            re.search(
                r"function\s+(?:burn|burnFrom)\s*\([^)]*\)\s*(?:public|external)?[^{]*\{[^}]{0,800}"
                r"(?:onlyOwner|msg\.sender\s*==\s*owner|require\s*\([^)]*owner)",
                source_clean,
                re.DOTALL | re.IGNORECASE,
            )
        )
    )

    patterns["liquidity_removal_guarded"] = int(
        bool(
            re.search(
                r"function\s+(?:removeLiquidity|removeLiquidityETH|withdraw|drain|exit)\s*\([^)]*\)\s*(?:public|external)?[^{]*\{[^}]{0,1200}"
                r"(?:require\s*\([^)]*(?:block\.timestamp|block\.number|now|lock|unlock)|onlyOwner)",
                source_clean,
                re.DOTALL | re.IGNORECASE,
            )
        )
    )

    patterns["unguarded_public_state_mutation"] = int(
        bool(
            re.search(
                r"function\s+(?:mint|setOwner|setRouter|setLiquidityPool)\s*\([^)]*\)\s+public\s*\{(?![^}]{0,400}onlyOwner)",
                source_clean,
                re.DOTALL | re.IGNORECASE,
            )
        )
    )

    patterns["owner_hardcoded"] = int(
        bool(
            re.search(
                r"address\s+(?:public\s+)?(?:constant|immutable)?\s*\w*owner\w*\s*=\s*0x[0-9a-fA-F]{40}\b",
                source_clean,
                re.IGNORECASE,
            )
        )
    )

    patterns["has_selfdestruct_or_delegatecall"] = int(
        bool(
            re.search(
                r"(?:selfdestruct\s*\(|\.delegatecall\s*\(|delegatecall\s*\()",
                source_clean,
                re.IGNORECASE,
            )
        )
    )

    patterns["asymmetric_liquidity_flow"] = int(
        bool(
            re.search(
                r"(?:uniswapV2Router|IUniswapV2Router|swapRouter)\.addLiquidity",
                source_clean,
                re.IGNORECASE,
            )
        )
        and not bool(
            re.search(
                r"removeLiquidity(?:ETH)?",
                source_clean,
                re.IGNORECASE,
            )
        )
    )

    patterns["has_fallback"] = int(
        bool(
            re.search(
                r"(?:fallback|receive)\s*\(\s*\)\s*(?:external|public)?\s*(?:payable)?\s*\{",
                source_clean,
                re.IGNORECASE,
            )
        )
    )

    has_add = bool(re.search(r"addLiquidity", source_clean, re.IGNORECASE))
    has_remove = bool(
        re.search(r"(?:removeLiquidity|removeLiquidityETH)", source_clean, re.IGNORECASE)
    )
    patterns["liquidity_asymmetric_no_remove"] = int(has_add and not has_remove)

    return patterns


def extract_enriched_vector(source_code: str) -> list[int]:
    """Ordered 0/1 vector aligned with ``ENRICHED_FEATURE_NAMES``."""
    d = extract_honeypot_patterns(source_code)
    return [int(d[name]) for name in ENRICHED_FEATURE_NAMES]


def extract_enriched_features(sol_file: Path) -> Dict[str, int]:
    """Load a .sol file and return all enriched flags (0/1)."""
    zeros = {name: 0 for name in ENRICHED_FEATURE_NAMES}
    try:
        source = sol_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return zeros
    d = extract_honeypot_patterns(source)
    return {k: int(d.get(k, 0)) for k in ENRICHED_FEATURE_NAMES}


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        print(extract_enriched_features(p))
    else:
        print("Usage: python 06b_extract_enriched_behavior_features.py <file.sol>")
