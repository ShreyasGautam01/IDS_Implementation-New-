# Reliability diagnostics across the four locked-split runs

These are post-run audits of the predeclared seed 42–45 outputs. No thresholds or model choices were changed using locked-test results. Values below are means across four model seeds on one fixed split; seed SD is not a confidence interval for new time periods or datasets.

## Run and seed integrity

All four runs have identical dataset SHA-256, configuration snapshots, temporal boundaries, test class counts, test row count (353,889), and row-ordered test labels. The continuous OSR scores, rejection flags, and tail-size sensitivity outputs are identical across runs because OSR geometry, Weibull fits, and thresholds are deterministic functions of the fixed data and split; they do not depend on the classifier random seed. Therefore the four seeds measure classifier-seed variability for classification/conformal/routing outputs, but do not provide four independent replications of OSR behavior. The repeated OSR rows should be reported once with the fixed-split denominator, not presented as independent evidence or used to imply zero uncertainty.

## OSR tail-size sensitivity

| Tail rows | Validation known rejection | Test known rejection | Test unknown rejection | Unknown AUROC | Unknown AUPR |
|---:|---:|---:|---:|---:|---:|
| 25 | 4.35% | 4.57% | 0/36 (0%) | 0.220 | 0.000092 |
| 50 (primary) | 4.85% | 4.96% | 1/36 (2.78%) | 0.216 | 0.000084 |
| 100 | 4.92% | 5.12% | 1/36 (2.78%) | 0.205 | 0.000072 |

The sensitivity analysis does not identify a tail size that provides useful unknown screening. The small change in test ranking should not be overinterpreted: there are only 36 unknown observations, and the sensitivity is on the same locked test period. Tail size must not be selected from these test metrics.

## Conformal comparison

| Method | Overall known empirical coverage | Mean class coverage | Worst class coverage | Mean set size | Empty sets (mean count) |
|---|---:|---:|---:|---:|---:|
| Marginal split conformal | 90.44% | 11.02% | 0.00% | 0.904 | 33,836 |
| Non-pooled Mondrian | 90.44% | 83.59% | 49.13% | 1.127 | 30,505 |

Marginal coverage is near its nominal 90% in aggregate but has zero empirical coverage for every non-benign known class in this test period. Mondrian prediction substantially improves the distribution of coverage across categories, but Analysis (63.52%) and Backdoor (49.13%) remain well below nominal. These are empirical measurements under temporal shift, not a guarantee of future-period coverage.

## Selective routing by class

Mean rates across seeds:

| Class | Support per run | Analyst escalation | Autonomous acceptance | Accuracy among automated rows |
|---|---:|---:|---:|---:|
| Benign | 322,809 | 25.71% | 74.29% | 100.00% |
| Analysis | 294 | 88.86% | 11.14% | 97.56% |
| Backdoor | 1,260 | 78.53% | 21.47% | 0.28% |
| DoS | 1,234 | 94.43% | 5.57% | 39.65% |
| Exploits | 10,803 | 96.74% | 3.26% | 70.05% |
| Fuzzers | 7,387 | 98.27% | 1.73% | 40.62% |
| Generic | 5,125 | 31.15% | 68.85% | 99.75% |
| Reconnaissance | 4,540 | 90.96% | 9.04% | 85.27% |
| Shellcode | 401 | 99.88% | 0.12% | 0% |
| Held-out Worms | 36 | 100% | 0% | n/a |

High overall accuracy among automated rows is dominated by benign and Generic traffic and conceals weak automation performance on several attack classes. Backdoor automated-subset accuracy is near zero; Shellcode automation is nearly absent. These class-specific trade-offs must accompany aggregate coverage and accuracy.

## Feature-schema interpretation

The executable contract and unit test define these as removal ablations: `baseline` retains all present configured groups, `set_a` excludes TTL, `set_b` excludes TTL and window, and `set_c` excludes TTL, window, and protocol. The earlier protocol text claiming additive groups has been corrected. See `feature_manifest_nf_unsw_nb15_v3.csv` for the v3 column inventory. The original manuscript's intended ablation remains unverified, so historical ablation claims should be checked against its source before publication.

## Reproducibility boundary

Recalculation from saved predictions exactly reproduced the OSR ranking/detection and routing metrics reported in run metadata. The prediction export lacks a separate closed-set top-1 class for OSR-rejected rows, so closed-set accuracy cannot be reconstructed from the prediction CSV alone. That limitation should be addressed in a future export version; the existing recorded metrics are tied to the saved run metadata and executable code.
