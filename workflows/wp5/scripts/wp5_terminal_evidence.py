"""Slurm allocation termination evidence, live or Root-captured. No compute or mutation."""
from __future__ import annotations
import getpass,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','TIMEOUT','BOOT_FAIL','DEADLINE','PREEMPTED'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def parse(stdout,job):
    rows=[]
    for line in stdout.splitlines():
        f=[part.strip() for part in line.split('|')]
        if len(f)>=3 and f[0]==str(job) and f[1]==getpass.getuser():rows.append({'job_id':f[0],'user':f[1],'state':f[2].split()[0]})
    return rows

def checked_terminal(job_id,source_run,evidence_path=None):
    job=str(job_id);source=Path(source_run).resolve();run_path=source/'run.json'
    run=json.loads(run_path.read_text());options=run['options']
    if str(options['job_id'])!=job or not source.is_relative_to(ROOT):raise ValueError('TERMINAL_SOURCE_JOB_OR_SCOPE_MISMATCH')
    if run_path.stat().st_uid!=os.getuid():raise ValueError('TERMINAL_SOURCE_UID_MISMATCH')
    base={'job_id':job,'node':run['node'],'user':getpass.getuser(),'run_json_path':str(run_path),'run_json_sha256':sha(run_path)}
    if evidence_path is not None:
        ep=Path(evidence_path).resolve()
        if not ep.is_relative_to(ROOT) or ep.stat().st_uid!=os.getuid():raise ValueError('TERMINAL_EVIDENCE_ROOT_OR_UID_MISMATCH')
        document=json.loads(ep.read_text())
        if document.get('schema')!='WP5_G6_TERMINAL_EVIDENCE_V1':raise ValueError('TERMINAL_EVIDENCE_SCHEMA')
        matches=[e for e in document['jobs'] if str(e['job_id'])==job]
        if len(matches)!=1:raise ValueError('TERMINAL_EVIDENCE_JOB_NOT_UNIQUE')
        entry=matches[0]
        for key in ('node','user','run_json_path','run_json_sha256'):
            if entry.get(key)!=base[key]:raise ValueError('TERMINAL_EVIDENCE_SOURCE_BINDING:'+key)
        state=str(entry['state']).split()[0]
        if state not in TERMINAL or entry.get('sacct_returncode')!=0 or not entry.get('sacct_stdout'):raise ValueError('TERMINAL_EVIDENCE_NO_SUCCESSFUL_TERMINAL_QUERY')
        return {**base,**entry,'evidence_origin':'ROOT_CAPTURED_SUCCESSFUL_SACCT','evidence_path':str(ep),'evidence_sha256':sha(ep)}
    command=['sacct','-X','-n','-P','-j',job,'--format=JobID,User,State']
    result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
    found=parse(result.stdout,job)
    evidence={**base,'sacct_argv':command,'sacct_returncode':result.returncode,'sacct_stdout':result.stdout,'sacct_stderr':result.stderr,'evidence_origin':'LIVE_SACCT'}
    if result.returncode or len(found)!=1 or found[0]['state'] not in TERMINAL:
        raise ValueError('SOURCE_JOB_NOT_CONFIRMED_TERMINAL:'+json.dumps(evidence,ensure_ascii=False))
    return {**evidence,'state':found[0]['state']}

def check():
    assert parse(' 123 | '+getpass.getuser()+' | FAILED |\n','123')[0]['state']=='FAILED'
    assert parse('123.batch|'+getpass.getuser()+'|COMPLETED|\n','123')==[]
    assert parse('123|other_user|FAILED|\n','123')==[]
    print('TERMINAL_PARSE_FIXTURES_PASS_NO_SACCT_NO_QM')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:check()
