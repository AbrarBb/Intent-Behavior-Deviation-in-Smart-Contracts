# Stage 2 workflow: preserve artifacts, analyze, enrich

This doc replaces Unix-only examples (`ps aux`, `mkdir -p`) with **Windows (PowerShell)** and adds repo-specific safeguards.

## Critical: do not overwrite a finished full-corpus build

Canonical outputs use the stem **`ml_dataset_verified_full`**:

- `artifacts/ml_dataset_verified_full.npz`
- `artifacts/ml_dataset_verified_full_meta.csv`
- `artifacts/ml_dataset_verified_full.csv`
- `artifacts/ml_dataset_verified_full_config.json`

**Smoke tests** must use a different stem so they never clobber Stage 2:

```powershell
python 12_build_verified_full_ml_dataset.py --max-contracts 50 --output-tag smoke50 --no-csv
```

That writes `artifacts/ml_dataset_verified_full_smoke50.*` instead.

Slither is **off** unless you pass `--enable-slither`. There is **no** `--no-slither` flag.

---

## Is Stage 2 still running? (Windows)

```powershell
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -match '12_build_verified_full_ml_dataset' } |
  Select-Object ProcessId, CommandLine
```

Or check Task Manager → Details → `python.exe` → command line.

---

## Backup immediately after Stage 2 completes

From repo root:

```powershell
.\tools\backup_verified_full_artifacts.ps1
```

Optional custom folder:

```powershell
.\tools\backup_verified_full_artifacts.ps1 -Destination "artifacts\stage2_slither_only_backup"
```

---

## If smoke test already overwrote artifacts

If `ml_dataset_verified_full_config.json` shows `total_contracts` ≈ 3–50 instead of ~3324, the canonical files were overwritten. **Re-run Stage 2** (with `--enable-slither` as you intended), then **backup** as above.

---

## Path A — Slither-only analysis (recommended first)

Assumes default stem and full row count (~3324).

**Diagnostics:**

```powershell
python tools\post_stage2_diagnostics.py
```

**Ablation:**

```powershell
python 15_ablation_study.py
python 14_feature_importance.py
```

**Training (optional):**

```powershell
python 13_train_verified_full_models.py
```

Use a different NPZ if you used `--output-tag`:

```powershell
python 13_train_verified_full_models.py --npz artifacts\ml_dataset_verified_full_smoke50.npz
```

---

## Path B — Slither + enrichment (full rebuild)

Another **1–3+ hours**. Keeps default stem only if you are **replacing** the corpus on purpose.

```powershell
$env:PATH = "$env:APPDATA\Python\Python314\Scripts;$env:PATH"
$env:PYTHONUNBUFFERED = "1"
python 12_build_verified_full_ml_dataset.py `
  --enable-slither `
  --slither-skip-solc-install `
  --enable-enriched-features `
  --slither-timeout 180
```

Then:

```powershell
python 15_ablation_study.py
python tools\post_stage2_diagnostics.py
```

---

## Path C — enrichment sampling only (no Slither, no overwrite)

Use **`--output-tag`** so the main artifacts stay untouched:

```powershell
python 12_build_verified_full_ml_dataset.py `
  --enable-enriched-features `
  --max-contracts 100 `
  --output-tag enrich_sample100 `
  --no-csv
```

Inspect `artifacts/ml_dataset_verified_full_enrich_sample100_meta.csv` or add CSV (omit `--no-csv`).

Run diagnostics on the tagged CSV:

```powershell
python tools\post_stage2_diagnostics.py --csv artifacts\ml_dataset_verified_full_enrich_sample100.csv
```

---

## Exact sequence after Stage 2 completes (~35 min lab time)

### 0) Confirm the builder is not still running

`ps | findstr` does **not** show Python command lines. Use:

```powershell
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -match '12_build_verified_full_ml_dataset' } |
  Select-Object ProcessId, CommandLine
```

No rows → proceed. Rows present → wait for completion.

### 1) Backup canonical stem (~30 s)

```powershell
.\tools\backup_verified_full_artifacts.ps1
```

Verify:

```powershell
Get-ChildItem artifacts\stage2_slither_only_backup\
```

Expect: `ml_dataset_verified_full.npz`, `ml_dataset_verified_full_meta.csv`, `ml_dataset_verified_full.csv`, `ml_dataset_verified_full_config.json`.

### 2) Path A diagnostics (~2 min)

```powershell
python tools\post_stage2_diagnostics.py
```

Expect `total_contracts` / CSV rows ≈ **3324** (or your verified-manifest size). A warning appears if **n < 1000** (smoke artifact).

### 3) Ablation (~CPU-bound; often well under 30 min on full CSV)

```powershell
python 15_ablation_study.py
```

Optional explicit CSV (default is `artifacts/ml_dataset_verified_full.csv`):

```powershell
python 15_ablation_study.py --csv artifacts\ml_dataset_verified_full.csv
```

### 4) Optional: feature importance

```powershell
python 14_feature_importance.py
```

### 5) Optional: hold-out training

```powershell
python 13_train_verified_full_models.py
```

### What to record for the paper / advisor

- Backup path confirmation  
- Full console output of `post_stage2_diagnostics.py`  
- Ablation table: Intent-only / Behavior-only / Hybrid — F1 and ROC-AUC  
- Baseline comparison (regex-only Slither columns): Behavior-only F1 **0.6945** (your prior snapshot; recompute after new CSV)

### Parallel: enrichment preview (does not touch canonical stem)

`post_stage2_diagnostics.py` needs a **CSV**. Omit `--no-csv` so the flat file exists:

```powershell
python 12_build_verified_full_ml_dataset.py `
  --max-contracts 100 `
  --output-tag enrich_preview_100 `
  --enable-enriched-features
```

Then:

```powershell
python tools\post_stage2_diagnostics.py --csv artifacts\ml_dataset_verified_full_enrich_preview_100.csv
```

---

## Decision tree (short)

1. Stage 2 finished → **backup** → Path A diagnostics + ablation.  
2. Behavior-only F1 still weak → Path C (quick) or Path B (full Slither + enrich).  
3. Always use **`--output-tag`** for any non-production rebuild.
