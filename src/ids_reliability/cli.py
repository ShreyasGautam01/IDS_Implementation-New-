from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .data_audit import dataset_audit
from .io import load_table, sha256_file
from .pipeline import run_pipeline
from .monotonic import run_binary_monotonicity_experiment
from .transfer import run_cross_dataset_experiment
from .schema_inspector import inspect_dataset_schema, write_schema_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ids-reliability", description="Reproducible temporal IDS reliability experiments")
    parser.add_argument("--config", default="configs/default.yaml", help="Path to experiment YAML configuration")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect-schema", help="Read only a small sample and verify required schema/timestamp fields")
    inspect.add_argument("--dataset", default=None)
    inspect.add_argument("--sample-rows", type=int, default=1000)
    audit = sub.add_parser("audit", help="Audit dataset schema, labels, timestamps, and sampled duplicate rate")
    audit.add_argument("--dataset", default=None)
    run = sub.add_parser("run", help="Run the canonical multiclass OSR + conformal + triage pipeline")
    run.add_argument("--dataset", default=None)
    run.add_argument("--seed", type=int, default=None)
    cross = sub.add_parser("cross-dataset", help="Run separate binary bidirectional feature-ablation experiment")
    cross.add_argument("--dataset-a", required=True)
    cross.add_argument("--dataset-b", required=True)
    cross.add_argument("--seeds", nargs="+", type=int, default=None)
    mono = sub.add_parser("monotonicity", help="Run separate binary-only volumetric sensitivity experiment")
    mono.add_argument("--dataset", default=None)
    mono.add_argument("--seed", type=int, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    if args.command == "inspect-schema":
        path = args.dataset or config.dataset["path"]
        report = inspect_dataset_schema(path, config, sample_rows=args.sample_rows)
        destination = write_schema_report(report, Path(config.output["directory"]) / "schema_inspection.json")
        print(destination)
        if report["required_columns_missing"]:
            raise SystemExit(f"Missing configured columns: {report['required_columns_missing']}")
        if not report["temporal_ready_sample_check"]:
            raise SystemExit("Configured timestamp could not be validated in the sample; inspect field name and unit before running")
    elif args.command == "audit":
        path = args.dataset or config.dataset["path"]
        frame = load_table(path)
        report = dataset_audit(
            frame,
            str(config.dataset["label_column"]),
            str(config.dataset["timestamp_column"]),
            int(config.dataset.get("duplicate_audit_sample_size", 200_000)),
            int(config.dataset.get("duplicate_audit_sample_seed", 17)),
            str(config.dataset["end_timestamp_column"]) if config.dataset.get("end_timestamp_column") else None,
            str(config.dataset.get("numeric_timestamp_unit", "ms")),
            str(config.dataset.get("end_numeric_timestamp_unit", config.dataset.get("numeric_timestamp_unit", "ms"))),
        )
        report["dataset_file"] = {"path": str(Path(path).resolve()), "size_bytes": Path(path).stat().st_size, "sha256": sha256_file(path)}
        destination = Path(config.output["directory"]).expanduser().resolve() / "dataset_audit.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(destination)
    elif args.command == "run":
        result = run_pipeline(config, args.dataset, args.seed)
        print(result)
    elif args.command == "cross-dataset":
        result = run_cross_dataset_experiment(config, args.dataset_a, args.dataset_b, args.seeds)
        print(result)
    elif args.command == "monotonicity":
        result = run_binary_monotonicity_experiment(config, args.dataset, args.seed)
        print(result)


if __name__ == "__main__":
    main()
