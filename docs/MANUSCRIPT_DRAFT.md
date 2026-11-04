# Reliability of Multiclass Intrusion Detection Under a Fixed Temporal Holdout

**Draft status:** Evidence-backed core draft for Methods, Results, Discussion, and Limitations. The starter references below were checked against primary dataset, publisher, or journal sources; the broader literature review, exact dataset acquisition date, and target publication format remain open. Do not submit in this form.

## Abstract (provisional)

High closed-set classification accuracy does not by itself establish that an intrusion detection system can identify unreliable predictions. We evaluated a multiclass gradient-boosted IDS together with class-conditional Mahalanobis–Weibull open-set scoring, split-conformal prediction, and a selective routing rule on NF-UNSW-NB15-v3 under a chronological holdout. Four classifier seeds used the same temporal partitions and the same test period. The test set contained 353,889 flows, including only 36 withheld `Worms` flows. Known-class closed-set accuracy ranged from 96.45% to 96.47%, while automated coverage ranged from 68.56% to 69.50%; accuracy among automated flows ranged from 99.75% to 99.80%. The open-set score rejected one of 36 unknown flows and achieved AUROC 0.216, whereas the maximum-probability baseline achieved AUROC between 0.970 and 0.974. Mondrian conformal prediction produced 90.44% overall known-class empirical coverage, but coverage varied substantially by class. The results show that strong aggregate accuracy and selective accuracy can coexist with poor unknown-family detection and uneven class-wise reliability. Conclusions are limited to one dataset, one future test window, and sparse unknown support.

**Keywords:** network intrusion detection; temporal evaluation; open-set recognition; conformal prediction; selective classification; class imbalance

## 1. Introduction (working draft)

Closed-set classification treats labels as a fixed set, so a classifier alone cannot reject an input as belonging to an unseen class. OpenMax illustrates this problem and proposes an extreme-value/meta-recognition method for open-set image recognition; its representation and decision rule differ from the tabular score evaluated here [4]. For network intrusion detection, the NF-UNSW-NB15-v3 release adds temporal flow features to the NetFlow-based UNSW-NB15 corpus, and its associated temporal study examines how those features behave over time [1, 2]. The base UNSW-NB15 corpus was introduced as a benchmark combining normal traffic with contemporary synthesized attack activity [3].

Split conformal prediction offers finite-sample coverage under exchangeability. Temporal drift can violate that assumption, so temporal evaluation should report observed coverage without presenting the usual guarantee as established [5].

The broad combination of conformal triage and unseen-attack-family analysis is already represented in recent work. Arepalli et al. evaluated conformal triage and probability-/distance-based novelty scores across two intrusion benchmarks and 15 leave-one-family-out experiments, and also reported a weekday-based temporal analysis on CIC-IDS2017 [6]. Their study establishes that this general research direction is not new. Our narrower question is how class-conditional Mahalanobis–Weibull scoring, conformal prediction, and selective routing behave on the timestamped NF-UNSW-NB15-v3 corpus under strictly ordered training, validation, calibration, and test periods with complete-flow boundary checks and an embargo. This is a protocol- and dataset-specific empirical extension, not a claim that integrating reliability and unknown-family evaluation is unprecedented.

We withhold the `Worms` family from model fitting and compare the open-set score with a maximum-probability baseline. The limited support of that family in the future window (36 test flows) makes the experiment a narrow audit rather than a broad estimate of unknown-attack performance.

The study covers one dataset and one temporal window. It does not establish generalization across datasets, a guaranteed open-set detector, calibrated classifier probabilities, or deployment safety. The reported results include negative evidence: the fitted Weibull score performs poorly on the withheld family, and aggregate routing accuracy masks weak performance for some attack classes.

## 2. Methods

### 2.1 Relation to recent direct prior work

Arepalli et al. studied conformal analyst triage and unseen-family novelty detection on UNSW-NB15 and CIC-IDS2017, including 15 leave-one-attack-family-out experiments. They compared probability-space and nearest-neighbor scores, evaluated marginal and class-conditional coverage, and reported a separate temporal analysis using earlier CIC-IDS2017 weekdays for training and later weekdays for calibration/test [6]. The present study does not claim novelty for conformal IDS triage, family-wise novelty evaluation, or their combination.

The present evaluation uses the NF-UNSW-NB15-v3 NetFlow release and one fixed future-time holdout. Its four primary partitions are temporally ordered, calibration precedes test, full flow intervals are checked at partition boundaries, and a 60-second embargo is applied. The withheld `Worms` family has only 36 test observations. The primary novelty detector is class-conditional Mahalanobis–Weibull, compared here with maximum probability. These design differences support a limited replication/extension question about a timestamped NetFlow version and stricter temporal partitioning; they do not support a claim of a generally new reliability framework.

### 2.2 Dataset and label construction

