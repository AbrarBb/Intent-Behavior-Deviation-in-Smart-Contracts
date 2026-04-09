# Contributions and gap vs. prior work

## Problem

Smart contracts are trusted partly through **natural language** (comments, NatSpec, marketing copy) while **behavior** is determined by executable Solidity. **Rug pulls** and related scams often exhibit **intent–behavior deviation**: the text promises user safety or fairness while the code retains **privileged withdrawal**, **unchecked mint**, or other **owner-controlled** fund paths.

## Gap in related work

| Stream | Typical focus | Typical limitation |
|--------|----------------|---------------------|
| NLP / documentation mining | Sentiment, topics, spec extraction from text | Rarely **grounded** in the **same** contract’s executable constraints |
| Static analysis (e.g. Slither) | Vulnerabilities, centralization, call graphs | Rarely **compared** to **what developers claim** in comments |
| On-chain heuristics | Transaction patterns, liquidity | Does not read **developer-facing intent** |

This work targets the **joint** question: for each contract instance, do **claimed intent** (as embedded from text) and **observed behavior features** (Slither + heuristics) support a coherent story, and can a **learned model** separate harmful mismatches from benign baselines?

## Contribution bullets (for the paper)

1. **Paired intent–behavior representation.** A reproducible pipeline that combines **Sentence-BERT** vectors over extracted / curated intent text with **tabular behavior features** (regex proxies and optional Slither detectors) on **the same** contract, enabling deviation-focused classification rather than text-only or code-only baselines.

2. **Corpus construction transparency.** Explicit reporting of **address-level balance** vs **Etherscan-verified** subsets (including imbalance after verification) and an optional **seed-fixed balanced verified** cohort for fair model comparison—reducing confusion between “balanced at crawl time” and “analyzable in practice.”

3. **Human-grounded labels (protocol).** A documented **manual annotation** scheme (`intent_label`, `behavior_label`, `final_label`) with guidance for inter-rater agreement, intended to support **auditability** beyond weak labels from external lists alone.

4. **Empirical baselines and ablations.** Scripted **hybrid vs intent-only vs behavior-only** (and behavior-without-Slither-detector-columns) experiments with stratified evaluation metrics suitable for **Methods** and **Threats** sections.

## Suggested positioning sentence (abstract)

> Prior contract security work often treats natural language and static analysis separately; we operationalize **intent–behavior deviation** on paired (text, code) instances and evaluate whether **hybrid** models outperform single-modality baselines on a verified-source Ethereum corpus with transparent cohort statistics.
