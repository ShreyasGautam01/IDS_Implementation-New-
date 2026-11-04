# Claim Ledger — allowed manuscript claims for v2.0.0

## Provenance boundary for the legacy IEEE manuscript

The manuscript inside `D:\ResearchPaper\IDS_Reliability_Benchmark_IEEE_Final_Package.zip` is a separate, earlier binary Random Forest study using UNSW-NB15 and CIC-IDS2017. Its motivation—accuracy alone does not expose unreliable predictions, and reliability signals should be compared across distinct failure modes—may be cited as historical project context after bibliographic verification. Its methods, numerical results, and specific claimed gap are not evidence for the current NF-UNSW-NB15-v3 GBDT/Mahalanobis–Weibull experiment. The current study's research question must be justified independently and limited to the experiment actually run.

A directly related article by Arepalli et al., “Conformal prediction for network intrusion triage and analysis of unseen attack families” (*Discover Informatics*, 2026; DOI 10.1007/s44564-026-00033-y), was published on 2026-11-02. It evaluates conformal triage and unseen-family novelty across UNSW-NB15 and CIC-IDS2017, including a weekday-based temporal analysis. Do not claim that conformal triage plus unseen-attack evaluation is itself a novel contribution. Position the present work only as a narrow empirical extension on NF-UNSW-NB15-v3 with ordered temporal partitions, complete-flow interval boundary checks, an embargo, and sparse `Worms` support; even that distinction requires complete comparison with the related paper and literature.

This ledger is the contract between implementation, experiments, metrics, and manuscript language. A claim may be promoted only when the named artifact exists and passes the acceptance criteria.

| Topic | What the code computes | Permitted wording | Prohibited wording / condition |
|---|---|---|---|
| Temporal evaluation | Global boundaries calculated from known-family timestamps; equal starts remain together; optional complete-flow interval and embargo purging; unknown-family times do not set cut points | “A global known-data-derived timestamp holdout was used; complete flow intervals were enforced when verified start/end fields were available.” | “Leakage-free” or “strictly leakage-safe” without campaign/host-session/duplicate overlap analysis and verified timestamp semantics. |
| Preprocessing | Pointwise invalid-flow filters; train-only median imputation and RobustScaler | “Pointwise invalid rows were filtered; learned preprocessing was fit on training data only.” | Claim of training-only deduplication; no deduplication is performed. |
| Feature ablation | Exact features removed/retained by four configured schemas | “The tested feature groups had these directional effects on these two datasets.” | “Topology invariant” or generally domain-invariant without broader external validation. |
| GBDT output | Multiclass predicted class probabilities | “GBDT probability outputs” or “model scores.” | “Calibrated probabilities” unless a separate probability calibration procedure is added and evaluated. |
| OSR score | Class geometry fitted on earlier proper-training observations; Weibull tails fitted on a later disjoint training subset; validation-selected class-specific thresholds; tail-fit diagnostics and predeclared tail-size sensitivity; comparison with `1 - max(class probability)` | “Empirical Mahalanobis–Weibull tail anomaly score with validation-selected threshold.” | “Theorem-guaranteed EVT detector,” “zero-day identification,” or OSR superiority without baseline evidence and independent tail-fit validation. |
| OSR threshold | Per-nearest-class validation quantile | “Threshold selected on a separate validation period to target a known-class rejection rate.” | Claim that future test FPR is guaranteed to equal the validation target. |
| Conformal coverage | Non-pooled per-class split conformal set membership; marginal SCP baseline computed on the same calibration/test rows | “Observed empirical class-conditional coverage on the temporal test set.” | “Exact coverage guarantee under temporal shift” without exchangeability justification. |
| Empty calibration class | p-value 1 for that candidate class | “Conservative inclusion for unobserved calibration strata.” | Cross-class statistical borrowing or claimed informative coverage for missing classes. |
| Evidence margin | Difference between two largest class p-values | “Ranking/separation heuristic.” | “Probability of correctness” or independently calibrated confidence. |
| SOC routing | Singleton conformal set AND singleton label agrees with classifier top-1 AND no OSR rejection AND margin threshold | “Offline selective routing on the held-out benchmark test period; singleton disagreement with classifier top-1 is escalated.” | “Safe SOC deployment” or “production-ready autonomy.” |
| Unknown performance | OSR rejection, escalation, autonomous acceptance reported separately | Report each metric separately with denominator. | Equating escalation rate with OSR detection rate. |
| AURC | Margin-ranked risk over all test rows | “Evidence-margin ranking AURC.” | Claim that it exactly evaluates the routing gate; gate-specific automation metrics are separate. |
| Cross-dataset transfer | Binary GBDT, source-only scaling, fixed target sample, two directions | “Binary zero-shot cross-dataset transfer under the stated protocol.” | Claim that the full multiclass OSR/conformal/SOC architecture transfers. |
| Monotonicity | A separate binary-only constrained GBDT sensitivity experiment ran on NF-UNSW-NB15-v3 for seed 42 under the specified synthetic feature increases. | “On the specified perturbation and sampled feature ranges, the constrained model retained attack recall and had no observed decreasing probability steps.” | Do not claim multiclass monotonicity, arbitrary adversarial robustness, or generalization beyond this one seed/dataset/construction. |
| Runtime | Runtime not currently a primary recorded benchmark | No line-rate claim until measured on stated hardware and batch sizes. | “Line-rate” or low-latency deployment claim. |

