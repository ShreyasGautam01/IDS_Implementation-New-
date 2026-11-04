# Research readiness and execution plan

**Audit snapshot:** 2026-11-04  
**Workspace:** `D:\ids_implementation_rebuilt`  
**Audit branch:** `research/baseline-audit`  
**Uploaded experiment snapshot:** `codex/ids-project-upload` at `ee1ffd0` (preserved; do not rewrite)

This document separates observed facts from interpretations and open decisions. The locked four-seed pipeline was regenerated under the same data, split, and model settings solely to preserve pre-OSR class predictions in each export. This was a reproducibility refresh, not a new protocol or hyperparameter experiment.

## 1. Current project and repository state

### Verified facts

- The implementation in the uploaded snapshot identifies itself as package v2.0.0. The current local project includes follow-up changes for `uv`, timestamp-free binary transfer, and four-seed v3 experiment reporting.
- The prior GitHub commit `ee1ffd0` is a root commit on `codex/ids-project-upload`. This branch was pushed because the remote `main` already had an unrelated README commit. Audit work is published on the separate `research/baseline-audit` branch; neither existing branch was rewritten.
- The local older package `D:\ResearchPaper\IDS_Reliability_Benchmark_Rework_Package\ids_rework_v2` was inspected. Its README, method rework spec, and run manifest describe a separate Random Forest benchmark with 30 UNSW-NB15 features, seeds 42–46, and Experiments A–C; they contain no current v3 `baseline`/`set_a`/`set_b`/`set_c` feature-ablation specification. This package therefore does not resolve the current manuscript intent. The separate v2.1.2 archive/source remains unavailable.
- A legacy IEEE final package was found at `D:\ResearchPaper\IDS_Reliability_Benchmark_IEEE_Final_Package.zip`. Its manuscript is titled “Beyond Accuracy: Benchmarking Lightweight Reliability Signals for Intrusion Detection Under Unseen Attacks and Distribution Shift.” It describes a different study: a binary Random Forest benchmark on UNSW-NB15 and CIC-IDS2017, with raw confidence, tree disagreement, distance, conformal prediction, withheld-family tests, and cross-dataset shift. It is useful evidence of the project's earlier motivation, but it is not the current GBDT/Mahalanobis–Weibull v3 study specification.
- The legacy manuscript's stated gap is that closed-set accuracy does not tell operators when predictions are unreliable, and that lightweight reliability signals had not been compared across distinct failure modes (ordinary errors, withheld attack families, and cross-dataset shift) in a controlled benchmark. Its stated contribution and results must not be attributed to the current v3 experiment.
- A direct recent prior study, Arepalli et al., “Conformal prediction for network intrusion triage and analysis of unseen attack families,” was published on 2026-11-02. It evaluates conformal triage and family-wise probability/distance novelty on UNSW-NB15 and CIC-IDS2017 across 15 leave-one-family-out runs, and includes a separate weekday-based temporal CIC-IDS2017 analysis. This substantially overlaps the project's broad motivation and combined reliability scope; the current study must be positioned as a narrower NF-UNSW-NB15-v3 temporal-protocol extension, not as the first combined reliability/unknown-family evaluation.
- The NF-UNSW-NB15-v3 source file and four seed run folders are available locally. Raw datasets and large per-flow prediction outputs are excluded from the uploaded commit. The UQ bag metadata records `Bagging-Date: 2025-02-28`; local NTFS metadata currently records the outer bag folder created on 2026-11-03 14:39:26 UTC and the CSV last written at 14:39:33 UTC. These local timestamps may describe a copy or extraction event and do not certify the project download date, which remains unknown.

### Open

- The audit branch is confirmed on GitHub. Current `main` state has not been independently compared with this branch; do not merge into `main` as part of this audit.
- Compare the current snapshot with v2.1.2 only if that package becomes available.

## 2. Existing empirical evidence

### Verified facts

