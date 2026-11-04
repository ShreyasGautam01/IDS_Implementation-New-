# NetFlow v2 binary cross-dataset pilot

## Study status and scope

This is an **exploratory, bounded pilot**, not a confirmatory temporal-transfer experiment. The two local NF-UNSW-NB15-v2 and NF-CSE-CIC-IDS2018-v2 Parquet files contain no configured flow-start timestamps. The code therefore uses a fixed stratified-random 55/45 source train/test split, recorded as `stratified_random_no_timestamp_available`. It evaluates binary `Label`, not multiclass labels, and does not evaluate OSR, conformal prediction, or routing.

Each dataset was streamed once to draw disjoint 10,000-row source and 10,000-row target samples. The same samples were reused for seeds 42–45. Four schemas and both directions yield 32 model-seed records. Results are in the local `artifacts_v2_transfer/cross_dataset/` CSV/JSON artifacts; the raw data are not included here.

## Results

Target metrics below are means over the four seeds. MCC is included to show performance under imbalance; negative or near-zero values indicate weak transfer.

| Direction | Code-defined removal schema | Macro-F1 | Balanced accuracy | MCC |
|---|---|---:|---:|---:|
| UNSW-NB15 v2 → CSE-CIC-IDS2018 v2 | baseline (retain all configured groups) | 0.478 | 0.608 | 0.138 |
| UNSW-NB15 v2 → CSE-CIC-IDS2018 v2 | set_a (exclude TTL) | 0.369 | 0.335 | -0.224 |
| UNSW-NB15 v2 → CSE-CIC-IDS2018 v2 | set_b (exclude TTL + window) | 0.488 | 0.605 | 0.135 |
| UNSW-NB15 v2 → CSE-CIC-IDS2018 v2 | set_c (exclude TTL + window + protocol) | 0.392 | 0.386 | -0.150 |
| CSE-CIC-IDS2018 v2 → UNSW-NB15 v2 | baseline (retain all configured groups) | 0.493 | 0.498 | -0.007 |
| CSE-CIC-IDS2018 v2 → UNSW-NB15 v2 | set_a (exclude TTL) | 0.497 | 0.502 | 0.008 |
| CSE-CIC-IDS2018 v2 → UNSW-NB15 v2 | set_b (exclude TTL + window) | 0.493 | 0.497 | -0.010 |
| CSE-CIC-IDS2018 v2 → UNSW-NB15 v2 | set_c (exclude TTL + window + protocol) | 0.489 | 0.491 | -0.021 |

## Interpretation

The pilot shows weak and direction-dependent zero-shot transfer on these fixed samples. In the UNSW-to-CIC direction, two removal schemas have negative MCC. In the reverse direction, all schemas are near zero MCC and balanced accuracy is near 0.5. These results do not support a general transferability claim. Because the source split is random rather than chronological, they say nothing about future-time domain transfer. The 10,000-row samples limit precision and population coverage; do not present them as full-dataset estimates.

Feature labels above follow the executable code and unit-test contract. The original manuscript's intended ablation direction still needs confirmation from its source specification.
