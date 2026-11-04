# NF-UNSW-NB15-v3 ↔ NF-CICIDS2018-v3 transfer and feature schemas

**Status:** Completed. This is the protocol's separate binary feature-ablation and bidirectional transfer experiment (RQ1); it does not evaluate multiclass OSR, conformal prediction, or selective routing.

## Design and provenance

- Dataset A: NF-UNSW-NB15-v3, 2,365,424 rows, SHA-256 `4ebb97bd74412d566137d95a6fc3ffd8f374f1cf8cfe204d007848e7a668f9b5`.
- Dataset B: NF-CICIDS2018-v3, 20,115,529 rows, SHA-256 `242a6971cc801eae621b1fc4d966db2cd0af9cc866805f36a6fc5d0058dfbb74`.
- A deterministic uniform sample without replacement selected 200,000 source rows and a separate, disjoint 200,000 target rows from each dataset. Samples were fixed across model seeds. Binary class counts are recorded in `experiment_metadata.json`.
- In each direction, the source sample was split chronologically into training and an in-domain future test subset using configured timestamp and complete-flow checks. The v3 source has valid start/end fields. The target sample is a fixed random sample across the target dataset's time span, not a temporally held-out target period.
- Four code-defined feature schemas (`baseline`, `set_a`, `set_b`, `set_c`), four seeds (42–45), and both transfer directions produced 32 run records. All four seeds produced identical metrics for each condition, so the observed across-seed SD is zero; the four seeds are not independent data or time replications.

## Zero-shot target results

Values are means across seeds; the seed-level values are identical in this run.

| Source → target | Schema | Target macro-F1 | Target balanced accuracy | Target MCC |
|---|---|---:|---:|---:|
| UNSW-v3 → CIC-IDS2018-v3 | baseline | 0.453 | 0.465 | -0.089 |
| UNSW-v3 → CIC-IDS2018-v3 | set_a | 0.389 | 0.466 | -0.046 |
| UNSW-v3 → CIC-IDS2018-v3 | set_b | 0.385 | 0.465 | -0.047 |
| UNSW-v3 → CIC-IDS2018-v3 | set_c | 0.393 | 0.500 | 0.000 |
| CIC-IDS2018-v3 → UNSW-v3 | baseline | 0.465 | 0.458 | -0.067 |
| CIC-IDS2018-v3 → UNSW-v3 | set_a | 0.475 | 0.478 | -0.049 |
| CIC-IDS2018-v3 → UNSW-v3 | set_b | 0.475 | 0.477 | -0.050 |
| CIC-IDS2018-v3 → UNSW-v3 | set_c | 0.402 | 0.356 | -0.145 |

The in-domain source-test scores were high for UNSW-v3 (macro-F1 0.998–1.000) and weak for CIC-IDS2018-v3 (macro-F1 0.477–0.481). In every zero-shot direction/schema condition, balanced accuracy was at or below 0.500 and MCC was near zero or negative. Thus, strong in-domain performance in one direction did not transfer to the other dataset on these fixed samples. No schema showed a consistent improvement across both directions and all metrics.

## Interpretation limits

These results support a bounded, sampled v3 transfer comparison, not full-population transfer estimates or temporal generalization to a future target period. The protocol tests binary labels only. Class imbalance, attack-taxonomy differences, and capture-domain differences are part of the observed transfer setting; the experiment does not isolate which caused the weak transfer. The third available v3 dataset, NF-ToN-IoT-v3, was not included because RQ1 specifies a two-dataset comparison. Adding it would be a separate, broader multi-domain experiment.

## Artifacts

- `artifacts_v3_transfer/cross_dataset/cross_dataset_per_seed.csv`
- `artifacts_v3_transfer/cross_dataset/cross_dataset_summary.csv`
- `artifacts_v3_transfer/cross_dataset/experiment_metadata.json`
- Configuration: `configs/v3_transfer.yaml`