We used the local `NF-UNSW-NB15-v3.csv` file identified in the run metadata by SHA-256 `4ebb97bd74412d566137d95a6fc3ffd8f374f1cf8cfe204d007848e7a668f9b5` and size 577,360,958 bytes. The analyzed file contains 2,365,424 flows [1]. The dataset acquisition date was not recorded and must be added from provenance records before publication.

`Benign` was encoded as class 0; eight known attack categories were encoded as classes 1–8. `Worms` was withheld from all fitted stages and encoded as unknown. The complete file contained 158 `Worms` flows. The time protocol excluded 122 that occurred before the final test window, leaving 36 unknown flows in the test set.

### 2.3 Temporal partitions and preprocessing

The start and end timestamps, `FLOW_START_MILLISECONDS` and `FLOW_END_MILLISECONDS`, were parsed as milliseconds since the Unix epoch and converted to UTC. Global temporal boundaries were derived from known-family records only. Equal start times were kept together. The target row proportions were 55% proper training, 15% validation, 15% conformal calibration, and 15% locked test. A 60-second total embargo was applied at each boundary, and flows crossing a partition boundary by their start/end interval were excluded.

The realized partitions contained 1,299,824 proper-training rows, 352,983 validation rows, 353,072 calibration rows, and 353,889 test rows. A further 5,534 rows were excluded around the temporal boundaries. The exact boundary timestamps and per-class counts are stored in the run metadata. These rules reduce near-boundary flow overlap but do not establish independence across longer campaigns, hosts, or sessions.

Non-finite feature values were treated as missing. Median imputation and a `RobustScaler` were fitted using proper-training rows only. The executed `set_c` schema selected 38 numeric predictors after removing identifiers/timestamps and the configured TTL, TCP-window, and protocol groups. This is a feature-removal schema in the executable code. The original manuscript's intended ablation direction is unverified, so we do not interpret the name `set_c` as evidence of a broader feature-group comparison.

### 2.4 Classifier

The classifier was `HistGradientBoostingClassifier` with 200 iterations, learning rate 0.08, at most 63 leaf nodes, minimum leaf size 20, balanced class weights, and no early stopping. We ran seeds 42, 43, 44, and 45 on the same data partitions. Classifier outputs were not probability-calibrated; they were used as model scores in downstream procedures.

### 2.5 Mahalanobis–Weibull open-set score

Within each known class, proper-training rows were ordered by timestamp. The earlier 70% of each class-specific sequence was used to estimate class geometry, and the later disjoint portion was used to fit a two-parameter Weibull distribution to the largest 50 Mahalanobis distances. Class geometry used a shrinkage covariance estimate. For a test flow, the continuous unknown score was the minimum of the fitted class-tail CDF values across known classes, so larger values indicate a flow deep in the fitted tail of its nearest known class. Tail sizes 25 and 100 were included in a predeclared sensitivity analysis.

Class-specific rejection thresholds were selected on the validation period to target a 5% known-class rejection rate. A nearest-class group required at least 20 validation examples; otherwise its threshold was set to 1.0, which disables rejection in that region. Only two of nine regions had fitted validation thresholds. Tail-fit diagnostics are descriptive and are not formal goodness-of-fit tests.

### 2.6 Conformal prediction and selective routing

We used non-randomized class-conditional split conformal prediction with miscoverage level \(\alpha=0.10\), calibrated on the separate calibration period. Candidate classes were not pooled. An unobserved calibration stratum would conservatively receive p-value 1. The classifier's probability outputs were used as nonconformity scores but are not claimed to be calibrated probabilities. Because calibration and test observations are separated in time, coverage is reported as empirical; exchangeability between these periods is not established.

A flow was routed for automation only when its conformal set contained exactly one class, that class matched the classifier's top-1 prediction, the open-set detector did not reject it, and the evidence margin was at least 0.25. All other flows were routed to analyst review. We report automation coverage, automated-subset accuracy, unknown rejection, class-wise conformal coverage, and per-class routing outcomes separately.

### 2.7 Reproducibility and comparisons

The four-seed pipeline was regenerated after updating the prediction export to retain the closed-set top-1 label before open-set rejection. The regenerated global metrics, dataset-file metadata, and temporal-split metadata match the original runs exactly for all four seeds. Closed-set accuracy recomputed from each regenerated prediction CSV also matches its metadata exactly. File sizes and SHA-256 checksums are in `docs/REEXPORT_MANIFEST.csv`; the large per-flow files remain in the local research archive and are not included in the repository.

## 3. Results

### 3.1 Closed-set classification and routing

All seeds evaluated the same 353,889 test flows, including 36 withheld-family examples. Known-class closed-set accuracy ranged from 96.45% to 96.47%. Automation coverage ranged from 68.56% to 69.50%; accuracy among automated flows ranged from 99.75% to 99.80%. Known-class OSR false rejection was 4.96% in each seed.

