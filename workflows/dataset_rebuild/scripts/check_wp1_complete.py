"""Check the completed report before selecting the native trial population."""
import json
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
report=json.loads((ROOT/'wp1_results/screening_report.json').read_text())
if report['status']!='COMPLETE':
    raise RuntimeError('WP1 has explicit unresolved annotations; inspect report before native panel selection')
if report['population']['records']!=15879477:
    raise RuntimeError('Full physical-source population is incomplete')
for role,count in [('train',15709889),('full',161329),('routine',16000),('unassigned',8259)]:
    if report['roles'][role]['records']!=count:
        raise RuntimeError('Original membership population differs: '+role)
if any(report['membership_integrity'].values()):
    raise RuntimeError('Original membership integrity failed')
print(json.dumps({'status':'WP1_REPORT_COMPLETE','next':'select whole-molecule native pilot panel'}))
