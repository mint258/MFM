"""Consume only completed new-panel summaries in the actual evaluation allocation."""
import argparse,fcntl,json,os,subprocess
from pathlib import Path
from phychem_mfm.phase1.v3_reselection import c1_result,t1_result
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
C=R.parent/'runs/model_v31_20261105'
def read(path):return json.loads(Path(path).read_text())
def save_new(path,value):
 path=Path(path)
 if path.exists():return
 path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def atomic(path,value):
 path=Path(path);temp=path.with_name(path.name+'.reselection_next')
 temp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n');temp.replace(path)
def load_group(rows):
 summaries={};details=[]
 for row in rows:
  output=Path(row['output']);marker=output/'producer_complete.json'
  if not marker.is_file():return None
  m=read(marker)
  if m.get('panel')!='v3' or m.get('statistics_complete') is not True:return None
  overview=read(output/'summary.json')
  values={name:read(output/(name+'_summary.json')) for name in overview['means']}
  summaries.setdefault(row['arm'],{})[row['condition']]=values
  details.append(dict(stage=row['stage'],arm=row['arm'],condition=row['condition'],
   output=str(output),checkpoint=row['checkpoint'],
   scores={name:value['mean_normalized_improvement'] for name,value in values.items()}))
 return summaries,details
def page(path,result,stage):
 path=Path(path)
 if path.exists():return
 lines=['# '+stage+'：原子化能与SoM仅报告面板','',
  'Panel v3；七个分子任务等权，跨条件再等权；1000次分子组配对bootstrap，seed20261025。','',
  '| 组 | 条件 | R1 | R2 | R3 | R1z | R2z |','| --- | --- | ---: | ---: | ---: | ---: | ---: |']
 for row in result['rows']:
  values=[format(row['scores'][key],'.8f') if row['scores'].get(key) is not None else '—'
   for key in ('R1','R2','R3','R1z','R2z')]
  lines.append('| '+' | '.join([row['arm'],row['condition'],*values])+' |')
 if stage=='C1':lines+=['','选定：**'+result['decision']['selected']+'**。']
 if stage=='T1':
  lines+=['','原C1-0来源的T1暂定模块：**'+result['provisional_latent']+'**。',
   '与新C1来源相容：'+str(result['applicability_matches_new_C1'])+'；SoM只报告，不作否决。']
 comparisons=result.get('pairwise',[]) if stage=='C1' else [dict(name=key,**value) for key,value in result.get('comparisons',{}).items()]
 if comparisons:
  lines+=['','| 比较 | Δ | 95%CI |','| --- | ---: | --- |']
  for value in comparisons:
   label=value.get('name',value.get('A','')+' - '+value.get('B',''))
   lines.append('| '+label+' | '+format(value['delta'],'.8f')+' | '+str(value['ci95'])+' |')
 lines+=['','历史v2结果、标签源和检查点原样保留；本页不是模型/配方冻结。','']
 path.write_text('\n'.join(lines))
def release_if_compatible(plan,policy):
 cpath=Path(plan['new_results']['C1']);tpath=Path(plan['new_results']['T1'])
 if not(cpath.exists() and tpath.exists()):return
 c1,t1=read(cpath),read(tpath)
 compatible=c1['decision']['selected']=='C1-0' and t1['provisional_latent']=='none'
 policy['authority']['reselection_status']=('COMPLETE_MATCHES_CURRENT_RUNNING_ARCHITECTURE'
  if compatible else 'NEW_SELECTION_REQUIRES_DOWNSTREAM_REPLAN')
 policy['authority']['selected_C1_panel_v3']=c1['decision']['selected']
 policy['authority']['selected_latent_panel_v3']=t1['provisional_latent']
 atomic(R/'configs/dev_panel_v3.json',policy)
 atomic(R/'configs/model_v3/active_decision_sources.json',
  dict(panel='v3',C1=str(cpath),T1=str(tpath),compatible_with_current_runs=compatible,
   model_and_recipe_frozen=False))
 if not compatible:return
 journal=C/'MODEL_V3_RESELECTION_FOLLOWON_RELEASE_20261113.json'
 if journal.exists():return
 before={}
 for job in plan['held_followon_trainings']:
  raw=subprocess.check_output(['scontrol','show','job','-o',str(job)],text=True)
  if not('UserId=zixiao(1278)' in raw and 'JobState=PENDING' in raw and 'RunTime=00:00:00' in raw):
   raise ValueError('Preserve actual follow-on state; coordinator must resolve this release')
  before[str(job)]=raw
 record=dict(phase='VALIDATED_MATCHING_NEW_CHOICES_BEFORE_RELEASE',before=before,released=[])
 atomic(journal,record)
 for job in plan['held_followon_trainings']:
  subprocess.run(['scontrol','release',str(job)],check=True)
  record['released'].append(job);atomic(journal,record)
 record['phase']='MATCHING_FOLLOWON_JOBS_RELEASED';atomic(journal,record)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--plan',type=Path,required=True);p.add_argument('--evaluation-output',type=Path,required=True)
 args=p.parse_args();plan=read(args.plan)
 if os.getuid()!=1278:raise ValueError('Use the actual model owner')
 if (not any(Path(row['output'])==args.evaluation_output for row in plan['runs']) and str(args.evaluation_output)!=plan.get('T0_2_output')):return
 with (args.plan.parent/'new_panel_aggregation.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  policy=read(R/'configs/dev_panel_v3.json')
  if policy['authority']['retrospective_scope']!='REEVALUATE_C1_T0_T1':return
  for stage,count in (('C1',6),('T0',4),('T1',10)):
   rows=[row for row in plan['runs'] if row['stage']==stage]
   if len(rows)!=count:raise ValueError('The exact requested checkpoint matrix is required')
   target=Path(plan['new_results'][stage]);page_path=R/('docs/model_v3/M3_'+stage+'_PANEL_V3_RESULTS.md')
   if target.exists():
    page(page_path,read(target),stage);continue
   ready=load_group(rows)
   if ready is None:continue
   panels,details=ready
   if stage=='C1':result=c1_result({arm:{c:v['R3'] for c,v in values.items()} for arm,values in panels.items()})
   elif stage=='T0':
    if not plan.get('T0_2_output') or not (Path(plan['T0_2_output'])/'summary.json').is_file():continue
    result=dict(status='T0_COMPLETE_PANEL_V3',panel='v3',selection_use=False,
     T0_1_source=plan['new_results']['C1'],T0_2_status='COMPLETE',T0_2_summary=str(Path(plan['T0_2_output'])/'summary.json'))
   else:
    if not Path(plan['new_results']['C1']).exists():continue
    result=t1_result(panels)
    result['applicability_matches_new_C1']=read(plan['new_results']['C1'])['decision']['selected']=='C1-0'
   if stage=='T0':
    statistics=read(Path(plan['T0_2_output'])/'summary.json')
    details.extend(dict(stage='T0',arm='T0-2',condition=row['condition'],
     output=plan['T0_2_output'],scores={key:row[key] for key in ('R1','R2')})
     for row in statistics['rows'])
   result.update(rows=details,source_plan=str(args.plan),source_roles=['train','train_inner_validation'],
    downstream_TEST_read=False,model_and_recipe_frozen=False)
   save_new(target,result);page(page_path,result,stage)
  release_if_compatible(plan,policy)
if __name__=='__main__':main()
