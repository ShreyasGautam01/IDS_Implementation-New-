# Reproducibility Checklist

## Before running

- [ ] Use the UQ NetFlow v3 release for temporal experiments; record the exact source URL and file version. Do not treat v2 row order as timestamp order.
- [ ] Verify exact start and end timestamp columns, numeric units, clock basis, and whether the end field denotes the final packet time.
- [ ] Confirm that every retained flow interval can be assigned wholly to one partition; review boundary-crossing and embargo exclusions.
- [ ] Verify binary and multiclass label semantics and spelling of the held-out family.
- [ ] Verify every feature schema against the actual Parquet columns.
- [ ] Record the hardware, operating system, Python version, and installed package versions.
- [ ] Keep the YAML config under version control; do not edit it after test results are inspected.

## During data preparation

- [ ] Preserve raw files read-only.
- [ ] Save the dataset audit and SHA-256.
- [ ] Inspect all pointwise row removals and label counts.
- [ ] Inspect the duplicate sample report; do not reinterpret it as a full-dataset count.
- [ ] Inspect realized global time boundaries and class counts in each partition.
- [ ] Verify the held-out family did not influence boundary construction and appears in the locked test window.
- [ ] Review per-class geometry/tail-fit row counts, Weibull fitting diagnostics, and the predeclared tail-size sensitivity output.
- [ ] Verify no unknown-family rows entered train, validation, or conformal calibration.
- [ ] Verify that all known classes appear in training.

## During experiments

- [ ] Keep test data locked until every fitted component and threshold is fixed.
- [ ] Run all declared seeds.
- [ ] Reuse one fixed cross-domain target sample across seeds.
- [ ] Report OSR detection and known-class false rejection separately.
- [ ] Report conformal empirical coverage separately from its exchangeability assumptions.
- [ ] Report automation rates and accepted-subset accuracy by class.
- [ ] Preserve failed and negative results.

## Before publication

- [ ] Recompute all manuscript tables from machine-readable outputs.
- [ ] Check every result denominator and prevalence.
- [ ] Check all bibliographic metadata against publisher/proceedings records.
- [ ] Ensure each mathematical statement maps to the implemented function.
- [ ] Ensure each code path used to generate a table is named in the paper.
- [ ] Remove all unsupported claims listed in `CLAIM_LEDGER.md`.
