# Research readiness and execution plan

**Audit snapshot:** 2026-11-04  
**Workspace:** `D:\ids_implementation_rebuilt`  
**Audit branch:** `research/baseline-audit`  
**Uploaded experiment snapshot:** `codex/ids-project-upload` at `ee1ffd0` (preserved; do not rewrite)

This document separates observed facts from interpretations and open decisions. No new model experiment was started during this baseline audit.

## 1. Current project and repository state

### Verified facts

- The implementation in the uploaded snapshot identifies itself as package v2.0.0. The current local project includes follow-up changes for `uv`, timestamp-free binary transfer, and four-seed v3 experiment reporting.
- The prior GitHub commit `ee1ffd0` is a root commit on `codex/ids-project-upload`. This branch was pushed because the remote `main` already had an unrelated README commit. Work for this audit is on a separate local branch.
- The local older package `D:\ResearchPaper\IDS_Reliability_Benchmark_Rework_Package\ids_rework_v2` exists. The handoff's separate v2.1.2 archive/source was not located during this audit and cannot currently be compared.
- A legacy IEEE final package was found at `D:\ResearchPaper\IDS_Reliability_Benchmark_IEEE_Final_Package.zip`. Its manuscript is titled “Beyond Accuracy: Benchmarking Lightweight Reliability Signals for Intrusion Detection Under Unseen Attacks and Distribution Shift.” It describes a different study: a binary Random Forest benchmark on UNSW-NB15 and CIC-IDS2017, with raw confidence, tree disagreement, distance, conformal prediction, withheld-family tests, and cross-dataset shift. It is useful evidence of the project's earlier motivation, but it is not the current GBDT/Mahalanobis–Weibull v3 study specification.
- The legacy manuscript's stated gap is that closed-set accuracy does not tell operators when predictions are unreliable, and that lightweight reliability signals had not been compared across distinct failure modes (ordinary errors, withheld attack families, and cross-dataset shift) in a controlled benchmark. Its stated contribution and results must not be attributed to the current v3 experiment.
- The NF-UNSW-NB15-v3 source file and four seed run folders are available locally. Raw datasets and large per-flow prediction outputs are excluded from the uploaded commit.

### Open

- Remote branch inventory and current `main` state still need confirmation through GitHub because direct `git ls-remote` was blocked by a local network/DNS failure. Do not merge into `main` as part of this audit.
- Compare the current snapshot with v2.1.2 only if that package becomes available.

## 2. Existing empirical evidence

### Verified facts

- Four runs exist for seeds 42–45, all with 353,889 test rows and the same future test period.
- The source data has 2,365,424 rows, SHA-256 `4ebb97bd74412d566137d95a6fc3ffd8f374f1cf8cfe204d007848e7a668f9b5`, and validated numeric start/end timestamp columns. There were 158 `Worms` rows overall; 122 before the test period were excluded and 36 remain in the test period.
- Reported four-seed known closed-set accuracy is 0.9645–0.9647; automated coverage 0.6856–0.6950; automated-subset accuracy 0.9975–0.9980.
- EVT rejects 1/36 unknown rows in each seed (2.78%; AUROC 0.216). Max-probability baseline AUROC is 0.970–0.974. The weak EVT result is a primary finding and must remain visible.
- Only two of nine nearest-class OSR regions use validation-fitted thresholds; seven use the predeclared no-rejection fallback due to insufficient validation support.
- Four-seed metrics are summarized in `artifacts_rebuilt/EXPERIMENT_RESULTS.md` and `artifacts_rebuilt/multi_seed_summary.csv`. Detailed run artifacts exist locally under timestamped seed directories. These detailed artifacts have not been uploaded.
- A bounded binary cross-dataset pilot ran on the two supplied v2 datasets, with 10,000-row disjoint source and target samples per dataset, four seeds (42–45), four code-defined removal schemas, and both directions. Because v2 has no configured flow timestamps, source evaluation uses the explicit stratified-random fallback. It is not temporal evidence. No real-data monotonicity experiment has been verified as run.

