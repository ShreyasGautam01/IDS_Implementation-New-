"""Create a fixed-split AUROC comparison from the four-seed result summary."""
from __future__ import annotations
import csv, html, statistics, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with (ROOT/'docs'/'multi_seed_summary.csv').open(newline='',encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
if len(rows)!=4 or {int(r['seed']) for r in rows}!={42,43,44,45}:
    raise SystemExit('Expected the four locked seeds 42–45.')
evt=[float(r['evt_unknown_auroc']) for r in rows]
mp=[float(r['max_probability_unknown_auroc']) for r in rows]
if max(evt)-min(evt)>1e-12:
    raise SystemExit('EVT score is expected to be deterministic on this fixed split.')
data=[
 {'method':'Mahalanobis-Weibull (fixed split)','metric':'AUROC','estimate':statistics.mean(evt),'sample_sd':'','seed_count':4,'interpretation':'Identical deterministic score across four classifier seeds; no seed SD reported.'},
 {'method':'Maximum-probability score','metric':'AUROC','estimate':statistics.mean(mp),'sample_sd':statistics.stdev(mp),'seed_count':4,'interpretation':'Mean and sample SD across four classifier seeds on the same fixed split.'},
]
out=ROOT/'docs'/'figures'
with (out/'figure2_open_set_auroc_data.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=data[0].keys()); w.writeheader(); w.writerows(data)
spec={'claim':'On this test window, the Mahalanobis-Weibull score ranks withheld Worms flows below known flows overall, while maximum probability ranks them substantially higher.','visual_form':'horizontal dot-and-interval comparison','metric':'AUROC','unit':'unitless (0 to 1)','higher_is_better':True,'target_width_mm':178,'target_height_mm':90,'uncertainty':'Maximum-probability sample SD across four seeds on one fixed split; not a confidence interval. EVT score is deterministic and identical across seeds.','support':'36 withheld Worms flows; 353,853 known flows','output':'SVG vector figure'}
(out/'figure2_open_set_auroc_spec.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
W,H=672.76,340.16; x0,x1=200,568; ys=[161,220]
scale=lambda v:x0+(x1-x0)*v
fmt=lambda v:f'{v:.3f}'
esc=html.escape
parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="178mm" height="90mm" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">','<title id="title">Unknown-family ranking differs sharply by score</title>','<desc id="desc">AUROC comparison for 36 held-out Worms flows versus 353,853 known flows. Mahalanobis-Weibull AUROC is below chance at 0.216. Maximum-probability mean AUROC is about 0.971 across four seeds.</desc>','<rect width="100%" height="100%" fill="#FFFFFF"/>','<style>text{font-family:Arial,Helvetica,Inter,"DejaVu Sans",sans-serif;fill:#171717}.muted{fill:#5E6462}.grid{stroke:#E8E8E5;stroke-width:1}.axis{stroke:#AEB3B0;stroke-width:1}.risk{stroke:#C84B31;fill:#C84B31}.teal{stroke:#1F6F5F;fill:#1F6F5F}.whisker{stroke-width:1.4;stroke-linecap:round}.tick{font-size:11px}.label{font-size:11.3px}</style>','<text x="18" y="28" font-size="14" font-weight="600">Unknown-family ranking differs sharply by score</text>','<text class="muted" x="18" y="49" font-size="10.5">Held-out Worms (n=36) versus known traffic (n=353,853) in one locked future window.</text>']
for t in (0,.25,.5,.75,1):
    xx=scale(t); parts.append(f'<line class="grid" x1="{xx:.2f}" y1="134" x2="{xx:.2f}" y2="251"/>'); parts.append(f'<text class="tick muted" x="{xx:.2f}" y="271" text-anchor="middle">{t:.2f}</text>')
parts.append(f'<line x1="{scale(.5):.2f}" y1="134" x2="{scale(.5):.2f}" y2="251" stroke="#8D8D88" stroke-width="1.1" stroke-dasharray="4 3"/>')
parts.append(f'<text x="{scale(.5)+5:.2f}" y="128" class="muted" font-size="10">chance</text>')
labels=[data[0]['method'],'Maximum probability (mean across 4 seeds)']
for i,(row,label) in enumerate(zip(data,labels)):
    yy=ys[i]; v=float(row['estimate']); xx=scale(v)
    parts.append(f'<text class="label" x="18" y="{yy+4}">{esc(label)}</text>')
    sd=float(row['sample_sd']) if row['sample_sd']!='' else 0
    xa,xb=scale(max(0,v-sd)),scale(min(1,v+sd)); col='risk' if i==0 else 'teal'
    parts += [f'<line class="{col} whisker" x1="{xa:.2f}" y1="{yy}" x2="{xb:.2f}" y2="{yy}"/>',f'<line class="{col}" x1="{xa:.2f}" y1="{yy-4}" x2="{xa:.2f}" y2="{yy+4}"/>',f'<line class="{col}" x1="{xb:.2f}" y1="{yy-4}" x2="{xb:.2f}" y2="{yy+4}"/>',f'<circle class="{col}" cx="{xx:.2f}" cy="{yy}" r="4"/>']
    value=fmt(v) if not sd else f'{fmt(v)} ± {fmt(sd)}'
    parts.append(f'<text x="585" y="{yy+4}" font-size="11.2" font-weight="600">{value}</text>')
parts += ['<line class="axis" x1="200" y1="251" x2="568" y2="251"/>','<text class="muted" x="384" y="292" text-anchor="middle" font-size="10.5">AUROC (higher is better)</text>','<text class="muted" x="18" y="307" font-size="10">Whiskers show sample SD for maximum probability across seeds; they are not confidence intervals.</text>','<text class="muted" x="18" y="319" font-size="10">The Weibull score is identical across seeds on this split. AUROC below 0.5 indicates an inverted ranking.</text>','</svg>']
(out/'figure2_open_set_auroc.svg').write_text('\n'.join(parts)+'\n',encoding='utf-8')
print(data)

