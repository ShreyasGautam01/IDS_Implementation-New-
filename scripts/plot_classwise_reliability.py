"""Generate a class-wise reliability SVG from regenerated per-class run outputs."""
from __future__ import annotations
import csv
import html
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = sorted((ROOT / "artifacts_reexport").glob("*_seed*"))
OUT = ROOT / "docs" / "figures"
ORDER = ["Benign", "Analysis", "Backdoor", "DoS", "Exploits", "Fuzzers", "Generic", "Reconnaissance", "Shellcode", "Unknown_held_out"]
DISPLAY = {"Unknown_held_out": "Held-out Worms"}
FIELDS = ["class", "support", "mondrian_coverage_mean_pct", "mondrian_coverage_sd_pp", "automation_coverage_mean_pct", "automation_coverage_sd_pp", "automated_subset_accuracy_mean_pct", "automated_subset_accuracy_sd_pp", "seed_count"]
if len(RUNS) != 4:
    raise SystemExit(f"Expected four regenerated seed runs; found {len(RUNS)}")
run_data = {}
for run in RUNS:
    seed = int(run.name.rsplit("seed", 1)[1])
    with (run / "per_class_metrics.csv").open(newline="", encoding="utf-8") as stream:
        run_data[seed] = {row["class"]: row for row in csv.DictReader(stream)}
rows = []
for name in ORDER:
    seed_rows = [run_data[seed][name] for seed in sorted(run_data)]
    supports = {int(row["support"]) for row in seed_rows}
    if len(supports) != 1:
        raise SystemExit(f"Support differs across seeds for {name}: {supports}")
    result = {"class": name, "support": supports.pop(), "seed_count": 4}
    measures = {
        "mondrian_coverage": [float(r["empirical_conformal_coverage"]) * 100 for r in seed_rows if r["empirical_conformal_coverage"]],
        "automation_coverage": [float(r["autonomous_acceptance_rate"]) * 100 for r in seed_rows],
        "automated_subset_accuracy": [float(r["automated_subset_accuracy"]) * 100 for r in seed_rows if r["automated_subset_accuracy"]],
    }
    for metric, vals in measures.items():
        mean_key, sd_key = f"{metric}_mean_pct", f"{metric}_sd_pp"
        result[mean_key] = statistics.mean(vals) if vals else ""
        result[sd_key] = statistics.stdev(vals) if len(vals) > 1 else (0.0 if vals else "")
    rows.append(result)
