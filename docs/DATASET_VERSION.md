# Dataset-version decision

The prior draft used NF-UNSW-NB15-v2 and NF-CSE-CIC-IDS2018-v2 while describing a timestamp-based chronological split. That pairing is not a valid basis for a verified chronological experiment.

The University of Queensland's NIDS dataset catalog distinguishes the releases as follows:

- NetFlow v2 provides 43 extended NetFlow features.
- NetFlow v3 builds on v2 and adds temporal features, for 53 total features; the UQ page describes v3 as the only version incorporating temporal features.

Sources:

- [University of Queensland — ML-Based NIDS Datasets](https://staff.itee.uq.edu.au/marius/NIDS_datasets/), NetFlow v2/v3 descriptions and dataset inventories.
- [University of Queensland Cyber Research Centre — NIDS datasets](https://www.cyber.uq.edu.au/project/machine-learning-based-nids-datasets).
- [Temporal Analysis of NetFlow Datasets for NIDS](https://arxiv.org/abs/2503.04404), which discusses timestamps in the v3 datasets.

The corrected configuration therefore declares `release: UQ NetFlow v3` and points to `NF-UNSW-NB15-v3.csv`. The cross-dataset experiment is intended to use `NF-CSE-CIC-IDS2018-v3.csv` as the other dataset. The current UQ catalog lists 2,365,424 UNSW-v3 flows, including 158 Worms flows, and 20,115,529 CIC18-v3 flows. These are source-catalog reference counts, not assumptions enforced by the software; compare them with the exact downloaded files and their snapshot dates.

The local NF-UNSW-NB15-v3 file used in the completed temporal runs came in a UQ data bag identified as `f7546561558c07c5_NFV3DATA-A11964_A11964` (RAiD: https://hdl.handle.net/102.100.100/602564; bagging date in bag metadata: 2025-02-28). The CSV checksum is `4ebb97bd74412d566137d95a6fc3ffd8f374f1cf8cfe204d007848e7a668f9b5`, size 577,360,958 bytes, row count 2,365,424. The bagging date is not necessarily the date this project downloaded the file; the local acquisition date remains unrecorded.

`FLOW_START_MILLISECONDS` and `FLOW_END_MILLISECONDS` are the configured start/end timestamp fields, interpreted as milliseconds since the Unix epoch in the v3 temporal-feature documentation. The start field denotes the first-packet time and the end field the last-packet time for the flow. They are both required by the default configuration so complete flow intervals—not only their start times—can be checked against partition boundaries. The exact downloaded file must still be checked because mirrors and converted files can rename or transform fields. The field semantics should be cross-checked against the dataset documentation and the flow-exporter definition. The IETF IPFIX definition describes flow start and end timestamps as the time of the first and last packet, respectively: [RFC 7011](https://www.rfc-editor.org/rfc/rfc7011.html). A v3-specific field description uses the name `FLOW_START_MILLISECONDS`; the exact downloaded data file must still be inspected because names and formats can vary across mirrors or conversions. The command `inspect-schema` performs a small-sample check before the full-data audit.

## Consequences for the paper

The previous v2 counts, class distributions, feature-ablation values, transfer results, OSR values, conformal coverage, and SOC triage metrics are **not v3 results**. They must not be carried into a v3 manuscript. The v3 release has different row counts and includes additional temporal fields. All experiment tables must be regenerated from the exact v3 files whose checksums appear in the run metadata.
