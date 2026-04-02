"""
Lightweight Solidity text extraction (no compiler).
Used for pilot folders (comments / NatSpec) and Streamlit heuristics.
"""

from __future__ import annotations

import re
from pathlib import Path


def _strip_solidity_strings(src: str) -> str:
    """Remove quoted string literals to avoid false comment matches inside strings."""

    def repl_single(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    def repl_double(m: re.Match[str]) -> str:
        return " " * (m.end() - m.start())

    out = re.sub(r"'(?:\\.|[^'\\])*'", repl_single, src)
    out = re.sub(r'"(?:\\.|[^"\\])*"', repl_double, out)
    return out


def extract_nat_spec_and_comments(src: str) -> str:
    """Collect ///, /** */, and // lines (best-effort)."""
    cleaned = _strip_solidity_strings(src)
    chunks: list[str] = []

    for m in re.finditer(r"/\*\*.*?\*/", cleaned, flags=re.DOTALL):
        chunks.append(m.group(0))
    for m in re.finditer(r"///.*", cleaned):
        chunks.append(m.group(0).strip())
    for m in re.finditer(r"//[^\n]*", cleaned):
        line = m.group(0).strip()
        if line.startswith("///"):
            continue
        chunks.append(line)

    return "\n".join(chunks).strip()


def extract_function_names(src: str) -> list[str]:
    """Heuristic function name list (misses some edge cases; fine for pilot)."""
    names: list[str] = []
    for m in re.finditer(
        r"\bfunction\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
        src,
    ):
        names.append(m.group(1))
    if re.search(r"\breceive\s*\(\s*\)\s*external", src):
        names.append("receive")
    if re.search(r"\bfallback\s*\(\s*\)\s*external", src):
        names.append("fallback")
    return names


def write_pilot_artifacts(code_path: Path, out_dir: Path) -> None:
    src = code_path.read_text(encoding="utf-8", errors="replace")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "code.sol").write_text(src, encoding="utf-8")
    (out_dir / "text.txt").write_text(extract_nat_spec_and_comments(src), encoding="utf-8")
    funcs = extract_function_names(src)
    (out_dir / "functions.txt").write_text("\n".join(funcs), encoding="utf-8")


def regex_behavior_flags(src: str, func_names: list[str]) -> dict[str, int]:
    """
    Offline heuristics aligned with the paper narrative (not sound static analysis).
    Complements Slither when compilation fails or for the Streamlit demo.
    """
    s = src.lower()
    joined = " ".join(fn.lower() for fn in func_names)

    owner_mod = bool(re.search(r"\bonlyOwner\b|\bonlyRole\b|\bauth\b", src))
    withdrawish = bool(
        re.search(r"\bwithdraw\w*\b|\brescue\w*\b|\brecover\w*\b", joined)
        or re.search(r"\bwithdraw\w*\b|\brescue\w*\b", s)
    )
    mintish = bool(re.search(r"\bmint\w*\b", joined) or re.search(r"\bmint\w*\b", s))
    emergency = bool(re.search(r"emergency", joined) or re.search(r"emergency", s))

    owner_withdraw = int(owner_mod and withdrawish)
    emergency_withdraw = int(emergency and withdrawish)

    unrestricted_mint = 0
    for m in re.finditer(
        r"function\s+(?:_)?mint\w*\s*\([^)]*\)\s*([^{]+)\{",
        src,
        flags=re.IGNORECASE,
    ):
        head = m.group(1)
        if re.search(r"\b(public|external)\b", head) and not re.search(
            r"\bonlyOwner\b|\bonlyRole\b|\bauth\b", head
        ):
            unrestricted_mint = 1
            break

    return {
        "regex_owner_withdraw": owner_withdraw,
        "regex_emergency_withdraw": emergency_withdraw,
        "regex_unrestricted_mint": unrestricted_mint,
    }