### Independent reproduction status

- Recomputed from all four `test_predictions.csv` files: unknown prevalence/count, EVT and max-probability AUROC/AUPR, OSR detection and known false-rejection rates, automated coverage and accepted-subset accuracy, and known-class conformal coverage. These match run metadata/comparison files at full floating-point precision for the checked metrics.
- Recomputed cross-run identity checks: same dataset checksum, config, boundaries, test class counts, test row count, and row-ordered true labels across all seeds.
- The completed-run prediction exports do not independently recover closed-set top-1 accuracy for OSR-rejected rows: they store `predicted_class_id=-1` without the pre-OSR class. The exporter has now been updated to include `closed_set_predicted_class_id` and its label in newly generated outputs. This code change does not retroactively repair the completed run artifacts; a rerun is needed to create a fully auditable prediction export.
- Detailed per-class conformal coverage, tail-size sensitivity, threshold fallbacks, and routing rates have been summarized in `docs/RELIABILITY_DIAGNOSTICS.md`.

## 3. Feature-ablation discrepancy (confirmed)

`src/ids_reliability/features.py` excludes each group's configured features when that group is active for the schema. Current code behavior is:

| Schema | Code excludes | Code retains from configured groups | Protocol documentation says |
|---|---|---|---|
| `baseline` | none of TTL/window/protocol | all present groups | identifiers/timestamps removed; all groups retained |
| `set_a` | TTL | window + protocol | baseline plus TTL |
| `set_b` | TTL + window | protocol | set A plus window |
| `set_c` | TTL + window + protocol | none | set B plus protocol |

The disagreement was confirmed between code and the earlier protocol wording. The code and unit test both support the feature-removal interpretation shown in the table, so that is now the authoritative implementation contract and the protocol text has been corrected. Whether this matches the original manuscript's intended ablation remains unverified without the source specification.

Seed 42 metadata confirms the main run used `set_c`, excluded the present `MIN_TTL`, `MAX_TTL`, `TCP_WIN_MAX_IN`, `TCP_WIN_MAX_OUT`, and protocol-group fields, and selected 38 numeric features. Thus, the model's features are known, but the manuscript's current description of `set_c` is wrong relative to the code. The main performance values remain observations for that exact 38-feature model; their intended ablation interpretation is unresolved. Cross-dataset schema comparisons also require corrected labels/interpretation before use.

The column-by-column manifest is `docs/feature_manifest_nf_unsw_nb15_v3.csv`. Under current code, the v3 data retain 47 predictors for `baseline`, 45 for `set_a`, 43 for `set_b`, and 38 for `set_c`. It identifies label fields, six identifier/time fields, all present configured group members, and the remaining numeric predictors. Configured but absent group members are `STTL`, `DTTL`, `INIT_WIN_BYTES_FWD`, and `INIT_WIN_BYTES_BWD`.

## 8. Independent prediction-artifact recomputation

Core OSR/routing metrics were recomputed from each saved `test_predictions.csv` using `true_class_id`, stored scores, stored OSR decisions, and stored routes. For seeds 42–45, recomputed EVT AUROC/AUPR, max-probability AUROC/AUPR, OSR detection/FPR, automation coverage, and automated-subset accuracy exactly match metadata (absolute difference 0 at displayed precision). Known-class conformal coverage recomputed from the saved class p-values is 0.9044, 0.9030, 0.9065, and 0.9037, matching the saved comparison outputs.

The predictions do not contain a separate closed-set top-1 class for rows rejected by OSR; `predicted_class_id` is replaced with -1 on those rows. Therefore closed-set accuracy cannot be independently recomputed solely from the current prediction CSVs. It can be checked by reproducing model inference from the data, config, and code, or the export schema can be improved in a new version. Do not describe unavailable independent recomputation as completed.

