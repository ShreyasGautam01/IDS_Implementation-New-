# Unit → Integration → Project Audit

## Unit layer

| Unit | Input | Output | Invariants checked | Test coverage |
|---|---|---|---|---|
| `config.py` | YAML file | validated typed config wrapper | required sections, split fractions, alpha, FPR, margin | valid and invalid configuration tests |
| `labels.py` | raw label values, held-out family | stable integer map | one benign label, one selected unknown family, deterministic known IDs | mapping tests |
| `features.py` | schema + dataframe columns/dtypes | selected features and removed/absent manifest | labels/time/identifiers excluded; unexpected nonnumeric columns fail | feature-ablation and nonnumeric tests |
| `data_audit.py` | raw dataframe | audit + pointwise cleaned dataframe | explicit invalid-row counts; no deduplication | exercised by end-to-end test |
| `splitting.py` | frame, start/end timestamp, target | global time windows and split manifest | cut points from known rows only; equal timestamps kept together; full flow intervals must fit within period when end-time exists; unknown excluded before test; all known training classes required | temporal boundary, unknown boundary invariance, invalid interval, withheld-label tests |
| `preprocessing.py` | raw numeric partitions | imputed/scaled matrices | fit only on train; partition columns must match | train-only-statistics test |
| `model.py` | transformed train matrix | one multiclass GBDT | at least two examples per known class; early stopping disabled | integration test |
| `open_set.py` | proper-train features/labels/timestamps; validation features/labels; test features | class-tail score, per-nearest-class threshold, rejection | chronological geometry/tail-fit subsets disjoint within proper training; explicit timestamps required; validation-only threshold; no cross-class threshold borrowing | OSR unit tests incl. no row-order fallback, tail diagnostics, and tail-size refit |
| `conformal.py` | calibration probabilities/labels | marginal quantile baseline plus class-conditional p-values, sets, margin | no pooling; ties conservative; empty strata include candidate label | p-value and empty-stratum tests |
| `triage.py` | classifier, conformal, OSR outputs and true labels | row records, per-class metrics, global metrics, risk curve | empty sets escalate; singleton must agree with top-1 before automation; OSR and escalation distinct; no automatic 100% when accepted set empty | triage unit tests incl. singleton disagreement |
| `transfer.py` | two datasets, seeds, schemas | bidirectional binary transfer metrics | chunked deterministic uniform sampling; disjoint source/target samples per dataset; fixed across seeds; source-only transform | integration-level fixed-sample transfer integration test |
| `monotonic.py` | binary dataset | isolated binary sensitivity and monotonicity audit | binary-only; configured positive constraints; same test rows for both models | synthetic binary monotonicity sensitivity integration test |

## Integration layer

The main pipeline integration order is fixed:

`load → raw audit → pointwise cleaning → label mapping → schema selection → global time split → train-only preprocessing → GBDT fit → OSR train fit → OSR validation threshold → conformal calibration → locked test predictions → triage evaluation → artifact export`.

No test labels are passed to model, OSR fitting, threshold selection, conformal fitting, or routing parameter selection. Test labels are used only after predictions are fixed, for evaluation.

The end-to-end synthetic integration test verifies that this entire path writes predictions, per-class metrics, and run metadata. It is a software integration test, not an empirical NetFlow result.

## Project layer

The project is considered execution-ready only when:

1. all unit and integration tests pass;
2. the exact local dataset schema and timestamp meaning are verified;
3. the audit output is reviewed for class availability and cleaning effects;
4. at least one full-data run completes without altering its protocol after test inspection;
5. repeated seeds complete for the stated experiment; separate transfer/monotonicity studies are either completed under their declared protocols or explicitly marked unrun and excluded from empirical claims;
6. the claim ledger is updated from real artifacts; and
7. the manuscript is regenerated from those artifacts.

## Known limitations not hidden by code

- The main temporal pipeline loads its selected dataset into pandas memory. The separate cross-dataset sampler streams CSV chunks or Parquet record batches, but its retained samples and model matrices are held in memory; this is bounded sampling, not constant-memory end-to-end training.
- Weibull diagnostics (in-sample fitted-tail log-likelihood/AIC and descriptive ECDF distance) and predeclared tail-size sensitivity are exported, but these do not establish model adequacy or formal EVT goodness-of-fit. Independent tail validation or bootstrap uncertainty analysis remains future work.
- The temporal split derives global boundaries from known-family records only. Complete flow-interval separation is enforced only when the configured start and end timestamps are both present, correctly parsed, and semantically verified from the exact downloaded dataset version. Campaign-level or host-session overlap is not automatically eliminated.
- Conformal theoretical coverage is conditional on within-class exchangeability, which may fail under temporal drift.
- Cross-dataset transfer and monotonicity are separate binary experiments, not part of the multiclass integrated pipeline.
- No measured live-SOC throughput, end-to-end latency, or analyst workload study is supplied by the code.

## Current empirical status (2026-11-04)

- The primary NF-UNSW-NB15-v3 temporal run completed for seeds 42–45 on one fixed split. Cross-run integrity and prediction-derived OSR/routing metrics were audited; see `EXPERIMENT_RESULTS.md` and `RELIABILITY_DIAGNOSTICS.md`.
- A bounded four-seed binary transfer pilot was run on the available v2 datasets. Both lacked flow timestamps, so source evaluation used stratified random splitting; these are exploratory non-temporal results and do not validate the v3 temporal-transfer protocol. See `CROSS_DATASET_V2_PILOT.md`.
- A real-data monotonicity experiment has not been run. Existing monotonicity coverage is synthetic testing only.
- The exact v3 file checksum is recorded. Its source bag identifier is known, but acquisition date is not yet in the experiment manifest.