| Seed | Known closed-set accuracy | Automated coverage | Automated-subset accuracy | Unknowns rejected |
|---:|---:|---:|---:|---:|
| 42 | 96.47% | 69.15% | 99.76% | 1/36 |
| 43 | 96.45% | 69.50% | 99.80% | 1/36 |
| 44 | 96.46% | 69.25% | 99.75% | 1/36 |
| 45 | 96.47% | 68.56% | 99.78% | 1/36 |

Despite high automated-subset accuracy in aggregate, class-wise results were uneven. Benign and Generic traffic accounted for most automated flows. Backdoor automated-subset accuracy was 0.28%, and Shellcode automation was nearly absent (0.12% coverage; 0% accuracy among its automated examples). Thus, aggregate selective accuracy should not be read as uniform reliability across attack categories.

### 3.2 Withheld-family detection

The Weibull score rejected 1 of 36 `Worms` flows (2.78%) and had AUROC 0.216 on this fixed test split. The maximum-probability unknown score had AUROC between 0.970 and 0.974 across classifier seeds. The Weibull AUROC and rejection decision were identical across seeds because the open-set calculation is deterministic on this fixed split and does not depend on classifier seed. These repeated values are not independent OSR replications.

Changing the tail size did not improve detection: the 25-row fit rejected 0/36 unknowns (AUROC 0.220), the primary 50-row fit rejected 1/36 (AUROC 0.216), and the 100-row fit rejected 1/36 (AUROC 0.205). No tested tail size provided useful unknown-family screening on this period.

Only two of nine nearest-class regions had enough validation examples for fitted rejection thresholds. The remaining seven used the predeclared no-rejection fallback. This further limits the detector's ability to screen unfamiliar flows assigned to those regions.

### 3.3 Conformal coverage

Marginal split conformal had 90.44% overall known-class empirical coverage, close to the nominal 90%, but its mean class coverage was 11.02%; all non-benign known classes had zero observed coverage. Non-pooled Mondrian conformal also had 90.44% overall known-class coverage and improved mean class coverage to 83.59%. Its worst class, Backdoor, had 49.13% coverage; Analysis had 63.52%. The Mondrian mean prediction-set size was 1.127. These are observed outcomes under the selected future test period, not coverage guarantees under temporal change.

### 3.4 Cross-class routing pattern

Overall, 68.56%–69.50% of test rows passed the predeclared automation gate, with 99.75%–99.80% accuracy among automated rows. However, automation coverage ranged from 0.12% for Shellcode to 74.29% for benign flows, and class-wise automated accuracy ranged from 0% for Shellcode to 100% for benign traffic. Backdoor's 0.28% automated accuracy is a particularly clear failure hidden by the aggregate. Every `Worms` test flow was escalated, but only one was rejected by the OSR detector; escalation therefore must not be conflated with unknown detection.

## 4. Discussion

The experiment demonstrates a gap between closed-set classification and open-set reliability on this test window. The classifier achieved high accuracy on known test classes, but the class-conditional Weibull score performed substantially worse than the simple maximum-probability baseline for the 36 withheld-family flows. This negative comparison is the principal result for unknown-family screening. The small unknown denominator prevents a precise estimate of performance beyond this window, but does not justify presenting the current detector as effective.

Conformal results show why aggregate coverage is insufficient for imbalanced temporal data. Marginal coverage was near its nominal target when averaged over known observations, yet it was zero for every non-benign known class. The class-conditional method distributed coverage more evenly, but still fell well below nominal for Backdoor and Analysis. Temporal shift may violate the exchangeability condition needed for finite-sample guarantees; the observed coverage should therefore be interpreted descriptively.

The routing rule also produced a favorable aggregate automated-subset accuracy while providing little or unreliable automation for several attack classes. Most automated cases were benign or Generic, whereas Backdoor automation was almost always wrong and Shellcode was rarely automated. This shows that aggregate accuracy can be dominated by common classes and should be accompanied by class-specific support, coverage, and risk.

The results support a limited conclusion: on this one future window, the implemented pipeline's screening and routing behavior varied sharply by reliability task and class. They do not establish cross-dataset reliability, repeated temporal generalization, a general EVT failure, or production readiness. A second v2 cross-dataset pilot and synthetic monotonicity tests are separate exploratory evidence and are not pooled with this v3 result.

The close prior study by Arepalli et al. makes it especially important to state this scope accurately. Their family-wise novelty and conformal-triage analyses already cover the broader question of whether such reliability mechanisms can support intrusion triage. Our result is a distinct observation on a temporal NetFlow v3 file using a flow-interval-aware, ordered holdout: under that protocol, the selected Mahalanobis–Weibull score failed to rank the 36 withheld `Worms` flows above known traffic, while the maximum-probability score ranked them substantially better. This should be presented as a narrow replication/extension result, not a contradiction of their multi-family findings or a general refutation of EVT-based open-set methods.

