"""Root's metadata-only coordinator for the approved stereo supplement."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(value) + '\n')
    os.replace(temporary, path)


def wait_jobs(ids):
    active = {'RUNNING','PENDING','CONFIGURING','COMPLETING','SUSPENDED','REQUEUED','RESIZING'}
    while True:
        try:
            text = subprocess.check_output(['sacct','-X','-P','-n','-j',','.join(ids),
                '-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'], text=True)
            rows = {r[0]:r for line in text.splitlines() if (r:=line.split('|'))[0] in ids}
        except subprocess.CalledProcessError as exc:
            print('Native accounting temporarily unavailable', str(exc), flush=True)
            time.sleep(55)
            continue
        if set(rows) == set(ids) and not any(r[1].split()[0] in active for r in rows.values()):
            if any(r[1] != 'COMPLETED' or r[2] != '0:0' for r in rows.values()):
                raise RuntimeError('ACTUAL_JOB_NOT_C0: ' + json.dumps(rows))
            return list(rows.values())
        time.sleep(55)


def job_script(root, runtime, python, config_path, node, partition, cpus, tag, command):
    """Actual allocated-node disk preflight and an independent five-second guard."""
    return f'''#!/bin/bash
#SBATCH --partition={partition}
#SBATCH --nodelist={node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={cpus}
#SBATCH --nice=1000
#SBATCH --job-name=pubchem_stereo_{tag}
#SBATCH --output={root}/{tag}_%j.out
set -euo pipefail
unset SBATCH_MEM SBATCH_MEM_PER_NODE SBATCH_MEM_PER_CPU SBATCH_MEM_PER_GPU
export CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH=/gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v2/lib:${{LD_LIBRARY_PATH:-}}
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd {runtime}
{python} -B - <<'PY'
import json,os,pathlib,socket,subprocess
from workflows.expansion.window3_v2.disk_guard import inspect_filesystem
root=pathlib.Path({str(root)!r})
config=json.loads(pathlib.Path({str(config_path)!r}).read_text())
for args in [['findmnt','-T',str(root)],['df','-B1',str(root),'/'],['df','-Pi',str(root),'/']]:
    subprocess.run(args,check=True)
checks=[inspect_filesystem(dict(config['disk_checks'][0],planned_bytes=512*1024**3,planned_inodes=1000000)),inspect_filesystem(config['disk_checks'][1])]
print(json.dumps(dict(state='ACTUAL_NODE_PREFLIGHT',checks=checks)),flush=True)
if not all(v['safe'] for v in checks): raise RuntimeError('ACTUAL_NODE_DISK_CAPACITY_UNSAFE')
job=os.environ['SLURM_JOB_ID']
guard=dict(uid=os.getuid(),node=socket.gethostname().split('.')[0],job_id=job,checks=config['disk_checks'],interval_seconds=5,state_path=str(root/('guard_'+job+'.state.json')),reservation_scope='single shared512GiB stereo supplement budget')
(root/('guard_'+job+'.json')).write_text(json.dumps(guard)+'\\n')
(root/('tmp_'+job)).mkdir(exist_ok=True)
PY
export TMPDIR={root}/tmp_${{SLURM_JOB_ID}}
{python} -B -m workflows.expansion.window3_v2.disk_guard --config {root}/guard_${{SLURM_JOB_ID}}.json > {root}/guard_${{SLURM_JOB_ID}}.out 2>&1 &
stereo_guard_pid=$!
trap 'kill "$stereo_guard_pid" 2>/dev/null || true' EXIT
{python} -B -m {command} --config {config_path}
'''


def submit(path, script):
    path.write_text(script)
    job = subprocess.check_output(['sbatch','--parsable',str(path)],text=True).strip().split(';')[0]
    if not job.isdecimal():
        raise RuntimeError('NATIVE_SUBMISSION_JOB_ID_MISSING')
    print('SUBMITTED', job, str(path), flush=True)
    return job


def choose_nodes():
    text = subprocess.check_output(['sinfo','-N','-h','-o','%N|%P|%C'],text=True)
    nodes = {}
    for line in text.splitlines():
        name,partition,counts = line.split('|')
        idle = int(counts.split('/')[1])
        row = nodes.setdefault(name,dict(idle=idle,partitions=set()))
        row['partitions'].add(partition.rstrip('*'))
    result, used = [], set()
    roles = [(64,'compute-0-1'),(32,'compute-0-2'),(48,'compute-0-8'),(16,'sonmi1')]
    for cpus,fallback in roles:
        candidates = [(0 if 'cpu' in v['partitions'] else 1, 0 if n==fallback else 1,n)
                      for n,v in nodes.items() if n not in used and v['idle']>=cpus
                      and ('cpu' in v['partitions'] or 'all' in v['partitions'])]
        name = min(candidates)[2] if candidates else fallback
        if name in used:
            raise RuntimeError('CPU_NODE_ASSIGNMENT_CONFLICT')
        used.add(name)
        partition = 'cpu' if 'cpu' in nodes[name]['partitions'] else 'all'
        result.append((name,partition,cpus))
    print(json.dumps(dict(fresh_sinfo=text,chosen=result)),flush=True)
    return result


def native_rows(ids):
    raw=subprocess.check_output(['sacct','-X','-P','-n','-j',','.join(ids),
        '-o','JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS'],text=True)
    return {r[0]:r for line in raw.splitlines() if (r:=line.split('|'))[0] in ids}


def submit_once(root, tag, script, metadata):
    launch=root/(tag+'_launch.json')
    if launch.exists():return read(launch)
    intent=root/(tag+'_submission_pending.json')
    if intent.exists():raise RuntimeError('RECOVER_ACTUAL_SUBMISSION_BEFORE_RELAUNCH: '+str(intent))
    save(intent,metadata)
    result=dict(metadata,job_id=submit(root/(tag+'.sbatch'),script))
    save(launch,result)
    return result


def monitor_preparation_repairs(root,config,jobs):
    """Use each released shard's CPUs for only its zero-native preparation fixes."""
    plans=read(root/'full_plan.json')
    checks=read(config['prepare_config'])['disk_checks']
    active={'RUNNING','PENDING','CONFIGURING','COMPLETING','SUSPENDED','REQUEUED','RESIZING'}
    outcomes={}
    while len(outcomes)<len(jobs):
        ids=[j['job_id'] for j in jobs]
        for tag in ('prepare_repair','repair'):
            for i in range(len(jobs)):
                path=root/(tag+'_'+str(i)+'_launch.json')
                if path.exists():ids.append(read(path)['job_id'])
        try:rows=native_rows(ids)
        except subprocess.CalledProcessError:
            time.sleep(55);continue
        for job,row in rows.items():
            if row[1].split()[0] not in active and (row[1]!='COMPLETED' or row[2]!='0:0'):
                raise RuntimeError('ACTUAL_JOB_NOT_C0: '+json.dumps(row))
        for i,base in enumerate(jobs):
            if i in outcomes:continue
            if rows.get(base['job_id'],['',''])[1]!='COMPLETED':continue
            node,partition,_=plans[i]
            selector_tag='prepare_repair_'+str(i)
            selector_config=root/(selector_tag+'_config.json')
            selector_output=root/('repair_inputs_'+str(i))
            if not (root/(selector_tag+'_launch.json')).exists():
                value=dict(base_output=base['output'],output=str(selector_output),metadata_readers=8,disk_checks=checks)
                save(selector_config,value)
                script=job_script(root,config['runtime'],config['python'],selector_config,node,partition,4,
                                  selector_tag,'workflows.expansion.window3_v2.stereo_batch prepare-repair')
                submit_once(root,selector_tag,script,dict(config=str(selector_config),output=str(selector_output)))
                continue
            selector=read(root/(selector_tag+'_launch.json'))
            if rows.get(selector['job_id'],['',''])[1]!='COMPLETED':continue
            prepared_path=selector_output/'prepared.json'
            prepared=read(prepared_path)
            if not prepared['stereo_molecules']:
                outcomes[i]=dict(prepared=str(prepared_path),output=None)
                continue
            repair_tag='repair_'+str(i)
            repair_config=root/(repair_tag+'_config.json')
            output=root/repair_tag
            if not (root/(repair_tag+'_launch.json')).exists():
                repair_cpus=config.get('repair_max_workers',{}).get(str(i),base['cpus'])
                workers=min(repair_cpus,(prepared['stereo_molecules']+127)//128)
                value=dict(read(base['config']),source_manifest=str(prepared_path),output=str(output),
                    mode='stereo_preparation_repair',stereo_supplement=True,workers=workers,batch_size=128,
                    shard_count=1,shard_residues=[0],shard_index=0,disk_checks=checks,
                    stereo_phase='explicit_H_normalization_preparation_fix',molecule_timeout_seconds=3600)
                save(repair_config,value)
                script=job_script(root,config['runtime'],config['python'],repair_config,node,partition,workers,
                                  repair_tag,'workflows.expansion.window3_v2.producer')
                submit_once(root,repair_tag,script,dict(config=str(repair_config),output=str(output)))
                continue
            repair=read(root/(repair_tag+'_launch.json'))
            if rows.get(repair['job_id'],['',''])[1]!='COMPLETED':continue
            if read(output/'summary.json')['counts']['molecules']!=prepared['stereo_molecules']:
                raise ValueError('ZERO_NATIVE_PREPARATION_REPAIR_COUNT_DIFFERS')
            outcomes[i]=dict(prepared=str(prepared_path),output=str(output))
        save(root/'preparation_repair_progress.json',dict(closed_shards=sorted(outcomes),base_jobs=[j['job_id'] for j in jobs]))
        if len(outcomes)<len(jobs):time.sleep(55)
    all_ids=[j['job_id'] for j in jobs]
    for tag in ('prepare_repair','repair'):
        for i in range(len(jobs)):
            path=root/(tag+'_'+str(i)+'_launch.json')
            if path.exists():all_ids.append(read(path)['job_id'])
    accounting=wait_jobs(all_ids)
    save(root/'science_and_preparation_accounting.json',dict(rows=accounting,
        allocated_core_hours=sum(int(r[3])*int(r[4]) for r in accounting)/3600))
    return [outcomes[i] for i in range(len(jobs))]


def run(config):
    import fcntl
    root = Path(config['root'])
    lock = (root/'stereo_coordinator.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if config.get('validation_jobs'):
        wait_jobs(config['validation_jobs'])
    wait_jobs([config['prepare_job']])
    prepared = read(config['prepared'])
    if prepared['stereo_molecules'] != 1285342 or prepared['original_rows'] != 2500000:
        raise ValueError('FROZEN_STEREO_SCOPE_DIFFERS')
    launch = Path(config.get('full_launch_path', str(root/'full_launch.json')))
    if launch.exists():
        jobs = read(launch)
    else:
        old = read('/gfshome/alpha/pubchem_window3_v2_20261105/full_0_config.json')
        checks = read(config['prepare_config'])['disk_checks']
        plan = root/'full_plan.json'
        if plan.exists():
            nodes = read(plan)
        else:
            nodes = choose_nodes()
            save(plan,nodes)
        jobs = []
        for index,((node,partition,cpus),residues) in enumerate(zip(nodes,[[0,1,2,3],[4,5],[6,7,8],[9]])):
            slot = root/('full_'+str(index)+'_launch.json')
            if slot.exists():
                jobs.append(read(slot))
                continue
            intent = root/('full_'+str(index)+'_submission_pending.json')
            if intent.exists():
                raise RuntimeError('RECOVER_ACTUAL_SUBMISSION_BEFORE_RELAUNCH: '+str(intent))
            output = root/('full_'+str(index))
            value = dict(old,source_manifest=config['prepared'],output=str(output),
                mode='stereo_supplement',stereo_supplement=True,workers=cpus,batch_size=128,
                shard_count=10,shard_residues=residues,disk_checks=checks)
            path = root/('full_'+str(index)+'_config.json')
            save(path,value)
            script = job_script(root,config['runtime'],config['python'],path,node,partition,cpus,
                                'full_'+str(index),'workflows.expansion.window3_v2.producer')
            save(intent,dict(config=str(path),job_name='pubchem_stereo_full_'+str(index)))
            job = submit(root/('full_'+str(index)+'.sbatch'),script)
            jobs.append(dict(job_id=job,node=node,cpus=cpus,output=str(output),config=str(path)))
            # Persist every actual submission immediately; coordinator restart
            # must never submit a second producer against that output.
            save(slot,jobs[-1])
        save(launch,jobs)
    historical=native_rows(config.get('historical_job_ids',[])) if config.get('historical_job_ids') else {}
    if set(historical)!=set(config.get('historical_job_ids',[])):
        raise RuntimeError('HISTORICAL_ACCOUNTING_MISSING')
    if any(r[1].split()[0] in {'RUNNING','PENDING','CONFIGURING','COMPLETING','SUSPENDED'} for r in historical.values()):
        raise RuntimeError('HISTORICAL_JOB_STILL_ACTIVE')
    repairs=monitor_preparation_repairs(root,config,jobs) if config.get('preparation_repair_enabled') else []
    if historical:
        science=read(root/'science_and_preparation_accounting.json')
        science['historical_terminal_rows']=list(historical.values())
        science['allocated_core_hours']+=sum(int(r[3])*int(r[4]) for r in historical.values())/3600
        save(root/'science_and_preparation_accounting.json',science)
    rows = wait_jobs([j['job_id'] for j in jobs])
    summaries = [read(Path(j['output'])/'summary.json') for j in jobs]
    if sum(s['counts']['molecules'] for s in summaries) != 1285342:
        raise ValueError('STEREO_PRODUCER_POPULATION_DIFFERS')
    save(root/'full_accounting.json',dict(rows=rows,historical_terminal_rows=list(historical.values()),
        allocated_core_hours=sum(int(r[3])*int(r[4]) for r in rows+list(historical.values()))/3600))
    final_launch = root/'finalize_launch.json'
    if final_launch.exists():
        final_job = read(final_launch)['job_id']
    else:
        value = dict(prepared=config['prepared'],delivery=str(root/'delivery'),
                     producer_outputs=[j['output'] for j in jobs],
                     preparation_repairs=repairs,
                     disk_checks=read(config['prepare_config'])['disk_checks'])
        path=root/'finalize_config.json';save(path,value)
        final_job=submit(root/'finalize.sbatch',job_script(root,config['runtime'],config['python'],path,
                         'sonmi1','cpu',1,'finalize','workflows.expansion.window3_v2.stereo_batch finalize'))
        save(final_launch,dict(job_id=final_job))
    final_rows=wait_jobs([final_job])
    save(root/'finalize_accounting.json',dict(rows=final_rows))
    print('STEREO_DELIVERY_CLOSED_PENDING_3D_ONLY_COVERAGE_AND_REPORT',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    run(read(parser.parse_args().config))