- Four runs exist for seeds 42–45, all with 353,889 test rows and the same future test period.
- The source data has 2,365,424 rows, SHA-256 `4ebb97bd74412d566137d95a6fc3ffd8f374f1cf8cfe204d007848e7a668f9b5`, and validated numeric start/end timestamp columns. There were 158 `Worms` rows overall; 122 before the test period were excluded and 36 remain in the test period.
- Reported four-seed known closed-set accuracy is 0.9645–0.9647; automated coverage 0.6856–0.6950; automated-subset accuracy 0.9975–0.9980.
- EVT rejects 1/36 unknown rows in each seed (2.78%; AUROC 0.216). Max-probability baseline AUROC is 0.970–0.974. The weak EVT result is a primary finding and must remain visible.
- Only two of nine nearest-class OSR regions use validation-fitted thresholds; seven use the predeclared no-rejection fallback due to insufficient validation support.
- Four-seed metrics are summarized in `artifacts_rebuilt/EXPERIMENT_RESULTS.md` and `artifacts_rebuilt/multi_seed_summary.csv`. Detailed run artifacts exist locally under timestamped seed directories. These detailed artifacts have not been uploaded.
- The four locked seeds were regenerated with the updated prediction exporter under `artifacts_reexport/`: `20261104T054008460933Z_seed42`, `20261104T054436806041Z_seed43`, `20261104T054840547477Z_seed44`, and `20261104T055304601532Z_seed45`. For every seed, global metrics, dataset-file metadata, and temporal-split metadata exactly match the original run. Each new prediction export has 353,889 rows and preserves the closed-set top-1 class before OSR. SHA-256 hashes and sizes for the new prediction/metadata files are recorded in `docs/REEXPORT_MANIFEST.csv`. The large local artifacts are intentionally excluded from GitHub; the code and reproduction notes are published.
- The protocol's binary cross-dataset experiment has completed on both the v2 pilot and the v3 UNSW/CIC-IDS2018 pair. The v2 pilot used 10,000-row disjoint samples and random source splits because timestamps were absent. The v3 comparison used 200,000-row disjoint source and target samples per dataset, chronological source evaluation, four schemas, four seeds, and both directions. Both are binary transfer studies, separate from the multiclass OSR/conformal/routing pipeline. The v3 results and limitations are in `docs/CROSS_DATASET_V3_EXPERIMENT.md`.
- The separate binary monotonicity sensitivity experiment has run on NF-UNSW-NB15-v3 (seed 42, `set_c`) and is recorded under `artifacts_reexport/monotonicity_binary/`, with interpretation in `docs/MONOTONICITY_V3_EXPERIMENT.md`. Its preprocessing path was corrected to apply the same non-finite handling and clipping used elsewhere before the run completed.

### Independent reproduction status

- Recomputed from all four `test_predictions.csv` files: unknown prevalence/count, EVT and max-probability AUROC/AUPR, OSR detection and known false-rejection rates, automated coverage and accepted-subset accuracy, and known-class conformal coverage. These match run metadata/comparison files at full floating-point precision for the checked metrics.
- Recomputed cross-run identity checks: same dataset checksum, config, boundaries, test class counts, test row count, and row-ordered true labels across all seeds.
- The original completed-run CSVs do not independently recover closed-set top-1 accuracy for OSR-rejected rows. In each regenerated export, closed-set accuracy recomputed directly from `true_class_id` and `closed_set_predicted_class_id` matches `run_metadata.json` exactly. The original run files remain unchanged.
- Detailed per-class conformal coverage, tail-size sensitivity, threshold fallbacks, and routing rates have been summarized in `docs/RELIABILITY_DIAGNOSTICS.md`.

### Figure production update (2026-11-04)

- Figure 1 is now generated at `docs/figures/figure1_classwise_reliability.svg`. It displays class-wise empirical Mondrian coverage and autonomous acceptance, test support, the nominal 90% reference, and sample-SD whiskers across the four classifier seeds on the same fixed split.
- Its source, structured summary data, and design specification are `scripts/plot_classwise_reliability.py`, `docs/figures/figure1_classwise_reliability_data.csv`, and `docs/figures/figure1_classwise_reliability_spec.json`. The manuscript caption is included in `docs/MANUSCRIPT_DRAFT.md`.
- Figures 1 and 2 were checked as valid SVG and previewed at their declared physical dimensions (178 × 140 mm and 178 × 90 mm). Native-render previews were inspected in color and grayscale. Figure 1 was revised after review to add the missing percentage-axis label and give the legend/notes more clearance; class supports, whiskers, chance/target references, and captions are visible without clipping. Marker shapes preserve distinction in grayscale. The outputs are editable vector drafts; venue-specific final formatting remains open.

