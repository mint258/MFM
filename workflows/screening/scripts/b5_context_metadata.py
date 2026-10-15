"""Post-run metadata only: contextual registry corrections do not change numeric ICC."""
import hashlib,json
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
p=ROOT/'b_quantum/analysis/B5_size_conditioned/report.json';data=json.loads(p.read_text())
if data['aligned_molecules']!=1441:raise ValueError('SOURCE_ATOM_GRAPH_ALIGNMENT_NOT_COMPLETE')
data['registry_metadata_revision']='V2 atom-level derived PM7 Coulson Fukui, explicit native/perturbed contexts'
data['registry_reference']=str(ROOT/'reports/label_registry_v2.json')
data['atom_level_fukui_alignment_correction']='All1441 source molecules already passed identical native atomic-number sequence and stored bondgraph/order checks in the completed B5 scan. Correcting the schema-level tag therefore removes no molecule/site and changes no numeric component or ICC; no additional QM or repeat analysis is needed.'
data['base_report_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
q=p.with_name('report_v2.json');q.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'B5_METADATA_CONTEXT_CLOSED','aligned_molecules':1441,'numeric_ICC_changed':False}))
