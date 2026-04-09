# Ablation experiment report

Positive class: rugpull (y=1). Metrics from stratified hold-out (25%) and 5-fold CV.

## Mode: `hybrid`

**Description:** 384-d intent + 14 behavior columns
**Shape:** (100, 398)

**Best model (by hold-out F1):** `random_forest` (F1=0.9600)

### logistic_regression

- Hold-out F1 (positive): 0.8696
- 5-fold CV F1: 0.9714 ± 0.0233
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [2, 10]]`

### random_forest

- Hold-out F1 (positive): 0.9600
- 5-fold CV F1: 0.9628 ± 0.0343
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [0, 12]]`

### linear_svc

- Hold-out F1 (positive): 0.8696
- 5-fold CV F1: 0.9714 ± 0.0233
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [2, 10]]`

---

## Mode: `intent_only`

**Description:** 384-d intent only
**Shape:** (100, 384)

**Best model (by hold-out F1):** `random_forest` (F1=0.9600)

### logistic_regression

- Hold-out F1 (positive): 0.8696
- 5-fold CV F1: 0.9714 ± 0.0233
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [2, 10]]`

### random_forest

- Hold-out F1 (positive): 0.9600
- 5-fold CV F1: 0.9628 ± 0.0343
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [0, 12]]`

### linear_svc

- Hold-out F1 (positive): 0.8696
- 5-fold CV F1: 0.9714 ± 0.0233
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [2, 10]]`

---

## Mode: `behavior_only`

**Description:** 14 behavior columns only
**Shape:** (100, 14)

**Best model (by hold-out F1):** `logistic_regression` (F1=0.5882)

### logistic_regression

- Hold-out F1 (positive): 0.5882
- 5-fold CV F1: 0.7147 ± 0.0633
- Confusion matrix [tn fp; fn tp]: `[[13, 0], [7, 5]]`

### random_forest

- Hold-out F1 (positive): 0.5882
- 5-fold CV F1: 0.7000 ± 0.0408
- Confusion matrix [tn fp; fn tp]: `[[13, 0], [7, 5]]`

### linear_svc

- Hold-out F1 (positive): 0.5882
- 5-fold CV F1: 0.7000 ± 0.0408
- Confusion matrix [tn fp; fn tp]: `[[13, 0], [7, 5]]`

---

## Mode: `hybrid_no_slither_detectors`

**Description:** 384-d intent + 6 (merged+regex), Slither detector block removed
**Shape:** (100, 390)

**Best model (by hold-out F1):** `random_forest` (F1=0.9600)

### logistic_regression

- Hold-out F1 (positive): 0.8696
- 5-fold CV F1: 0.9714 ± 0.0233
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [2, 10]]`

### random_forest

- Hold-out F1 (positive): 0.9600
- 5-fold CV F1: 0.9628 ± 0.0343
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [0, 12]]`

### linear_svc

- Hold-out F1 (positive): 0.8696
- 5-fold CV F1: 0.9714 ± 0.0233
- Confusion matrix [tn fp; fn tp]: `[[12, 1], [2, 10]]`

---

## Error analysis (hybrid / best F1 model)

Use confusion matrix from **hybrid** + **random_forest** for qualitative follow-up: inspect false positives (benign predicted rugpull) and false negatives in `pilot_data/`.
- Matrix: `[[12, 1], [0, 12]]`
