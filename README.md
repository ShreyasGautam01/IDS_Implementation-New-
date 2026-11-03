# IDS Reliability Rebuild (v2.0.0)

This is a clean, claim-aligned rebuild of the IDS reliability project. It is intentionally separate from the original repository so that the original code, draft paper, metrics, and commit history remain untouched.

The implementation is organized around one canonical multiclass pipeline:

1. audit and validate source data;
2. clean only explicitly defined invalid records and report every removal;
3. make one **global timestamp-ordered** train/validation/calibration/test split;
4. fit imputation and robust scaling on training rows only;
5. train one multiclass `HistGradientBoostingClassifier`;
6. fit class-conditional Mahalanobis/Weibull tail scores on training rows and calibrate the rejection operating point on validation rows;
7. fit non-pooled Mondrian conformal prediction on the separate calibration rows;
8. route only when the conformal set is a singleton, that singleton agrees with classifier top-1, OSR does not reject, and the evidence margin clears the configured threshold;
9. evaluate the locked test period and save row-level and aggregate evidence.

The binary cross-dataset transfer and binary monotonicity experiments are separate commands. They are not represented as properties of the multiclass end-to-end pipeline.

## Important scope and validity rules

- The corrected primary experiment targets the UQ NetFlow v3 release. UQ documents v3 as the NetFlow version that adds temporal features; v2 does not provide the required temporal fields. The configured timestamp column must exist and parse. The pipeline stops rather than inventing chronological order.
- Temporal cut points are global, derived from known-family rows only, and preserve equal timestamps in the same partition. They are not calculated independently per class. The configured start/end times are used to exclude flows crossing partition boundaries; the withheld family's timestamps do not influence the cut points.
- The held-out family is excluded from train, validation, and calibration. Only its observations in the final test time window are evaluated; earlier observations are reported as excluded from this temporal OSR experiment.
- A known class that first appears after the training window causes a hard failure. It is not silently remapped or treated as a known trained class.
- Invalid duration and zero-packet records are removed using explicit rules; counts are recorded. Rows are **not deduplicated**. A deterministic sample duplicate audit is reported instead.
- Missing or non-finite feature values are imputed using medians learned from training data only. The robust scaler is also fit on training data only.
- The GBDT probabilities are not assumed to be calibrated. They are used as nonconformity scores; conformal validity depends on exchangeability, not on probability calibration. The run also reports a marginal split-conformal baseline alongside Mondrian prediction on the same data.
- The conformal implementation never pools calibration scores from different classes. An empty calibration stratum conservatively includes that candidate class in every prediction set.
- Ordinary class-conditional conformal guarantees require exchangeability within each class. With future-time test data and distribution shift, this must not be assumed; the reported temporal coverage is empirical unless the assumption is independently justified.
- The OSR evaluation includes a max-probability unknown-score baseline so the EVT score is not judged in isolation. A predeclared minimum of 20 unknown observations is required in the locked test window by default; the rare held-out `Worms` class in the UQ v3 catalog has only 158 rows, so its time distribution and realized test support must be reviewed before an open-set claim. Class geometry and Weibull tail fitting use disjoint, chronologically ordered subsets of proper training data. Tail-fit diagnostics and predeclared tail-size sensitivity are exported; these are descriptive and do not establish formal EVT validity. OSR rejection thresholds are class-specific with respect to the nearest fitted class tail. A class with fewer than 20 validation observations assigned to its tail gets threshold 1.0 (no OSR rejection for that nearest-class region), rather than borrowing another class's threshold.
- Monotonicity is evaluated in a separate binary experiment only. The multiclass integrated model does not claim a monotonicity guarantee.

See `docs/RESEARCH_PROTOCOL.md`, `docs/CLAIM_LEDGER.md`, and `docs/IMPLEMENTATION_AUDIT.md` before interpreting results.

## Setup (Windows PowerShell)

Use Python 3.11 or 3.12. The supported range is declared in `pyproject.toml`; `uv.lock` pins a reproducible environment.

```powershell
cd path\to\ids-implementation-rebuilt
uv sync --python 3.11
.\.venv\Scripts\Activate.ps1
```

To refresh the lock file after intentionally changing dependencies, run `uv lock`, then run `uv sync` and commit both `pyproject.toml` and `uv.lock`.

Copy the default config and edit the paths/columns to match the actual local Parquet files:

```powershell
Copy-Item configs\default.yaml configs\local.yaml
```

At minimum, verify these settings against the real file schema:

```yaml
dataset:
  release: "UQ NetFlow v3"
  path: "D:/Datasets/NF-UNSW-NB15-v3.csv"
  label_column: "Attack"
  binary_label_column: "Label"
  timestamp_column: "FLOW_START_MILLISECONDS"
  numeric_timestamp_unit: "ms"
  unknown_family: "Worms"
```

