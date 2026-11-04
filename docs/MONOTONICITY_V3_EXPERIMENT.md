# Binary monotonicity sensitivity on NF-UNSW-NB15-v3

**Status:** Completed for seed 42 as the separate binary sensitivity experiment in Research Protocol RQ5. This is not part of the multiclass OSR, conformal, or routing evaluation.

## Protocol

- Dataset: the exact NF-UNSW-NB15-v3 file recorded in run metadata, SHA-256 `4ebb97bd74412d566137d95a6fc3ffd8f374f1cf8cfe204d007848e7a668f9b5`.
- Temporal partition: the configured 55/15/15/15 global chronological split, 60-second embargo, and complete-flow interval checks; the sensitivity metrics use the final partition.
- Model: binary HistGradientBoosting models, unconstrained and constrained to be non-decreasing in the selected volumetric features; seed 42.
- Training sensitivity: duplicate 5% of benign training rows after increasing all selected volumetric features by 6 training-set IQRs.
- Test sensitivity: increase those same volumetric features on attack test rows by 0, 0.25, 0.5, 0.75, or 1.0 times the configured 6-IQR perturbation; benign test rows remain unchanged.
- Monotonicity audit: vary each constrained feature independently on a deterministic 1,000-row test subset across the five levels.

## Results

The test partition contains 353,879 rows: 31,080 attacks and 322,799 benign flows. At the unperturbed level, attack recall was 99.98% for the unconstrained model and 99.98% for the constrained model; benign false-positive rates were 0.0291% and 0.0313%, respectively.

Under the specified simultaneous increase to attack features, unconstrained attack recall fell to 60.93%, 58.20%, 57.68%, and 44.49% at perturbation levels 0.25, 0.5, 0.75, and 1.0. The constrained model's attack recall was 99.99% at each of those levels. Its benign false-positive rate remained 0.0313%; this follows in part because perturbations were applied only to attack test rows.

The independent probability monotonicity audit found zero negative steps across 68,000 comparisons over 17 constrained features. The minimum observed step was 0. This verifies the configured monotonic direction on the sampled rows and feature ranges tested.

## Interpretation limits

This is one seed, one dataset, one feature schema (`set_c`), and one synthetic perturbation family. It does not establish robustness to realistic or adaptive attacks, feasible correlated feature changes, other directions of change, other datasets, or the multiclass reliability pipeline. The controlled increase changes several related flow-volume fields together and should be described exactly as this sensitivity construction. The small improvement at epsilon zero and lack of seed replications should also be retained in interpretation.

## Artifacts

- `artifacts_reexport/monotonicity_binary/binary_monotonicity_sensitivity.csv`
- `artifacts_reexport/monotonicity_binary/monotonicity_feature_audit.csv`
- `artifacts_reexport/monotonicity_binary/experiment_metadata.json`
- Implementation: `src/ids_reliability/monotonic.py`

During the first run attempt, infinite feature values reached the imputer. The monotonicity path was corrected to use the shared preprocessing finite-value replacement and clipping before transformations; the results above are from the successful rerun.