## 3. Feature-schema audit and manuscript scope

`src/ids_reliability/features.py` excludes each group's configured features when that group is active for the schema. Current code behavior is:

| Schema | Code excludes | Code retains from configured groups | Protocol documentation says |
|---|---|---|---|
| `baseline` | none of TTL/window/protocol | all present groups | identifiers/timestamps removed; all groups retained |
| `set_a` | TTL | window + protocol | baseline plus TTL |
| `set_b` | TTL + window | protocol | set A plus window |
| `set_c` | TTL + window + protocol | none | set B plus protocol |

The disagreement was confirmed between code and earlier protocol wording. The code, tests, and corrected protocol now agree on the feature-removal interpretation shown in the table. The primary multiclass temporal reliability pipeline uses `set_c`; the separate binary transfer experiment compares all four schemas. These answer different questions and must not be conflated. Recovering an older manuscript's wording is unnecessary because this implementation and protocol define the executed comparison.

Seed 42 metadata confirms the main run used `set_c`, excluded the present `MIN_TTL`, `MAX_TTL`, `TCP_WIN_MAX_IN`, `TCP_WIN_MAX_OUT`, and protocol-group fields, and selected 38 numeric features. The main multiclass reliability results are observations for that exact feature set. Separately, the binary transfer comparison evaluates all four schemas as specified in `docs/CROSS_DATASET_V3_EXPERIMENT.md`.

The column-by-column manifest is `docs/feature_manifest_nf_unsw_nb15_v3.csv`. Under current code, the v3 data retain 47 predictors for `baseline`, 45 for `set_a`, 43 for `set_b`, and 38 for `set_c`. It identifies label fields, six identifier/time fields, all present configured group members, and the remaining numeric predictors. Configured but absent group members are `STTL`, `DTTL`, `INIT_WIN_BYTES_FWD`, and `INIT_WIN_BYTES_BWD`.

## 8. Independent prediction-artifact recomputation

Core OSR/routing metrics were recomputed from each saved `test_predictions.csv` using `true_class_id`, stored scores, stored OSR decisions, and stored routes. For seeds 42–45, recomputed EVT AUROC/AUPR, max-probability AUROC/AUPR, OSR detection/FPR, automation coverage, and automated-subset accuracy exactly match metadata (absolute difference 0 at displayed precision). Known-class conformal coverage recomputed from the saved class p-values is 0.9044, 0.9030, 0.9065, and 0.9037, matching the saved comparison outputs.

The original predictions do not contain a separate closed-set top-1 class for rows rejected by OSR; `predicted_class_id` is replaced with -1 on those rows. The refreshed predictions contain `closed_set_predicted_class_id` and `closed_set_predicted_class`. For each of seeds 42–45, closed-set accuracy computed directly from the CSV for known-class rows is exactly equal to the metadata value. The regenerated run metadata also matches the original global metrics, dataset-file metadata, and temporal split exactly.

An additional cross-run integrity check confirms all four runs have identical source hashes, config snapshots, boundaries, test class counts, row counts, and row-ordered true labels. OSR scores and rejection flags are exactly identical across seeds because the OSR method is deterministic and does not use the classifier's random seed. Thus the four seeds quantify model-seed variability for classification/conformal/routing, but do **not** provide repeated independent OSR replications. Report the OSR outcome once for this fixed split (with 36 unknown rows); do not imply zero uncertainty from its zero across-seed standard deviation.

## 4. Research gap and current research questions

The earlier IEEE manuscript frames the broad motivation as a gap between ordinary closed-set accuracy and the operational need to identify unreliable predictions, with reliability signals compared across ordinary errors, withheld attack families, and cross-dataset shift. More recent direct work by Arepalli et al. already evaluates conformal triage and unseen attack families across two datasets, including temporal evaluation. The broad gap has therefore been addressed and should not be claimed as novel.

For the current v3 experiment, the defensible question is how the implemented GBDT reliability pipeline (class-conditional Mahalanobis–Weibull OSR, conformal prediction, and selective routing) behaves on a fixed future-time split of the temporal NF-UNSW-NB15-v3 release, with complete-flow interval boundary checks and a rare withheld family. This is a narrow protocol- and dataset-specific extension to the recent direct study, not evidence of a general literature gap. It covers one dataset and one chronological test window, does not establish broad reliability across datasets or periods, and the weak EVT outcome must remain central.