The UQ v3 dataset documentation identifies temporal features in the v3 release. Its temporal-analysis documentation describes `FLOW_START_MILLISECONDS` and `FLOW_END_MILLISECONDS` in milliseconds since the Unix epoch. Verify both fields, their units, and their semantics in the exact downloaded file before running. A v2 file is not a substitute: it lacks the v3 temporal additions. If there is no trustworthy timestamp field, the main temporal protocol cannot be run as a temporal experiment.

## Commands

Inspect the real file schema without loading the full dataset, then run the full audit before fitting anything:

```powershell
ids-reliability --config configs/local.yaml inspect-schema
ids-reliability --config configs/local.yaml audit
```

Run the canonical multiclass pipeline:

```powershell
ids-reliability --config configs/local.yaml run --seed 42
```

Run the separate binary cross-dataset ablation (the fixed target sample is reused across model seeds):

```powershell
ids-reliability --config configs/local.yaml cross-dataset `
  --dataset-a "D:/Datasets/NF-UNSW-NB15-v3.csv" `
  --dataset-b "D:/Datasets/NF-CSE-CIC-IDS2018-v3.csv" `
  --seeds 42 43 44 45
```

The supplied NetFlow v2 Parquet files have no trustworthy flow-start/end timestamps. They cannot be used for the temporal multiclass pipeline above. For a clearly labeled, non-temporal binary transfer ablation only, use the dedicated v2 config and local files:

```powershell
uv run ids-reliability --config configs/v2_transfer.yaml cross-dataset `
  --dataset-a "Datasets/NF-UNSW-NB15-V2.parquet" `
  --dataset-b "Datasets/NF-CSE-CIC-IDS2018-V2.parquet" `
  --seeds 42 43 44 45
```

When a source sample has no configured timestamp column, this command uses a fixed stratified random source train/test split and records `stratified_random_no_timestamp_available` in its output. These results are not temporal generalization estimates. The v2 config uses 10,000 source and 10,000 target rows per dataset as a bounded pilot; increase those sample sizes before a final transfer study.

Run the separate binary monotonicity sensitivity experiment:

```powershell
ids-reliability --config configs/local.yaml monotonicity --seed 42
```

Equivalent module invocation is available before installing the package:

```powershell
$env:PYTHONPATH = "src"
python -m ids_reliability --config configs/local.yaml audit
```

## Outputs

The main pipeline creates one timestamped run directory under `output.directory` with:

- `test_predictions.csv`: one row per locked test flow, including true/predicted category, route, OSR score/rejection, set size, evidence margin, and per-class conformal p-values;
- `per_class_metrics.csv`: per-class empirical coverage, OSR rejection, escalation, autonomy, and automated-subset accuracy;
- `conformal_comparison.csv` and `conformal_per_class_comparison.csv`: marginal SCP versus Mondrian MCP on the identical calibration and known-class test rows;
- `risk_coverage_curve.csv`: risk as a function of evidence-margin-ranked coverage;
- `osr_tail_fit_diagnostics.csv` and `osr_tail_size_sensitivity.csv`: per-class fitted-tail diagnostics and the predeclared tail-size sensitivity with separate validation thresholds;
- `run_metadata.json`: dataset checksum, row-removal audit, selected feature names, global temporal boundaries, class mapping, preprocessing provenance, classifier settings, OSR parameters/thresholds, conformal assumptions, policy, metrics, software versions, and config snapshot.

Cross-dataset and monotonicity experiments have their own directories and metadata. They do not overwrite the main run output. The cross-dataset sampler streams CSV chunks or Parquet record batches and keeps disjoint fixed samples; the main temporal pipeline loads its selected dataset into pandas memory.

## Validation

```powershell
python -m pytest -q
```

The included tests cover label mapping, feature selection, global temporal partitioning, train-only preprocessing, conformal p-values and empty strata, OSR calibration, triage metrics, and a complete synthetic end-to-end run. They do not validate the real dataset's timestamps, reproduce the original paper's reported numbers, or replace a full-data experiment.

## Research execution order

1. Run `audit` and inspect timestamp coverage, labels, schema, physical-filter counts, and duplicate sample report.
2. Confirm label/timestamp semantics from the dataset source documentation.
3. Run the full pipeline once with the locked default protocol; inspect metadata before interpreting metrics.
4. Run at least four predeclared seeds if seed variability is part of a claim. Use the same split and fixed target sample when isolating model-seed variability.
5. Run cross-dataset transfer separately and report directional performance, including negative MCC and low absolute scores.
6. Run the binary monotonicity experiment separately and retain benign false-positive rates alongside attack recall.
7. Regenerate the manuscript only from committed output artifacts and the claim ledger.

## What this project does not claim

It does not claim general topology invariance, guaranteed performance under arbitrary temporal shift, exact class-conditional coverage under non-exchangeable temporal shift, cross-class calibration pooling, universal zero-day detection, real-world SOC deployment safety, line-rate throughput, or adversarial robustness outside the explicitly defined binary perturbation experiment.
