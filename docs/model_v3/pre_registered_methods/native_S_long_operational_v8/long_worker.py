"""One allocated native B job; no SSH, sbatch, quota writer or compute sacct."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from long_common import *
sys.dont_write_bytecode=True


def command(phase,frame,submission,job):
    layout=slot_layout(phase,frame['slot']);management=layout['management'];child=layout['child'];record=management/'supervisor.json'
    return [str(PYTHON),'-u','-B',str(RUNTIME/'tools/model_v3/run_supervised.py'),
        '--output-root',str(child),'--record',str(record),'--gpu-uuid',GPU,
        '--wall-seconds',str(SUPERVISOR_SECONDS),'--rss-limit-bytes',str(RSS),'--output-budget-bytes',str(OUTER),
        '--private-scratch-root','/tmp/mv3n_'+job,'--private-storage-budget-bytes',str(PRIVATE),'--',
        str(PYTHON),'-u','-B',str(HERE/'long_child.py'),'--phase',str(phase),
        '--submission',submission['path'],'--submission-sha256',submission['sha256'],
        '--runtime-contract',frame['runtime_contract']['path'],'--output',str(child),
        '--observations',str(record)+'.jsonl']


def snapshot(management,manifest,pins):
    directory=management/'source_snapshot';directory.mkdir()
    files=[]
    for name in [row['path'] for row in pins['files']]+['source_pins.json']:
        source=binding(HERE/name);raw=Path(source['path']).read_bytes()
        target=directory/name
        with target.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        copied=binding(target);require(copied['sha256']==source['sha256'],'Actual source snapshot differs')
        files.append(dict(relative_path=name,bytes=copied['bytes'],sha256=copied['sha256']))
    return write(directory/'MANIFEST.json',dict(schema='native_S_long_source_snapshot_v1',
        original_manifest=manifest,files=files,code_sha=CODE,prereg_sha=PUBLIC))


def metadata_QA(management,contract):
    files=list(HERE.glob('*.py'))+[HERE/'source_pins.json',Path(contract)]
    before={str(path):binding(path)['sha256'] for path in files}
    xml=management/'metadata_QA.xml'
    argv=[str(PYTHON),'-B','-m','pytest',str(HERE/'test_long_contract.py'),str(HERE/'test_quota_retry.py'),'-q','-p','no:cacheprovider',
        '-o','tmp_path_retention_policy=failed','--junitxml='+str(xml),
        '--basetemp='+str(management/'qa_tmp')]
    row=actual(argv,env=environment(cpu=True,contract=contract),timeout=45,check=False)
    raw=write(management/'metadata_QA_command.json',row)
    require(row['returncode']==0,'Necessary long-launch metadata QA failed; model not started')
    root=ET.parse(xml).getroot();suites=[root] if root.tag=='testsuite' else list(root.findall('testsuite'))
    counts={key:sum(int(suite.get(key,0)) for suite in suites) for key in ('tests','failures','errors','skipped')}
    after={str(path):binding(path)['sha256'] for path in files}
    require(counts==dict(tests=8,failures=0,errors=0,skipped=0) and before==after,
        'Exact8 zero-skip operational QA/source closure required (original4 plus quota4)')
    return write(management/'metadata_QA.json',dict(status='PASS_PENDING_SAME_MODEL_PARENT_TERMINAL',
        actual_command=raw,XML=binding(xml),counts=counts,sources_before=before,sources_after=after,
        independent_CPU_parent_C0_claimed=False,science_or_B_acceptance=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',type=Path,required=True);parser.add_argument('--submission',type=Path,required=True)
    parser.add_argument('--pins-sha256',required=True);args=parser.parse_args()
    started=time.monotonic();manifest,pins=verify(args.pins_sha256)
    import native_resources as resources
    job=os.environ['SLURM_JOB_ID'];process=resources.process_allocation(job)
    deadline=time.monotonic()+20
    while not args.submission.exists() and time.monotonic()<deadline:time.sleep(.1)
    submission=binding(args.submission);frame=read_ref(submission)
    require(frame['status']=='SUBMITTED' and frame['actual_sbatch_job_id']==job
        and frame['phase']==str(args.phase) and frame['package_manifest']==manifest,
        'Actual Root submission/job/source differs')
    argv=frame['actual_sbatch']['argv']
    require(frame['actual_sbatch']['returncode']==0 and frame['actual_sbatch']['stdout'].split(';',1)[0].strip()==job,
        'Exact actual sbatch receipt required')
    resources.validate_sbatch(argv)
    for option in ('--nodelist='+NODE,'--cpus-per-task=16','--time=02:00:00'):
        require(argv.count(option)==1,'Root actual Slurm resource argv differs')
    require(binding(frame['script']['path'])==frame['script']
        and frame['script']['sha256']==binding(HERE/'long_gpu.sbatch')['sha256'],'Copied batch source differs')
    from adopt_operational import verified_adoption
    adoption_ref,adoption=verified_adoption(args.phase,manifest)
    require(frame['operational_adoption']==adoption_ref and frame['method_publication']==adoption['method_publication'],
        'Worker source/publication/resource adoption differs')
    observations=resources.observe(worker=True,root_frame=frame)
    own=actual(['scontrol','show','job',job],check=False)
    if own['returncode']==0:
        require(('JobId='+job) in own['stdout'] and 'NumCPUs=16' in own['stdout'] and NODE in own['stdout'],
            'Own actual controller job differs')
    else:require(resources.unavailable(own),'Unknown own-job controller failure')
    layout=slot_layout(args.phase,frame['slot']);management=layout['management'];management.mkdir(mode=0o700,parents=True)
    snapshot_ref=snapshot(management,manifest,pins)
    qa=metadata_QA(management,frame['runtime_contract']['path'])
    require(time.monotonic()-started<70,'Preflight used Slurm finalization margin; no model launched')
    env=environment(cpu=True,contract=frame['runtime_contract']['path'])
    # Metadata-only namespace check; no Inputs construction or native scan.
    check=actual([PYTHON,'-B',V8/'candidate_probe.py','--contract',frame['runtime_contract']['path']],env=env,timeout=60)
    require(time.monotonic()-started<70,'Origin preflight used bounded Slurm margin')
    sys.path.insert(0,str(RUNTIME/'tools/model_v3'))
    import runtime_monitor,long_frames
    observed=long_frames.ledger_baseline(args.phase,runtime_monitor)
    observed.update(slot_root=str(layout['root']),job_id=job)
    baseline=write(management/'ledger_baseline.json',observed)
    supervisor=command(args.phase,frame,submission,job)
    write(management/'prelaunch.json',dict(schema='native_S_long_worker_prelaunch_v1',
        submission=submission,process=process,resource_observations=observations,own_controller_observation=own,
        origin_probe=check,metadata_QA=qa,source_snapshot=snapshot_ref,baseline=baseline,
        actual_planned_supervisor_argv=supervisor,model_started=False,
        accounting_scope='live_current_proc_NVML; known Slurm transport may reuse fresh bound Root frame'))
    completed=subprocess.run(supervisor,stdin=subprocess.DEVNULL,
        env=environment(contract=frame['runtime_contract']['path']))
    return completed.returncode


if __name__=='__main__':raise SystemExit(main())
