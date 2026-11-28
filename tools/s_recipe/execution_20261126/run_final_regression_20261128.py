"""One final default CPU regression, only after all registered science closes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from cpu_execution_20261126 import execution_fields, native_record, stop_new_work_epoch
from storage_20261122 import CONTROL as C, REPO as R, write

owner=native_record()
read=lambda p:json.loads(Path(p).read_text())
progress=read(R/'results/s_recipe/execution_progress_20261127.json')
pairs=read(R/'results/s_recipe/full_finetune_contrasts_status.json')
curve=read(R/'results/s_recipe/budget_curve_status.json')
subset=read(R/'results/s_recipe/molecule_scaling.json')
report=R/'docs/s_recipe/FINAL_REPORT.md'
if (progress.get('completed_full_fit_count')!=192 or len(progress.get('selected_models',[]))!=192
        or len(list((R/'results/s_recipe/full_finetune').glob('*.json')))!=16
        or pairs.get('required_pairs')!=13 or pairs.get('completed_pairs')!=13 or pairs.get('pending_pairs')
        or curve.get('status')!='READOUTS_COMPLETE_FULLFT_COMPLETE' or subset.get('status')!='COMPLETE'
        or report.read_text().splitlines()[0]!='# S 家族实验报告'):
    raise ValueError('All original/A/B/C science and final report must actually close before the one full regression')
transport=R/'reproduction/linked_sources/docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py'
if not transport.is_file():raise ValueError('Bind the documented original native transport')
env=dict(os.environ,PHASE1_NATIVE_TRANSPORT_PATH=str(transport),CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
env['PYTHONPATH']=env.get('PYTHONPATH','')+os.pathsep+str(C)
commands=[('current_default_pytest',R/'current',[sys.executable,'-m','pytest','-q'],3600),
    ('S_full_pytest',R,[sys.executable,'-m','pytest','tools/s_recipe','-q'],1800),
    ('root_compatibility_unittest',R,[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],120),
    ('default_repository_check',R,[sys.executable,'tools/check_repository.py'],180)]
directory=Path(os.environ['S_NATIVE_CPU_RECORD']).parent
result=dict(status='RUNNING',scope='All default current tests, complete S tests, root compatibility, default repository check',
    gates=dict(successful_fits=192,selected_models=192,fullFT_points=16,registered_pairs=13,C1=curve['status'],C2=subset['status']),
    CUDA_VISIBLE_DEVICES='',native_transport=str(transport),steps=[],**execution_fields())
output=C/'final_regression_20261128.json'
for label,cwd,argv,estimated_seconds in commands:
    if time.time()+estimated_seconds>=stop_new_work_epoch():
        result.update(status='FAILED_INSUFFICIENT_REAL_FINISH_WINDOW',unstarted_step=label)
        write(output,result)
        raise SystemExit('Do not start a new test unit without its real cleanup margin')
    log=directory/(label+'.log')
    started=time.time()
    with log.open('wb') as stream:
        process=subprocess.run(argv,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,check=False)
    step=dict(step=label,cwd=str(cwd),argv=argv,started_at=started,ended_at=time.time(),
        exit_code=process.returncode,log=str(log))
    result['steps'].append(step)
    result['status']='RUNNING' if process.returncode==0 else 'FAILED'
    write(output,result)
    print(json.dumps(step),flush=True)
    if process.returncode!=0:
        write(R/'results/s_recipe/final_validation_20261128.json',result)
        raise SystemExit(process.returncode)
result['status']='COMPLETE'
write(output,result)
write(R/'results/s_recipe/final_validation_20261128.json',result)
print(json.dumps(dict(status='COMPLETE',steps=len(result['steps']),**execution_fields())),flush=True)
