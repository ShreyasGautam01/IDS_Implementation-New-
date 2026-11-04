# UQ NetFlow v3 temporal experiment: seed summary

## Protocol and data

- Dataset: UQ NetFlow NF-UNSW-NB15-v3 CSV; SHA-256 `4ebb97bd74412d566137d95a6fc3ffd8f374f1cf8cfe204d007848e7a668f9b5`.
- Four predeclared model seeds: 42, 43, 44, 45; each run uses the same global temporal boundaries and locked test period.
- Test period: 2015-02-18 09:08:45.757 UTC through 12:29:25.011 UTC; 353,889 flows, including 36 held-out Worms flows.
- The run enforces complete flow intervals and 60-second boundary embargoes. The dataset has 158 Worms rows total; 122 before the future test period were excluded from OSR fitting/evaluation.

## Results (mean ± sample SD across seeds)

| Metric | Mean | SD |
|---|---:|---:|
| Known closed-set accuracy | 0.964658 | 0.000098 |
| Automated coverage | 0.691165 | 0.003960 |
| Accuracy among automated rows | 0.997734 | 0.000222 |
| EVT unknown detection rate | 0.027778 | 0.000000 |
| EVT unknown AUROC | 0.215686 | 0.000000 |
| Max-probability baseline AUROC | 0.971288 | 0.001924 |
| EVT unknown AUPR | 0.000084 | 0.000000 |
| Max-probability baseline AUPR | 0.003235 | 0.001552 |
| Known-class OSR false-rejection rate | 0.049594 | 0.000000 |

## Interpretation and limitations

- All seeds share the exact same dataset hash, configuration, temporal boundaries, class counts, and row-ordered test labels. OSR scores, thresholds, rejection decisions, and tail-size sensitivity are identical across seeds because these steps are deterministic and do not depend on the classifier seed. The zero OSR seed SD is therefore **not** an uncertainty estimate or independent replication; describe OSR as one fixed-split evaluation with 36 unknown test flows.
- EVT rejected 1 of 36 held-out Worms flows in each seed (2.78% detection; AUROC 0.216). The max-probability baseline ranked unknowns much better (mean AUROC 0.971), though its AUPR remains low because unknown prevalence is about 0.010%.
- Only two of nine nearest-class OSR regions received validation-fitted thresholds; the remaining seven used the predeclared no-rejection threshold because their validation groups were too small.
- Conformal test coverage is empirical under temporal shift; exchangeability is not established. Only 36 unknown test rows make unknown metrics highly uncertain.
- These four seeds support reporting the observed results and limitations, not a claim of reliable open-set detection. Do not tune on the locked test period.

## Run artifacts

Per-seed detailed outputs remain in each timestamped `*_seed42` through `*_seed45` directory. `multi_seed_summary.csv` contains the concise per-seed metrics.
