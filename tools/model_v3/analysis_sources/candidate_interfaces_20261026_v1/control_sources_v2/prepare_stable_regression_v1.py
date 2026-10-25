"""Freeze full-suite assignments using real successful artifact sizes, not source length."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025');PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
p=argparse.ArgumentParser();p.add_argument('--action',choices=['freeze','submit'],required=True);p.add_argument('--tree',type=Path);p.add_argument('--label',required=True);p.add_argument('--baseline',default='wire_provider_postmerge_v1');p.add_argument('--new-module-reserve-MiB',type=int,default=512);p.add_argument('--indices',type=int,nargs='+');p.add_argument('--node');a=p.parse_args()
if not re.fullmatch('[A-Za-z0-9_]{1,64}',a.label) or not re.fullmatch('[A-Za-z0-9_]{1,64}',a.baseline):raise ValueError('Fresh simple labels required')
plan_path=R/(a.label+'_plan.json')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def exact_code(tree):
    sha=subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True,timeout=45).strip()
    if subprocess.check_output(['git','-C',str(tree),'status','--porcelain'],timeout=45).strip():raise ValueError('Clean exact committed branch required')
    return sha
if a.action=='freeze':
    if plan_path.exists() or not 16<=a.new_module_reserve_MiB<=1024:raise ValueError('Fresh plan and bounded declared new-module reserve required')
    tree=a.tree.absolute();sha=exact_code(tree);baseline_path=R/(a.baseline+'_complete.json');baseline=json.loads(baseline_path.read_text())
    if baseline['status']!='PASS' or len(baseline['job_ids'])!=8 or baseline['counts']['failures'] or baseline['counts']['errors']:raise ValueError('Actual successful complete eight-parent baseline required')
    current={str(p.relative_to(tree)):digest(p) for p in sorted((tree/'current/tests').glob('test_*.py'))};rows=[None]*8;seen={};baseline_refs=[]
    for job in baseline['job_ids']:
        summary_path=R/('integration_tests_'+job)/'summary.json';supervisor_path=R/('integration_supervisor_'+job+'.json');summary=json.loads(summary_path.read_text());sup=json.loads(supervisor_path.read_text())
        if summary['status']!='PASS' or summary['code_commit']!=baseline['code_commit'] or sup['status']!='COMPLETED' or sup['exit_code']!=0 or sup['first_failure'] is not None:raise ValueError('Exact successful baseline summary/supervisor required')
        i=summary['partition_index']
        if rows[i] is not None:raise ValueError('Duplicate baseline partition')
        observed=sup['last_total_bytes']
        if not 0<=observed<2*1024**3:raise ValueError('Successful baseline must fit existing2GiB')
        rows[i]={'index':i,'files':[],'baseline_last_observed_combined_bytes':observed,'new_reserved_bytes':0,'planned_bytes':observed,'baseline_job_id':job}
        for name,source_sha in summary['test_source_sha256'].items():
            if name in seen:raise ValueError('Overlapping baseline tests')
            seen[name]=(i,source_sha)
        baseline_refs.extend([{'path':str(path),'sha256':digest(path)} for path in (summary_path,supervisor_path)])
    if {name:value[1] for name,value in seen.items()}!=baseline['test_source_sha256']:raise ValueError('Baseline full source coverage differs from certificate')
    reserve=a.new_module_reserve_MiB*1024**2;limit=2*1024**3-64*1024**2;changed=[]
    for name,source_sha in current.items():
        if name in seen:
            i,oldsha=seen[name];rows[i]['files'].append(name)
            if oldsha!=source_sha:rows[i]['new_reserved_bytes']+=reserve;rows[i]['planned_bytes']+=reserve;changed.append(name)
    new=sorted(set(current)-set(seen))
    for name in new:
        eligible=[row for row in rows if row['planned_bytes']+reserve<=limit]
        if not eligible:raise ValueError('No measured partition headroom for new module; profile or split without relaxing2GiB')
        row=min(eligible,key=lambda x:(x['planned_bytes'],x['index']));row['files'].append(name);row['new_reserved_bytes']+=reserve;row['planned_bytes']+=reserve
    if any(not row['files'] or row['planned_bytes']>limit for row in rows):raise ValueError('Every actual partition needs source and measured+reserved headroom')
    for row in rows:row['files'].sort()
    runner=R/'run_regression_8130_v2.py';script=R/'run_regression_partition_v2.sbatch';assignment=R/(a.label+'_assignment.json')
    payload={'schema':'model_v3_stable_regression_plan_v1','code_sha':sha,'partitions':8,'all_test_file_sha256':current,'assignments':rows,'baseline_certificate':{'path':str(baseline_path),'sha256':digest(baseline_path)},'baseline_source_refs':baseline_refs,'new_test_files':new,'changed_test_files':changed,'removed_test_files':sorted(set(seen)-set(current)),'per_job_output_budget_bytes':2*1024**3,'per_new_or_changed_module_reserve_bytes':reserve,'old_successful_assignments_retained':True,'capacity_is_a_conservative_plan_not_peak_proof':True}
    with assignment.open('x') as f:json.dump(payload,f,indent=2);f.write('\n')
    bindings=[]
    for i in range(8):
        path=R/(a.label+f'_part{i}_bindings.json');data={'MODEL_V3_EXECUTION_SHA':sha,'MODEL_V3_CPU_EXECUTION_TREE':str(tree),'MODEL_V3_REGRESSION_RUNNER':str(runner),'MODEL_V3_REGRESSION_RUNNER_SHA':digest(runner),'MODEL_V3_PARTITION_COUNT':'8','MODEL_V3_PARTITION_INDEX':str(i),'MODEL_V3_PARTITION_PLAN':str(assignment),'MODEL_V3_PARTITION_PLAN_SHA':digest(assignment)}
        with path.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
        bindings.append(str(path))
    with plan_path.open('x') as f:json.dump({'tree':str(tree),'code_sha':sha,'partitions':8,'planned_bindings':bindings,'scheduler_script':str(script),'scheduler_script_sha256':digest(script),'assignment':str(assignment),'assignment_sha256':digest(assignment)},f,indent=2);f.write('\n')
    print(json.dumps({'status':'STORAGE_AWARE_PLAN_FROZEN','code_sha':sha,'new_modules':new,'planned_MiB':[round(row['planned_bytes']/1024**2,2) for row in rows]}))
else:
    data=json.loads(plan_path.read_text());tree=Path(data['tree'])
    if exact_code(tree)!=data['code_sha'] or digest(Path(data['assignment']))!=data['assignment_sha256'] or digest(Path(data['scheduler_script']))!=data['scheduler_script_sha256']:raise ValueError('Plan/source/runner bindings changed')
    if not a.indices or len(set(a.indices))!=len(a.indices) or any(i not in range(8) for i in a.indices):raise ValueError('Exact unique wave indices required')
    wave=R/(a.label+'_wave_'+'_'.join(map(str,a.indices))+'.json')
    if wave.exists():raise FileExistsError('Do not retry a recorded wave without inspecting exact partial submissions')
    submitted=[]
    try:
        for i in a.indices:
            receipt=R/(a.label+f'_part{i}_submission.json')
            subprocess.run([PY,'-B',str(R/'submit_cpu_task_v2.py'),'--node',a.node,'--memory-MiB','32768','--script',data['scheduler_script'],'--bindings',data['planned_bindings'][i],'--output',str(receipt)],check=True)
            submitted.append(str(receipt))
    finally:
        with wave.open('x') as f:json.dump({'plan':str(plan_path),'indices':a.indices,'actual_submissions':submitted},f,indent=2);f.write('\n')