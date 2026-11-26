"""E1 full-cohort conformer counts; original published-rank/D5 loader only."""
import json,os,time
from pathlib import Path
from finetune_entry import CooperativeStop,set_actual_deadline
from finetune_statistics_entry import atomic_json,fingerprint
import shared_guard

def main():
 q=Path('/share/home/zixiao/descriptor_analysis/MFM_p_recipe')
 c=json.loads((q/'configs/p_recipe/fixed_20261115/round4/F2.json').read_text())
 output=q/'results/p_recipe/E1_actual_conformer_counts.json'
 state=Path('/share/home/zixiao/descriptor_analysis/runs/p_recipe_20261113/fixed_20261115/E1_conformer_count_cursor_20261124.json')
 if output.exists():raise ValueError('Closed E1 inventory must be reused')
 with CooperativeStop() as stop:
  set_actual_deadline(dict(cleanup_seconds=180,work_unit_seconds=120),stop)
  reg=json.loads((shared_guard.REGISTRY/'p-recipe.json').read_text())
  def guard():
   shared_guard.check_with_timeout('p-recipe','node_ram',4*2**30,node='compute-0-12')
   shared_guard.check_with_timeout('p-recipe','node_disk',16*2**20,path='/tmp',node='compute-0-12')
   shared_guard.check_with_timeout('p-recipe','shared_fs',sum(e['bytes'] for e in reg['entries'] if e['kind']=='shared_fs' and e.get('path')=='/share'),path='/share')
  guard()
  from phychem_mfm.phase1.p_recipe_data import train_indices
  from phychem_mfm.phase1.v31_loader import MFM4Dataset
  indices=train_indices(c)
  identity=dict(corpus=fingerprint(c['corpus']),source_root=c['root'],molecules=len(indices),order='fixed_random',D5_excluded_before_selection=True)
  s=json.loads(state.read_text()) if state.exists() else dict(identity=identity,cursor=0,sums=[0,0,0,0],histogram={})
  if s['identity']!=identity:raise ValueError('Inventory population changed')
  data=MFM4Dataset(c['root'],split='TRAIN',source='PM7',order='fixed_random',k=10,molecule_indices=indices,geometry_only=True)
  try:
   for cursor in range(s['cursor'],len(indices)):
    if cursor%4096==0:
     s['cursor']=cursor;atomic_json(state,s)
     if stop.requested or time.time()+120>=float(os.environ['P_MANAGED_STOP_NEW_UNITS_AT']):return 75
     if cursor%65536==0:guard();print(json.dumps(dict(cursor=cursor,total=len(indices))),flush=True)
    n=len(data.choices(int(indices[cursor])));data._molecules.clear()
    for j,k in enumerate([1,2,5,10]):s['sums'][j]+=min(k,n)
    s['histogram'][str(n)]=s['histogram'].get(str(n),0)+1
   s['cursor']=len(indices);atomic_json(state,s)
   rows=[dict(k=k,molecules=len(indices),allowed_conformers_total=s['sums'][j],actual_mean_k=s['sums'][j]/len(indices)) for j,k in enumerate([1,2,5,10])]
   result=dict(status='COMPLETE',job=os.environ['SLURM_JOB_ID'],identity=identity,rows=rows,available_conformer_histogram=s['histogram'],geometry_forward=False,training_performed=False,labels_refitted=False)
   atomic_json(output,result)
   with (q/'docs/p_recipe/daily/2026-11-24.md').open('a') as f:f.write('\nE1全量TRAIN实际平均k（D5先排除、固定随机秩、无补足）：'+', '.join('k='+str(r['k'])+': '+format(r['actual_mean_k'],'.8f') for r in rows)+'；'+str(len(indices))+'分子，原加载器一次流式统计，无新前向/拟合。\n')
   print(json.dumps(result),flush=True);return 0
  finally:data.close()
if __name__=='__main__':raise SystemExit(main())
