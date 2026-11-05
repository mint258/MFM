"""Freeze four/eight bounded regression partitions; submit explicitly selected waves."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025');PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
p=argparse.ArgumentParser();p.add_argument('--action',choices=['freeze','submit'],required=True);p.add_argument('--tree',type=Path);p.add_argument('--label',required=True);p.add_argument('--partitions',type=int,choices=[4,8],default=8);p.add_argument('--indices',nargs='+',type=int);p.add_argument('--node');a=p.parse_args()
if not re.fullmatch('[A-Za-z0-9_]{1,64}',a.label):raise ValueError('Fresh simple label required')
plan=R/(a.label+'_plan.json')
def code(tree):
    result=subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True,timeout=45).strip()
    if subprocess.check_output(['git','-C',str(tree),'status','--porcelain'],timeout=45).strip():raise ValueError('Exact committed clean source required')
    return result
if a.action=='freeze':
    tree=a.tree.absolute()
    if not tree.is_relative_to(R.parents[1]) or plan.exists():raise ValueError('Fresh owned tree/plan required')
    sha=code(tree);runner=R/'run_regression_8130_v1.py';bindings=[]
    for i in range(a.partitions):
        target=R/(a.label+f'_part{i}_bindings.json')
        payload={'MODEL_V3_EXECUTION_SHA':sha,'MODEL_V3_CPU_EXECUTION_TREE':str(tree),'MODEL_V3_REGRESSION_RUNNER':str(runner),'MODEL_V3_REGRESSION_RUNNER_SHA':hashlib.sha256(runner.read_bytes()).hexdigest(),'MODEL_V3_PARTITION_COUNT':str(a.partitions),'MODEL_V3_PARTITION_INDEX':str(i)}
        with target.open('x') as f:json.dump(payload,f,indent=2);f.write('\n')
        bindings.append(str(target))
    with plan.open('x') as f:json.dump(dict(schema='model_v3_bounded_regression_plan_v3',tree=str(tree),code_sha=sha,partitions=a.partitions,planned_bindings=bindings,per_actual_parent_output_budget_bytes=2147483648,reason='Split growing full-suite artifacts into eight parents; existing failed outputs retained and no budget relaxed'),f,indent=2);f.write('\n')
    print(json.dumps(dict(status='FROZEN_NOT_SUBMITTED',plan=str(plan),code_sha=sha)))
else:
    data=json.loads(plan.read_text());tree=Path(data['tree'])
    if code(tree)!=data['code_sha']:raise ValueError('Source changed since plan')
    if not a.indices or len(set(a.indices))!=len(a.indices) or any(i not in range(data['partitions']) for i in a.indices):raise ValueError('Explicit unique partition indices required')
    wave=R/(a.label+'_wave_'+'_'.join(map(str,a.indices))+'.json')
    if wave.exists():raise FileExistsError('Wave already attempted; inspect preserved partial receipts')
    submissions=[]
    try:
        for i in a.indices:
            target=R/(a.label+f'_part{i}_submission.json')
            subprocess.run([PY,'-B',str(R/'submit_cpu_task_v2.py'),'--node',a.node,'--memory-MiB','32768','--script',str(R/'run_regression_partition_v1.sbatch'),'--bindings',data['planned_bindings'][i],'--output',str(target)],check=True)
            submissions.append(str(target))
    finally:
        with wave.open('x') as f:json.dump(dict(plan=str(plan),indices=a.indices,actual_submissions=submissions),f,indent=2);f.write('\n')