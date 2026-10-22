"""Metadata-only prospective same-GPU A0/A4 characterization; does not select LR."""
import json,hashlib,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
def ref(path):
    p=Path(path);b=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
old=json.loads((R/'configs/performance_crossover_plan_v1.json').read_text())
assert old['warmup_steps_per_block']==4 and old['timed_steps_per_block']==10
old['crossover_order']=['A0','candidate','candidate','A0']
old.update(status='PRESELECTION_CHARACTERIZATION_ONLY_NO_COST_ESTIMATOR_OVERRIDE',candidate_group='A4',LR_selection_made_by_this_probe=False,
    actual_parent_snapshot=ref(R/'control/accounting_snapshots/completed_d3_profiles_A3_v1_v1.json'),required_actual_parent_ids=['4515542','4515607'],
    official_training_updates_added=0,parameter_updates=0,zero_learning_rate_optimizer_calls=56,
    source_reference=ref(R/'analysis/preselection_performance_crossover_v1.py'),requested_memory_GiB=32,host_RSS_cap_GiB=26)
for condition in ['A0','A4']:
    pointer=json.loads((R/'reports'/(condition+'_seed0_latest.json')).read_text());assert ref(pointer['path'])['sha256']==pointer['sha256']
    result=json.loads(Path(pointer['path']).read_text());assert result['status']=='D3_CONDITION_COMPLETE' and result['optimizer_updates']==4000
snapshot=json.loads(Path(old['actual_parent_snapshot']['path']).read_text())
assert all(snapshot['rows'][jid][:2]==['COMPLETED','0:0'] for jid in old['required_actual_parent_ids'])
with (R/'configs/preselection_performance_crossover_plan_v1.json').open('x') as f:json.dump(old,f,indent=2);f.write('\n')
print(json.dumps(dict(status=old['status'],candidate='A4',source_reference=old['source_reference'])))
