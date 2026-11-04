# Research Protocol v2.0.0

## 0. Dataset-version correction

The paper draft used NF-UNSW-NB15-v2 and NF-CSE-CIC-IDS2018-v2 while claiming chronological timestamp splitting. The University of Queensland dataset catalog states that NetFlow v2 contains 43 extended features, whereas v3 is the version incorporating temporal features and 53 extended features. The corrected temporal experiment therefore uses **NF-UNSW-NB15-v3** and **NF-CSE-CIC-IDS2018-v3**. The configured `FLOW_START_MILLISECONDS` field must be confirmed in the exact downloaded file. V2 results from the earlier draft are not directly comparable with v3 results and must not be relabelled as v3.

## 1. Research questions

**RQ1 — Feature ablation and transfer:** How do predefined identifier/header feature groups affect binary in-domain and bidirectional cross-dataset transfer performance on two aligned NetFlow datasets?

**RQ2 — Open-set screening:** How effectively does a class-conditional Mahalanobis/Weibull tail score rank held-out-family observations above known-class observations, and what is its known-class rejection operating point on a separate validation period?

**RQ3 — Class-conditional prediction sets:** How does non-pooled Mondrian split conformal prediction distribute empirical coverage across known attack categories under the chosen temporal test protocol?

**RQ4 — Selective routing:** What fraction of test flows satisfies a predeclared automation gate, and what are the class-specific risks among automated flows and the analyst queue?

**RQ5 — Binary monotonicity sensitivity (separate):** Under an explicitly synthetic volumetric augmentation and perturbation protocol, how do constrained and unconstrained binary classifiers differ in attack recall and benign false-positive rate?

## 2. Population and data lineage

For every dataset, record the source release/version, download URL, file name, SHA-256, file size, acquisition date, schema, row count, label counts, and timestamp interpretation. `run_metadata.json` stores the local file hash and structural audit. For the current v3 file, the exact local checksum, size, schema, and row counts are recorded, and its UQ data-bag identifier is available in the local package metadata; the acquisition/download date has not been independently recorded and must be added before publication.

The code removes only records satisfying the configured physical-invalidity rules: missing class label, negative numeric duration, or zero/missing total packet count when both packet-count columns exist. Each count is reported. The code does not deduplicate. A sampled exact-duplicate audit is reported as a sample statistic and is never extrapolated into a full-dataset duplicate count.

All non-finite feature values are converted to missing values. Median imputation is fitted on training rows only. No global feature statistic is computed from validation, calibration, or test records.

## 3. Labels

The benign label is encoded as class 0. Remaining non-benign, non-withheld attack categories are assigned stable sorted integer IDs beginning at 1. One configured family is withheld and encoded as -1. Its name and mapping are stored in run metadata.

Only the configured family is excluded from training in the main open-set experiment. If another known category has no training-period observations but appears later, the run fails. Researchers must then predefine a revised taxonomy or a separate temporal-novelty protocol rather than silently treating that class as learned.

## 4. Global temporal partition

The configured start timestamp column is parsed as UTC. Numeric timestamps use the explicit configured unit. Boundary quantiles are calculated from known-family records only, so the withheld family cannot influence the split cut points through its time distribution. Rows are partitioned by one global time boundary sequence over unique start timestamps, preserving equal timestamp groups. The withheld family is held out from boundary construction as well as all fitted stages.

Default row-mass targets are:

- proper training: first 55%;
- validation: next 15%;
- conformal calibration: next 15%;
- locked test: final 15%.

The realized partition sizes may differ because equal timestamps are never split. Boundaries and realized row counts are stored. The fractions are global and are not independently calculated per category. A configurable purge/embargo interval is applied around each cut point; the default is 60 seconds total width per boundary (30 seconds on each side). The interval must be justified against the dataset time resolution and flow/campaign duration. When a flow end-time field is configured, a retained flow must end within its assigned interval; flows whose start/end interval crosses a partition boundary are excluded and counted. The default config uses both `FLOW_START_MILLISECONDS` and `FLOW_END_MILLISECONDS`. If no trustworthy end-time field exists, the weaker start-only mode is explicitly recorded and must not be described as complete-flow separation. The embargo reduces near-boundary flow dependence but does not prove that longer attack campaigns, host sessions, or duplicate sessions cannot span periods. Embargo and cross-boundary exclusions are exported separately.