with (OUT / "figure1_classwise_reliability_data.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
spec = {
    "claim": "Class-wise reliability differs substantially: empirical Mondrian coverage is low for some attack classes, while automation is concentrated in Benign and Generic flows.",
    "visual_form": "horizontal paired dot-and-interval plot",
    "metric": ["empirical Mondrian conformal coverage", "autonomous acceptance rate"],
    "unit": "percent",
    "category_order": ORDER,
    "target_width_mm": 178,
    "target_height_mm": 140,
    "uncertainty": "mean ± sample standard deviation across four classifier seeds on one fixed temporal split; not a confidence interval",
    "annotation_plan": ["nominal 90% Mondrian target reference", "per-class test support"],
    "output": "SVG vector figure",
}
(OUT / "figure1_classwise_reliability_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

# Final physical dimensions are 178 x 140 mm (viewBox uses CSS px at 96 dpi).
W, H = 672.76, 529.13
x0, x1 = 250.0, 642.0
y0, step = 146.0, 29.0
scale = lambda value: x0 + (x1 - x0) * value / 100.0
esc = lambda text: html.escape(str(text), quote=True)
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="178mm" height="140mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
 '<title id="title">Class-wise coverage and automation diverge</title>',
 '<desc id="desc">Paired point and sample-standard-deviation intervals for Mondrian conformal coverage and autonomous acceptance in each class. Supports are shown at left. The dashed line marks the 90 percent conformal target.</desc>',
 '<rect width="100%" height="100%" fill="#FFFFFF"/>',
 '<style>text{font-family:Arial,Helvetica,Inter,"DejaVu Sans",sans-serif;fill:#171717}.muted{fill:#5E6462}.grid{stroke:#E8E8E5;stroke-width:1}.axis{stroke:#AEB3B0;stroke-width:1}.teal{stroke:#1F6F5F;fill:#1F6F5F}.auto{stroke:#555B59;fill:#555B59}.whisker{stroke-width:1.35;stroke-linecap:round}.tick{font-size:11px}.label{font-size:11.3px}.support{font-size:10.8px}</style>',
 '<text x="18" y="27" font-size="14" font-weight="600">Class-wise coverage and automation diverge</text>',
 '<text class="muted" x="18" y="48" font-size="10.7">Points show four-seed means; whiskers show sample SD on the same fixed split.</text>',
 '<text class="muted" x="18" y="126" font-size="10">Class</text>',
 '<text class="muted" x="218" y="126" text-anchor="end" font-size="10">Test n</text>']
for tick in (0, 25, 50, 75, 100):
    x = scale(tick)
    parts.append(f'<line class="grid" x1="{x:.2f}" y1="{y0-9}" x2="{x:.2f}" y2="{y0+9*step+9}"/>')
    parts.append(f'<text class="tick muted" x="{x:.2f}" y="{y0+9*step+27}" text-anchor="middle">{tick}</text>')
parts.append(f'<line x1="{scale(90):.2f}" y1="{y0-9}" x2="{scale(90):.2f}" y2="{y0+9*step+9}" stroke="#9A681A" stroke-width="1.15" stroke-dasharray="4 3"/>')
parts.append(f'<text x="{scale(90)+4:.2f}" y="{y0-15}" fill="#805716" font-size="10">90% target</text>')
for i, row in enumerate(rows):
    yy = y0 + i * step
    name = DISPLAY.get(row["class"], row["class"])
    parts.append(f'<text class="label" x="18" y="{yy+4:.2f}">{esc(name)}</text>')
    parts.append(f'<text class="support" x="218" y="{yy+4:.2f}" text-anchor="end">{int(row["support"]):,}</text>')
    cov = row["mondrian_coverage_mean_pct"]
    if cov != "":
        mean, sd, cy = float(cov), float(row["mondrian_coverage_sd_pp"]), yy - 4.3
        left, right = scale(max(0, mean-sd)), scale(min(100, mean+sd))
        parts += [f'<line class="teal whisker" x1="{left:.2f}" y1="{cy:.2f}" x2="{right:.2f}" y2="{cy:.2f}"/>',
                  f'<line class="teal" x1="{left:.2f}" y1="{cy-3:.2f}" x2="{left:.2f}" y2="{cy+3:.2f}"/>',
                  f'<line class="teal" x1="{right:.2f}" y1="{cy-3:.2f}" x2="{right:.2f}" y2="{cy+3:.2f}"/>',
                  f'<circle class="teal" cx="{scale(mean):.2f}" cy="{cy:.2f}" r="3.2"/>']
    mean, sd, ay = float(row["automation_coverage_mean_pct"]), float(row["automation_coverage_sd_pp"]), yy + 4.3
    left, right = scale(max(0, mean-sd)), scale(min(100, mean+sd))
    parts += [f'<line class="auto whisker" x1="{left:.2f}" y1="{ay:.2f}" x2="{right:.2f}" y2="{ay:.2f}"/>',
              f'<line class="auto" x1="{left:.2f}" y1="{ay-3:.2f}" x2="{left:.2f}" y2="{ay+3:.2f}"/>',
              f'<line class="auto" x1="{right:.2f}" y1="{ay-3:.2f}" x2="{right:.2f}" y2="{ay+3:.2f}"/>',
              f'<rect class="auto" x="{scale(mean)-2.8:.2f}" y="{ay-2.8:.2f}" width="5.6" height="5.6"/>']
parts += [f'<line class="axis" x1="{x0}" y1="{y0+9*step+9}" x2="{x1}" y2="{y0+9*step+9}"/>',
 '<text class="muted" x="446" y="452" text-anchor="middle" font-size="10.2">Test flows (%)</text>',
 '<circle cx="260" cy="478" r="3.2" fill="#1F6F5F"/><text class="muted" x="269" y="482" font-size="10.2">Mondrian coverage</text>',
 '<rect x="408" y="475.2" width="5.6" height="5.6" fill="#555B59"/><text class="muted" x="420" y="482" font-size="10.2">Autonomous acceptance</text>',
 '<text class="muted" x="18" y="506" font-size="10">Held-out Worms has no conformal-coverage estimate; 36/36 were routed away from automation.</text>',
 '<text class="muted" x="18" y="519" font-size="10">Seed SD is not uncertainty across periods or datasets. Higher acceptance is not inherently better.</text>',
 '</svg>']
(OUT / "figure1_classwise_reliability.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")
print(f"Wrote data and SVG from seeds {sorted(run_data)}")