Current evidence-bearing questions are:

1. How does the closed-set classifier perform on the fixed future period?
2. Does the class-conditional Mahalanobis/Weibull score identify a withheld family better than a max-probability baseline?
3. What empirical class-wise coverage and set sizes does non-pooled conformal prediction produce under this temporal split?
4. What coverage and errors result from the fixed selective-routing rule?

Cross-domain and monotonicity questions are separate experiments. The v3 bidirectional transfer/schema experiment answers the binary transfer question for fixed samples from the two v3 populations; it is not transfer evaluation of the multiclass reliability pipeline. The v3 monotonicity experiment is a one-seed binary sensitivity analysis and does not establish a guarantee for the multiclass pipeline or arbitrary adversarial robustness.

## 5. Immediate audit and implementation tasks

1. Compare the draft and protocol against Arepalli et al. (2026), Ahmed et al. (2026), and their closely related references; the temporal-shift audit is now cited as context, but the full literature comparison and narrow contribution statement still need review.
2. Treat this repository, including `docs/MANUSCRIPT_DRAFT.md`, the protocol, code, run metadata, and claim ledger, as the authoritative record of the current study. The other local packages are separate historical projects and are not required to continue the paper.
3. Use `docs/MANUSCRIPT_EVIDENCE_MAP.md` as the current claim-to-evidence map. Complete the focused related-work comparison against primary sources before submission; do not carry forward legacy numbers without exact provenance.
4. Decide whether more datasets or a newly predeclared test design are needed for broader claims. Any new design after current test inspection must be marked exploratory or separately confirmatory.
5. The locked four-seed rerun with the updated exporter is complete. Keep the regenerated output folders and their checksums available with the research archive if per-flow auditability is needed.
6. Cite the exact dataset release, UQ source record, and analyzed-file checksum. The project's acquisition date was not recorded and is not a blocker; do not infer it from the bagging date or filesystem times.
7. The protocol's v3 transfer and real-data monotonicity experiments are complete under the recorded configurations. If stronger seed-level uncertainty is required for monotonicity, add seeds as an explicitly labeled extension; the current result is a single-seed sensitivity analysis.
8. Decide from the selected venue and remaining results whether supplementary figures are needed; derive them only from locked outputs and preserve their plotted values alongside source CSVs.
9. Freeze paper tables and revise Methods, Results, interpretation, Discussion, and Limitations against the recorded artifacts; no external handoff folder is required.

## 6. Acceptance criteria before final paper results

- The primary paper names the executed `set_c` feature schema precisely and does not imply a comparative feature-ablation result. The code/docs/tests agree on the schema definition.
- Every reported number reproduces from committed code/config and identified run artifacts.
- Per-seed predictions and metadata agree on dataset checksum, fixed split, class counts, metric definitions, and score direction.
- Unknown-family results prominently state the 36-row denominator and do not imply robust OSR from this support.
- Conformal results are described as empirical under temporal shift unless exchangeability is justified.
- Cross-dataset claims are limited to the sampled binary v2 and v3 transfer experiments. Monotonicity claims are limited to the recorded v3 binary perturbation experiment and its tested feature directions.
- Limitations include the single dataset/test window, rare unknown support, insufficient validation strata, no independent EVT tail validation, and no deployment or workload evaluation.

## 7. Inputs still useful

- Evidence-backed Methods, Results, Discussion, Limitations, and provisional Abstract/Conclusion sections are drafted in `docs/MANUSCRIPT_DRAFT.md`. The focused literature review and venue formatting remain open.
- No additional project handoff or manuscript is needed: this repository is the current study record. Keep the four-schema comparison scoped to the separate binary transfer experiment; the multiclass reliability result is for `set_c` only.
- The completed v2/v3 transfer and v3 monotonicity outputs are separate protocol experiments; they must not be presented as one end-to-end temporal v3 reliability result.
- No additional dataset is required to complete the independent audit of the existing four runs. Additional v3 datasets/time periods would be required for broader external/temporal generalization claims.
