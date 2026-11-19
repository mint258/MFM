"""Publish writer/closure metadata; never read an active SQLite from another node."""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time


def check_access(path):
    p=Path(path).parent/'access.json'
    if not p.exists():return None
    record=json.loads(p.read_text())
    if not record['cross_node_read_allowed'] and record['producer_node']!=socket.gethostname().split('.')[0]:
        raise RuntimeError('Shared SQLite writer is active on '+record['producer_node']+
            '; cross-node consumption waits for its actual closure, without a database copy')
    return record


def publish(path,record):
    path=Path(path)
    record=dict(record,observed_epoch=time.time(),publishing_uid=os.getuid())
    temp=path.with_name(path.name+'.pending_'+str(os.getpid()))
    with temp.open('x') as stream:
        json.dump(record,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temp.replace(path)


def completed_evidence(job):
    result=subprocess.run(['scontrol','show','job',str(job)],capture_output=True,text=True,timeout=30)
    if result.returncode==0:
        values=dict(re.findall(r'\b(JobId|JobState|ExitCode|UserId|NodeList)=([^\s]+)',result.stdout))
        if values.get('JobId')!=str(job) or values.get('JobState')!='COMPLETED' or values.get('ExitCode')!='0:0':
            raise RuntimeError('Original source Slurm producer is not COMPLETED/0:0')
        if '('+str(os.getuid())+')' not in values.get('UserId',''):raise ValueError('Source producer UID differs')
        return {'tool':'native scontrol','raw':result.stdout,'source_node':values.get('NodeList')}
    # Compute-node sacct uses an unavailable localhost dbd on this cluster.
    # Query the established login metadata endpoint without moving any data.
    raw=subprocess.check_output(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10','sonmi',
        'sacct','-j',str(job),'-X','--noheader','--parsable2','-o','JobID,State,ExitCode'],text=True,timeout=30)
    lines=[x.split('|') for x in raw.splitlines() if x.startswith(str(job)+'|')]
    if len(lines)!=1 or lines[0][1:3]!=['COMPLETED','0:0']:raise RuntimeError('Actual source accounting is not closed successfully')
    return {'tool':'native sacct via login metadata SSH','raw':raw,'source_node':None}


def seal_geometry(root,job):
    evidence=completed_evidence(job)
    folder=Path(root)/'geometry/shared_v1'
    path=folder/('producer_'+str(job)+'.json');manifest=json.loads(path.read_text())
    if (str(manifest['job'])!=str(job) or manifest['status']!='ALL_QUEUED_MOLECULES_TERMINAL'
            or any(manifest['states'].get(k,0) for k in ('PENDING','INTENT'))):
        raise ValueError('Original source producer has not closed its complete queue')
    access=folder/'access.json'
    prior=json.loads(access.read_text()) if access.exists() else {}
    if prior and str(prior['producer_job'])!=str(job):raise ValueError('A different source producer owns the access declaration')
    publish(access,{'producer_job':job,'producer_node':evidence['source_node'] or prior.get('producer_node','unknown'),
        'cross_node_read_allowed':True,'immutable':True,'source_producer_manifest':str(path),
        'actual_closure_evidence':evidence,'scientific_failures_and_unknowns_preserved':True,
        'database_copy_created':False})
    print('GEOMETRY_CROSS_NODE_READ_SEALED',job,manifest['states'],flush=True)
