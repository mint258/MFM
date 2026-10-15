"""Metadata-only report tree inspection; does not read source records."""
import json
from pathlib import Path
old=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
r=json.loads((old/'reports/wp4_final_pilot_accounted/wp4_pilot_report.json').read_text())
print('REPORT_KEYS',list(r))
for key in r:
    if any(x in key for x in ('cost','project','account')):
        v=r[key];print(key,list(v) if isinstance(v,dict) else type(v).__name__)
p=json.loads((old/'wp4_polar_cost_v2/job_4512844_summary.json').read_text());print('PROBE_KEYS',list(p))
for k,v in p.items():
    if isinstance(v,list):print(k,len(v),list(v[0]) if v and isinstance(v[0],dict) else '')