An additional cross-run integrity check confirms all four runs have identical source hashes, config snapshots, boundaries, test class counts, row counts, and row-ordered true labels. OSR scores and rejection flags are exactly identical across seeds because the OSR method is deterministic and does not use the classifier's random seed. Thus the four seeds quantify model-seed variability for classification/conformal/routing, but do **not** provide repeated independent OSR replications. Report the OSR outcome once for this fixed split (with 36 unknown rows); do not imply zero uncertainty from its zero across-seed standard deviation.

## 4. Research gap and current research questions

The earlier IEEE manuscript frames the broad motivation as a gap between ordinary closed-set accuracy and the operational need to identify unreliable predictions, with reliability signals compared across ordinary errors, withheld attack families, and cross-dataset shift. The current implementation is materially different, so that earlier paper is context—not an authoritative specification or validation of this study.

For the current v3 experiment, the defensible narrower gap/question is whether the implemented GBDT reliability pipeline (class-conditional Mahalanobis–Weibull OSR, conformal prediction, and selective routing) remains informative on a fixed future-time split with severe class imbalance and very sparse withheld-family support. The evidence covers one dataset and one chronological test window. It does not establish broad reliability across datasets or time periods, and the weak EVT outcome must be treated as a central negative result.

Current evidence-bearing questions are:

1. How does the closed-set classifier perform on the fixed future period?
2. Does the class-conditional Mahalanobis/Weibull score identify a withheld family better than a max-probability baseline?
3. What empirical class-wise coverage and set sizes does non-pooled conformal prediction produce under this temporal split?
4. What coverage and errors result from the fixed selective-routing rule?

Cross-domain and monotonicity questions are separate studies; the available v2 transfer pilot and synthetic tests do not answer them confirmatorily for v3.

## 5. Immediate audit and implementation tasks

1. Recover/locate the exact v2.1.2 archive/source and any current-study manuscript/specification if available; compare version/method definitions and confirm the manuscript's intended feature ablation. The legacy IEEE package above is not that specification.
2. Build a manuscript claim-to-evidence map once the paper draft is available. Do not carry forward legacy numbers without exact provenance.
3. Decide whether more datasets or a newly predeclared test design are needed for broader claims. Any new design after current test inspection must be marked exploratory or separately confirmatory.
4. Rerun the locked experiment with the updated exporter if artifact-only reproduction of closed-set metrics is required; the new output schema preserves pre-OSR classifier top-1 labels.
5. Record the actual dataset download/acquisition date and source citation in the provenance manifest; the UQ bagging date is not the project download date.
6. Run the real-data monotonicity experiment only if that research question remains in scope; otherwise explicitly omit empirical monotonicity results from the paper.
7. Once open provenance/specification inputs are resolved, freeze paper tables and draft methods, results, interpretation, discussion, and limitations from artifacts.

## 6. Acceptance criteria before final paper results

- Feature-schema definitions have one authoritative, versioned meaning, and the code/docs/tests agree.
- Every reported number reproduces from committed code/config and identified run artifacts.
- Per-seed predictions and metadata agree on dataset checksum, fixed split, class counts, metric definitions, and score direction.
- Unknown-family results prominently state the 36-row denominator and do not imply robust OSR from this support.
- Conformal results are described as empirical under temporal shift unless exchangeability is justified.
- Cross-dataset and monotonicity claims are included only if corresponding real-data runs exist and meet their declared protocols.
- Limitations include the single dataset/test window, rare unknown support, insufficient validation strata, no independent EVT tail validation, and no deployment or workload evaluation.

## 7. Inputs still useful

- The exact v2.1.2 ZIP/source snapshot or a location where it can be accessed, if available.
- The original paper draft or authoritative feature-ablation specification, if the relevant version is not in the older package.
- No additional dataset is required to complete the independent audit of the existing four runs. Additional v3 datasets/time periods would be required for broader external/temporal generalization claims.
