# Project structure and execution map

## Unit layer

| Module | Responsibility | Main contract |
|---|---|---|
| `config.py` | Parse and validate YAML | Reject incomplete/invalid experiment definitions |
| `io.py` | CSV/Parquet I/O and file hashing | Fail on unsupported formats or missing paths |
| `schema_inspector.py` | Sample/metadata schema check | Verify configured label and temporal fields before full load |
| `data_audit.py` | Dataset audit and pointwise physical filters | Count every removal; do not deduplicate |
| `labels.py` | Stable label IDs and one held-out family | Unknown family is excluded from all fitted stages |
| `features.py` | Nested feature schemas | Time, labels, IDs excluded; unexpected nonnumeric predictors fail |
| `splitting.py` | Global forward-time partition | Common boundaries, preserved equal timestamps, embargo and full-flow interval checks |
| `preprocessing.py` | Imputation/scaling | Learn statistics on proper training only |
| `model.py` | One multiclass GBDT | Closed-set probabilities; no calibration claim |
| `open_set.py` | Mahalanobis/Weibull score and threshold | Geometry/tail fit separated in proper training; threshold fitted on validation |
| `conformal.py` | Marginal and non-pooled Mondrian predictors | Same fixed classifier; calibration rows only; no class pooling |
| `triage.py` | Routing and selective metrics | Singleton must match top-1; OSR, escalation, and autonomy kept distinct |
| `transfer.py` | Separate binary transfer study | Fixed samples across seeds; train-source preprocessing only |
| `monotonic.py` | Separate binary synthetic monotonicity study | Explicit perturbation only; feature-wise monotonicity audit |
| `pipeline.py` | Main integration orchestrator | One end-to-end data lineage and run metadata |

## Integration layer

The canonical main flow is:

`CSV/Parquet → source audit → pointwise validity filters → label map → feature manifest → global temporal split → train-only preprocessing → GBDT → OSR geometry/tail fit → OSR validation threshold → conformal calibration → locked test scoring → selective routing → metrics/artifacts`.

No test labels are consumed until evaluation. The held-out family cannot enter model fitting, OSR fitting, OSR threshold selection, or conformal calibration. The split metadata and all fitted-stage parameters are saved in `run_metadata.json`.

The transfer and monotonicity commands are separate binary experiments, not hidden subroutines of the main multiclass system.

## Project layer

`README.md` gives setup and command instructions. `docs/RESEARCH_PROTOCOL.md` defines the experimental design. `docs/CLAIM_LEDGER.md` constrains manuscript language. `docs/IMPLEMENTATION_AUDIT.md` records design and limitations. `docs/REPRODUCIBILITY_CHECKLIST.md` defines the pre-publication acceptance steps. `docs/VALIDATION_REPORT.md` records what was actually tested in this environment.