Known classes are assigned to the four windows based on timestamp. Withheld-family observations before the test window are excluded from this temporal open-set experiment and counted. Withheld-family observations in the final test window are evaluated as unknown. No unknown observations enter training, validation, or calibration.

The pipeline requires each known category to occur in the proper training window and requires at least the predeclared minimum number of held-out-family observations (default 20) in the final test window. This avoids presenting open-set ranking metrics from a handful of unknown observations. Otherwise it stops with an actionable error. It does not force an earlier attack observation into a later test period.

## 5. Preprocessing and classifier

The model input feature set is determined from column names and dtypes, not from target/test performance. All schemas remove labels, explicit identifiers, and timestamps. The tested implementation defines a nested **feature-removal ablation**:

- `baseline`: retain all present configured TTL, TCP window, and protocol groups;
- `set_a`: exclude TTL-related fields;
- `set_b`: exclude TTL and TCP window fields;
- `set_c`: exclude TTL, TCP window, and protocol enumeration/identifier fields.

This definition follows the executable contract in `features.py` and its unit test. It replaces the earlier, incorrect wording that described the sets as progressively adding groups. Whether this matches the original manuscript's intended comparison remains unverified; do not describe prior results as an additive feature study unless the original study specification confirms that interpretation.

Actual columns removed, present, absent, and retained are stored for every run. Any unexpected non-numeric predictor column causes an explicit error instead of silent deletion.

A single `HistGradientBoostingClassifier` is fitted on proper training data. Early stopping is disabled; hyperparameters are fixed in the versioned config. Its probabilities are not described as calibrated. No MLP is trained, no latent embedding is extracted, and no probability calibration method is implied.

## 6. Open-set detector

Within each known class, sort proper-training observations by their verified start timestamps. Use the earlier `geometry_fraction` portion to estimate the class mean and Ledoit-Wolf shrinkage covariance. Use the later, disjoint portion of proper-training observations to calculate Mahalanobis distances and fit a two-parameter Weibull distribution to the largest `tail_size` distances, fixing the location parameter at zero. At least five geometry and five tail-fit rows are required per class; otherwise the run stops. The detector never falls back to input row order. Store geometry/tail counts, fitted shape/scale, in-sample log-likelihood/AIC, and a descriptive empirical-CDF distance. The latter are diagnostics on the fitting tail, not independent goodness-of-fit tests.

For a new sample, calculate each class-tail Weibull CDF. The continuous unknown score is the minimum CDF across known classes: a sample is considered far into the fitted tail of its nearest known class when this score is large.

The discrete rejection threshold is fitted on the validation period. Assign each known validation observation to its nearest class tail, then choose a class-specific higher quantile targeting the configured known-class false-rejection rate. The observed rejection fraction on this same validation data is a threshold-fit diagnostic, not an independent estimate of future false-rejection performance; locked-test known-class rejection is reported separately. For a nearest-class group with fewer than 20 validation examples, set its threshold to 1.0 (do not OSR-reject that region) and report that fallback explicitly. No other class's threshold is borrowed.

This is an empirical tail-score detector. The code does not claim the fitted Weibull model is guaranteed by the Fisher–Tippett–Gnedenko theorem for the observed finite sample. A predeclared tail-size sensitivity analysis (default 25, 50, and 100) refits the tail distributions on the same disjoint tail-fit observations and recalibrates each variant on validation data. The configured primary tail size is fixed before test inspection; test performance is diagnostic and is not used to choose the primary size. Fitted-tail diagnostics are descriptive and do not prove tail-model adequacy.

## 7. Conformal prediction

Use the classifier's fixed probability outputs as a nonconformity score:

\[
s(x,y)=1-\hat p_y(x).
\]

Fit class-specific calibration score arrays on the calibration period. For each test sample and candidate class, use the non-randomized p-value

