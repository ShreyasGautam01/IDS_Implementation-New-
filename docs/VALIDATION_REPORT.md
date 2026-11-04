# Validation report — IDS Reliability Rebuild v2.0.0

## Scope

This report records software validation of the rebuilt implementation. It does not present new scientific results on the UQ NetFlow datasets.

## Executed checks

- Python bytecode compilation: `python -m compileall -q src tests`.
- Unit and synthetic integration suite: `python -m pytest -q`.
- CLI parser smoke test: `python -m ids_reliability --help`.
- Deterministic, disjoint chunked sample test for the transfer experiment, including multi-chunk repeatability.
- Editable local package installation without dependency re-resolution: `python -m pip install -e . --no-deps --no-build-isolation`.
- Synthetic end-to-end execution writes test predictions, per-class metrics, run metadata, conformal comparisons, OSR diagnostics, and tail-size sensitivity outputs.

The final local run completed with **29 tests passed in the most recent run**. The included tests exercise code paths with deterministic synthetic data; they do not demonstrate NetFlow model accuracy or robustness.

## Later validation addendum (2026-11-04)

The statements in the original report below describe the validation state when it was written and are not the current experiment status. Subsequent work:

- The suite was rerun after the timestamp-free v2 transfer fallback and sampler optimization: **34 tests passed**.
- The full NF-UNSW-NB15-v3 audit completed: 2,365,424 rows; start/end timestamp parsing valid for all rows; no end-before-start intervals; dataset SHA-256 is recorded in run metadata.
- The canonical temporal pipeline completed for seeds 42, 43, 44, and 45 on a fixed split. Per-seed run artifacts remain local under `artifacts_rebuilt/`; a summary is in `EXPERIMENT_RESULTS.md` and `multi_seed_summary.csv`.
- OSR/routing metrics were independently recomputed from saved predictions and matched metadata exactly. Closed-set accuracy cannot be independently reconstructed from the saved prediction CSV alone because classifier top-1 labels on OSR-rejected rows are not exported.
- A bounded four-seed binary transfer pilot completed on supplied v2 files using a stratified-random source split. It is not a temporal experiment; see `CROSS_DATASET_V2_PILOT.md`.
- The protocol's four-schema binary transfer experiment completed on NF-UNSW-NB15-v3 and NF-CICIDS2018-v3 with four seeds in both directions. Its source-side in-domain split is chronological; its fixed target sample spans the target time range. See `CROSS_DATASET_V3_EXPERIMENT.md`.
- The separate v3 binary monotonicity sensitivity experiment completed for seed 42; see `MONOTONICITY_V3_EXPERIMENT.md`. It is a synthetic perturbation study, not a robustness guarantee.
- Feature-schema documentation was corrected to match the behavior asserted by source tests. Original manuscript intent still requires confirmation.

## Environment used for the local check

- Python 3.13.5
- NumPy 2.3.5
- pandas 2.2.3
- scikit-learn 1.8.0
- SciPy 1.17.0
- PyYAML 6.0.3
- pytest 9.0.2

`pyarrow` was not installed in this execution environment. Consequently, the Parquet schema-inspection and Parquet loading paths were not exercised here. CSV parsing, algorithmic units, CLI parsing, and the synthetic end-to-end pipeline were exercised. The GitHub Actions workflow additionally defines tests on Python 3.11 and 3.12, but those remote CI jobs have not been run from this environment.

## Not executed in the original validation report (historical state)

- No real UQ NetFlow v3 files were supplied to this session.
- No full-dataset audit, v3 timestamp verification, or v3 model fit was executed.
- No v3 transfer, OSR, conformal, triage, or monotonicity metrics have been generated.
- No original draft-paper numbers have been reused or represented as v3 results.
- No live SOC deployment, line-rate test, or analyst workload evaluation was performed.

## Acceptance before scientific interpretation

1. Download the exact UQ v3 release files and record their source URL, date, size, and SHA-256.
2. Run `inspect-schema`; verify start/end timestamp columns and units against the downloaded file's documentation.
3. Run `audit`; review row filtering, duplicate sample, label counts, and timestamp validity.
4. Run the canonical pipeline. Check realized split windows and the count of withheld-family observations in the future test window. The default run deliberately fails if fewer than 20 unknown-family test rows remain.
5. Inspect `run_metadata.json`, all tail diagnostics, and per-class outputs before making any claim.
6. Repeat predeclared seeds and regenerate the manuscript only from resulting machine-readable artifacts.

A passing synthetic integration test establishes that modules connect and produce expected artifact types; it does not establish the validity of the source dataset, exchangeability under temporal drift, Weibull tail adequacy, or performance on unseen attacks.
