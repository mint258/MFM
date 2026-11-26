"""Close registered T1/T2 composition pairs and the original budget curve."""
import sys,os,pathlib,json,csv,io,time,fcntl,hashlib,runpy
import numpy as np
R=pathlib.Path('/share/home/zixiao/descriptor_analysis');Q=R/'MFM_p_recipe'
C=R/'runs/p_recipe_20261113/fixed_20261115'
B=pathlib.Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113/fixed_20261115/analysis_20261122')
sys.path.insert(0,str(Q/'tools/p_recipe'))
from finetune_statistics_entry import require_cpu_admission
from composition_statistics import summary
from composition_mean_statistics import hcomp_decision
import shared_guard
def write(path,value):
 tmp=path.with_name(path.name+'.new')
 tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');os.replace(tmp,path)
def main():
 admit=dict(node='compute-0-11',excluded_nodes=['compute-0-'+str(x) for x in [8,10,14,15,16,17,18]],reservation_ids=['P_F_remaining_CPU11_RAM','P_F_remaining_CPU11_tmp','registered_F1_F2_remaining'],output=str(B),output_mount='/lfshome',ram_peak_bytes=4*2**30,remaining_output_bytes=64*2**20)
 require_cpu_admission(admit)
 claim=json.loads((shared_guard.REGISTRY/'p-recipe.json').read_text())
 future=sum(x['bytes'] for x in claim['entries'] if x['kind']=='shared_fs' and x.get('path')=='/share')
 assert os.stat(C).st_dev==os.stat(shared_guard.disk_probe_target('/share')).st_dev
 shared_guard.check_with_timeout('p-recipe','shared_fs',future,path='/share')
 old=json.loads((B/'composition_mean_statistics/primary.json').read_text())
 t1=json.loads((B/'composition_T1_mean/primary.json').read_text())
 desc=json.loads((B/'composition_T1_descriptive/primary.json').read_text())
 assert t1['status']==desc['status']=='COMPLETE'
 assert [x['source'] for x in t1['rows']]==['T1_1M','T1_3M','T1_6M','T1_9M']
 with np.load(B/'composition_mean_statistics/new_paired_draws.npz',allow_pickle=False) as f: t2change=f['T2_9M_minus_1M'].copy()
 draws={}
 for key in ['T1_1M','T1_9M']:
  with np.load(t1['retained'][key]['base_draws'],allow_pickle=False) as f:draws[key]=f['CEV'].copy()
 assert all(x.shape==(1001,) and x.dtype==np.float64 for x in [t2change,*draws.values()])
 t1change=draws['T1_9M']-draws['T1_1M'];did=t2change-t1change
 joint=B/'composition_joint';joint.mkdir(exist_ok=True)
 with (joint/'new_paired_draws.npz').open('xb') as f:np.savez(f,T1_9M_minus_1M=t1change,T2_change_minus_T1_change=did)
 change=old['H_comp']['T2_9M_minus_1M']
 result=dict(status='COMPLETE',authority='USER_DIRECTIVE_20261122C',H_comp=dict(T2_9M_minus_1M=change,T1_9M_minus_1M=summary(t1change),T2_change_minus_T1_change=summary(did),decision=hcomp_decision(change,summary(did))),H_B4=old['H_B4'],decision_metric='mean(H) CEV only',atomic_metrics=['EEV'],mean_descriptive_metrics=['CEV_size','CVF','CVF_res','PR'],old_primaries_recomputed=False,new_bootstrap_weight_generations=0,retained_draws=str(joint/'new_paired_draws.npz'),mechanism_claim=False)
 write(joint/'primary.json',result)
 D=Q/'results/p_recipe/fixed_20261115/analysis_20261122'
 p=D/'H_comp.csv';raw=p.read_bytes();reader=csv.DictReader(io.StringIO(raw.decode()));previous=list(reader);fields=reader.fieldnames
 assert len(previous)==8 and not any(x['source'].startswith('T1_') for x in previous)
 extra=[];descs={x['source']:x for x in desc['rows']}
 for row in t1['rows']:
  dr=descs[row['source']];mean=dict(row)
  for k in ['CEV_size','CEV_size_CI_low','CEV_size_CI_high']:mean[k]=dr[k]
  extra.append({k:mean.get(k,'') for k in fields})
  atom={k:row[k] for k in ['source','samples','source_training_budget','layer','molecules','records']}
  atom.update(representation='atomic(H)')
  for k in ['EEV','EEV_CI_low','EEV_CI_high']:atom[k]=dr[k]
  extra.append({k:atom.get(k,'') for k in fields})
 buf=io.StringIO(newline='');csv.DictWriter(buf,fieldnames=fields).writerows(extra)
 updated=raw+buf.getvalue().encode();assert updated.startswith(raw)
 tmp=p.with_name(p.name+'.new');tmp.write_bytes(updated);os.replace(tmp,p)
 write(D/'H_comp_joint.json',result)
 write(D/'T1_mean_composition_primary.json',t1);write(D/'T1_22C_descriptive_primary.json',desc)
 ledger_path=R/'runs/p_recipe_20261113/study_execution.json';ledger=json.loads(ledger_path.read_text())
 for n,gpu,cpu in [(1,4539147,4539154),(4,4539148,4539155),(5,4539149,4539156),(6,4539150,4539157),(7,4539151,4539158),(8,4539152,4539159)]:
  run='fixed_20261115_budget_T1_'+str(n)+'M_L6_H0';s=json.loads((R/'runs/p_recipe_20261113/budget_curve_20261122'/run/'summary.json').read_text())
  assert s['status']=='COMPLETE' and s['statistics_complete'] and int(s['gpu_job_id'])==gpu and int(s['statistics_job_id'])==cpu
  ledger['runs'][run].update(state='COMPLETED',exit_code='0:0',native_closure_verified=True)
  ledger['cpu_statistics'][run].update(state='COMPLETED',exit_code='0:0',native_closure_verified=True)
 write(ledger_path,ledger)
 import budget_curve_report as report
 planpath=Q/'configs/p_recipe/fixed_20261115/confirmation/budget_curve_plan.json'
 prior_admit=report.admit_statistics;report.admit_statistics=lambda:require_cpu_admission(admit)
 try:budget=report.aggregate(planpath)
 finally:report.admit_statistics=prior_admit
 assert budget['status']=='COMPLETE' and budget['closed_readouts']==22 and len(budget['closed_original_9M_arms'])==5
 taskfile=Q/'results/p_recipe/fixed_20261115/confirmation/budget_curve_tasks.csv'
 raw=taskfile.read_bytes();reader=csv.DictReader(io.StringIO(raw.decode()));rows=list(reader);fields=reader.fieldnames
 keys={(x['arm'],int(x['samples']),x['readout'],x['task']) for x in rows};new=[]
 with (Q/'results/p_recipe/scores.csv').open() as stream:
  fcntl.flock(stream,fcntl.LOCK_SH);scores=list(csv.DictReader(stream));fcntl.flock(stream,fcntl.LOCK_UN)
 for n in [5,6,7,8]:
  run='fixed_20261115_budget_T1_'+str(n)+'M_L6_H0';added=[x for x in scores if x['run']==run and int(x['samples'])==n*1000000];assert len(added)==18
  for x in added:
   key=('T1',n*1000000,x['readout'],x['task'])
   if key not in keys:new.append({f:x[f] for f in fields});keys.add(key)
 buf=io.StringIO(newline='');csv.DictWriter(buf,fieldnames=fields).writerows(new)
 updated=raw+buf.getvalue().encode();assert updated.startswith(raw)
 assert len(list(csv.DictReader(io.StringIO(updated.decode()))))==486
 tmp=taskfile.with_name(taskfile.name+'.new');tmp.write_bytes(updated);os.replace(tmp,taskfile)
 doc=Q/'docs/p_recipe/BUDGET_CURVE_COMPLETE_20261123.md'
 doc.write_text('# 9M预算曲线：全部注册点完成\n\n'+report.report_section()+'\n')
 complete=dict(status='COMPLETE',H_comp=result['H_comp'],budget_readouts=22,budget_points=27,task_rows=486,old_primaries_recomputed=False,job=os.environ['SLURM_JOB_ID'])
 write(C/('composition_budget_joint_'+os.environ['SLURM_JOB_ID']+'.json'),complete)
 print(json.dumps(complete),flush=True)
if __name__=='__main__':main()