\[
p_y(x)=\frac{1+\#\{i:s_i^{(y)}\ge s(x,y)\}}{n_y+1}.
\]

Ties are counted with `>=`, making the p-value conservative. A label is included when `p_y(x) > alpha`. If a class has no calibration observations, set its candidate p-value to 1, conservatively including it in every prediction set. There is no KS clustering, no cross-class pooling, and no claim that such pooling preserves class-conditional validity.

The finite-sample class-conditional guarantee requires exchangeability between calibration and test observations within each class, conditional on the fixed trained predictor. As the main protocol uses a future-time test window, temporal shift may violate exchangeability. Therefore the result is reported as **empirical class-conditional coverage on the temporal test period** unless exchangeability is independently justified.

The evidence margin is the difference between the largest and second-largest class p-values. It is treated as a ranking statistic, not a calibrated probability of correctness.

## 8. Selective SOC routing

Let `Gamma(x)` be the conformal set and `I_OSR(x)` the OSR rejection flag. Automate exactly when the conformal set is a singleton containing the classifier top-1 label, OSR does not reject, and the evidence margin clears the predeclared threshold:

\[
\Gamma(x)=\{\arg\max_y\hat p_y(x)\}\;\land\;I_{OSR}(x)=0\;\land\;\delta_{em}(x)\ge\tau.
\]

All other observations go to analyst review, including empty sets, multi-label sets, and singleton sets that disagree with the classifier top-1 label. The class assigned to the flow is `Unknown_held_out` only when OSR rejects; conformal empty sets do not independently overwrite a known-class prediction. An unknown flow that passes the gate and receives a known prediction is counted as an autonomous error.

Report separately: OSR detection rate for unknowns, OSR false-rejection rate for knowns, total analyst escalation rate, unknown analyst escalation rate, unknown autonomous acceptance rate, automated subset accuracy, benign false-alarm rate, and per-class automation rates. AURC is explicitly a margin-ranked all-test risk–coverage statistic; it is not substituted for the actual gate's automated-subset risk.

## 9. Cross-dataset experiment

This is a separate binary task using the shared `Label` column. For each dataset, draw one deterministic source sample and one deterministic target sample, each bounded by the configured sample-size limit (default 200,000 rows). Reuse those same source and target samples across model seeds so seed variation is not confounded with resampling. For timestamped v3 sources, partition the selected source sample globally by its start timestamp and evaluate in-domain on its future test period. If the configured timestamp is absent, the implementation uses a fixed stratified-random source split; this is not a temporal experiment and must be reported separately. Fit preprocessing on source training rows only and evaluate zero-shot on the fixed target sample. Report the realized source/target sample sizes and class counts. This is a sampled transfer experiment, not a full-population transfer test.

Run all declared seeds. Report macro-F1, balanced accuracy, and MCC for each direction and seed. Do not infer success from relative improvement alone; report absolute performance and negative MCC values.

This experiment does not evaluate the full multiclass OSR/conformal/triage system.

## 10. Binary monotonicity experiment

This separate experiment fits two binary GBDTs: unconstrained and constrained with positive constraints only on configured volumetric fields. A configured fraction of benign training examples is duplicated with those fields increased by a fixed multiple of the proper-training IQR. Attack test rows are then perturbed by predefined multiples of the same IQR.

Report attack recall, benign false-positive rate, and macro-F1 at every perturbation level. In addition, empirically audit positive-class probability monotonicity by increasing each constrained field independently on deterministic held-out feature rows. This checks the configured monotonicity direction one feature at a time and does not prove arbitrary adversarial robustness.

This experiment demonstrates behaviour only under its explicit synthetic perturbation construction. It does not prove robustness to arbitrary adversarial manipulation, and it does not apply to the multiclass main pipeline.

## 11. Statistical reporting

- Distinguish standard deviation across seeds from standard deviation across classes.
- State exact per-experiment row counts and unknown prevalence with every AUROC/AUPR table.
- Use one fixed target sample across seeds when estimating model-seed variation.
- Report all seeds, not only a favorable seed.
- Do not call AUPR comparable across datasets with different unknown prevalence without discussing prevalence sensitivity.
- Preserve negative and null results.
- Never combine metrics from distinct data populations into one architecture-level claim without labelling the experimental population.