## Required outputs before manuscript writing

- Main pipeline: `run_metadata.json`, `test_predictions.csv`, `per_class_metrics.csv`, `risk_coverage_curve.csv`.
- Cross-dataset: `cross_dataset_per_seed.csv`, `cross_dataset_summary.csv`, `experiment_metadata.json`.
- Monotonicity: `binary_monotonicity_sensitivity.csv`, `experiment_metadata.json`.
- Four main seeds (42–45) have been completed for NF-UNSW-NB15-v3; see `artifacts_rebuilt/EXPERIMENT_RESULTS.md` and `artifacts_rebuilt/multi_seed_summary.csv`. This supports descriptive seed variability for this fixed split, not generalization to other periods or datasets.
- A v2 cross-dataset pilot exists with 4 seeds and 10k disjoint source/target rows per dataset, but it uses random source splits because timestamps are absent. See `docs/CROSS_DATASET_V2_PILOT.md`; it is exploratory and non-temporal.
- The protocol's v3 binary cross-dataset schema experiment is complete on 200k disjoint source/target samples from NF-UNSW-NB15-v3 and NF-CICIDS2018-v3, with four schemas, four seeds, and both directions. See `docs/CROSS_DATASET_V3_EXPERIMENT.md`. It does not evaluate the full multiclass reliability pipeline.
- A one-seed real-data v3 binary monotonicity sensitivity run is complete under the specified synthetic feature perturbations. See `docs/MONOTONICITY_V3_EXPERIMENT.md`; do not generalize it to arbitrary attacks or the multiclass pipeline.
- Baseline comparisons with exact test sample sizes and class prevalences.
- Tail-fit diagnostics and sensitivity analysis are exported; independent tail validation/uncertainty analysis is still required before a strong EVT-method contribution.

## Results that must remain visible

1. Negative transfer or negative MCC in either direction.
2. Cases where max-probability or another simple OSR baseline outperforms the EVT score.
3. Low-coverage classes and empty calibration strata.
4. Unknown flows accepted for automation and their errors.
5. Any class for which validation data are insufficient to calibrate an OSR threshold.
6. Any temporal split that cannot include the held-out family in the final test window.

## Observed result requiring prominent reporting (2026-11-03)

- In all four seeds, the locked future test window contains 36 held-out `Worms` flows (0.0102% of test rows). EVT OSR rejects 1/36 (2.78%; AUROC 0.216), while the max-probability baseline AUROC is 0.970–0.974. This is evidence against the current EVT score's usefulness on this test period.
- Only two of nine nearest-class regions receive validation-fitted OSR thresholds. The other seven use the predeclared threshold 1.0 because their validation groups are too small. This limitation must be stated.
- Four-seed known closed-set accuracy is 0.9645–0.9647. Automated coverage is 0.6856–0.6950 and automated-subset accuracy is 0.9975–0.9980. These are benchmark results, not deployment-safety evidence.
- The temporal conformal coverage is empirical; exchangeability under temporal drift is not established. Unknown support is too small for precise estimates.
- Feature schema names denote removal ablations in the executable implementation and unit tests: baseline retains all configured groups; `set_a` excludes TTL; `set_b` excludes TTL plus window; `set_c` excludes all three groups. This code-defined interpretation is used for the completed binary transfer/schema experiment. Do not infer feature-ablation effects for the separate multiclass pipeline, which used `set_c` only.
- Four-seed post-run diagnostics are in `docs/RELIABILITY_DIAGNOSTICS.md`: tail sizes 25/50/100 do not make the EVT detector useful; marginal conformal has zero observed coverage for every non-benign known class; Mondrian improves class distribution but Analysis and Backdoor remain below nominal; routing aggregate accuracy hides very poor automated accuracy for Backdoor and Shellcode.
- Existing completed-run prediction files independently reproduce OSR and routing metrics. They do not separately export closed-set classifier top-1 labels on OSR-rejected rows, limiting closed-set metric recomputation from those CSVs alone.
- The pipeline exporter now includes `closed_set_predicted_class_id` and `closed_set_predicted_class` before OSR rejection. The four locked seeds were regenerated locally with this schema; each metadata file's global metrics, dataset identity, and temporal split match the original exactly, and closed-set accuracy recomputed from each CSV matches metadata. File hashes are recorded in `docs/REEXPORT_MANIFEST.csv`. The large regenerated files are excluded from the repository, so retain the local research archive when full per-flow auditability is needed.