## 5. Limitations

1. **Single corpus and window.** All main claims come from one dataset release and one chronological test interval. Performance on other periods or network environments is unknown.
2. **Rare unknown family.** Only 36 `Worms` flows appear in the test window. AUROC and rejection rate are therefore uncertain and family-specific; the experiment cannot establish general zero-day detection.
3. **Validation support.** Seven of nine OSR nearest-class regions could not receive fitted rejection thresholds under the minimum-support rule and used no-rejection fallbacks.
4. **Temporal dependence.** The embargo and complete-flow boundary checks reduce overlap around cut points, but do not rule out campaigns, host sessions, or duplicates spanning periods.
5. **Conformal exchangeability.** Calibration and test data are temporally separated. Exact split-conformal coverage assumptions have not been established under this temporal shift.
6. **Feature specification uncertainty.** The code and tests define removal ablations, but the intended direction in the current-study manuscript is unverified. The primary run uses `set_c`; its result should not be presented as a validated feature ablation.
7. **No deployment evaluation.** The study does not measure latency, analyst workload, operational safety, line rate, or performance under adaptive attackers.
8. **Limited replication scope.** Four classifier seeds share the same split and data. They characterize model-seed variation, not variation across time periods or environments. OSR scores are deterministic across those seeds.
9. **Provenance and literature.** The dataset acquisition date and a verified bibliography for the current study remain to be completed.
10. **Prior-work overlap.** A directly related 2026 paper already evaluates conformal triage and unseen-family detection across two datasets, including a temporal analysis. The current paper has a narrower contribution; a complete comparison with that paper and its cited work is required before making any novelty claim.

## 6. Conclusion (provisional)

On one fixed future-time test window from NF-UNSW-NB15-v3, high known-class accuracy and high accuracy among automatically accepted flows did not imply strong unknown-family screening or uniform class-wise reliability. The current Mahalanobis–Weibull score rejected only 1 of 36 withheld-family flows and ranked them worse than the maximum-probability baseline. Mondrian conformal prediction improved class-wise coverage relative to marginal conformal, but important attack classes remained well below nominal coverage. These findings are descriptive for this dataset and period; broader claims require additional time windows and external datasets.

## Items to resolve before submission

- Expand the verified starter bibliography into a balanced related-work review of NIDS reliability, open-set detection, and temporal evaluation; confirm the relevant literature before making any novelty claim.
- Recover the current-study manuscript or authoritative feature-ablation specification.
- Confirm the dataset acquisition date and complete citation/metadata.
- Add the full class-wise results table with uncertainty/support columns and produce publication-ready figures.
- Verify all descriptions against the final selected venue's reporting requirements.

## References (verified starter set; expand before submission)

1. University of Queensland, “ML-Based NIDS Datasets,” dataset catalogue and NF-UNSW-NB15-v3 entry, accessed 4 November 2026. [https://staff.itee.uq.edu.au/marius/NIDS_datasets/](https://staff.itee.uq.edu.au/marius/NIDS_datasets/)
2. M. Luay, S. Layeghy, N. Noorbin, M. Sarhan, G. Kulatilleke, N. Moustafa, and M. Portmann, “Time Matters: Temporal NetFlow Features for ML-Based Network Intrusion Detection,” *IEEE Access*, vol. 14, pp. 66899–66913, 2026, doi: [10.1109/ACCESS.2026.3688204](https://doi.org/10.1109/ACCESS.2026.3688204).
3. N. Moustafa and J. Slay, “UNSW-NB15: A comprehensive data set for network intrusion detection systems (UNSW-NB15 network data set),” in *2015 Military Communications and Information Systems Conference (MilCIS)*, 2015, pp. 1–6, doi: [10.1109/MilCIS.2015.7348942](https://doi.org/10.1109/MilCIS.2015.7348942).
4. A. Bendale and T. E. Boult, “Towards Open Set Deep Networks,” in *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR)*, 2016, pp. 1563–1572, doi: [10.1109/CVPR.2016.173](https://doi.org/10.1109/CVPR.2016.173).
5. R. F. Barber, E. J. Candès, A. Ramdas, and R. J. Tibshirani, “Conformal prediction beyond exchangeability,” *The Annals of Statistics*, vol. 51, no. 2, pp. 816–845, 2023, doi: [10.1214/23-AOS2276](https://doi.org/10.1214/23-AOS2276).
6. S. V. Arepalli, U. S. G. Irrinki, A. Morampudi, et al., “Conformal prediction for network intrusion triage and analysis of unseen attack families,” *Discover Informatics*, vol. 1, article 33, 2026, published 2 November 2026, doi: [10.1007/s44564-026-00033-y](https://doi.org/10.1007/s44564-026-00033-y).
