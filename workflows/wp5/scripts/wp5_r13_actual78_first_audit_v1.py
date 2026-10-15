import collections,hashlib,json,os,re,subprocess,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
manifest=root/'submission/recovery_attempt_v13/submitted_jobs.json';m=json.loads(manifest.read_text())
assert m['status']=='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED' and len(m['main'])==72 and len(m['cleanup'])==6
jobs=m['main']+m['cleanup']; ids={str(x['job_id']) for x in jobs};assert len(ids)==78
r=subprocess.run(['scontrol','show','job','-o'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
assert r.returncode==0
live={}
for line in r.stdout.splitlines():
    fields=dict(re.findall(r'(\w+)=([^\s]+)',line))
    if fields.get('JobId') in ids:live[fields['JobId']]=fields
q=subprocess.run(['sacct','-X','-n','-P','-j',','.join(sorted(ids,key=int)),'--format=JobID,User,State,ExitCode,AllocCPUS,ElapsedRaw'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
assert q.returncode==0
accounting={}
for line in q.stdout.splitlines():
    f=line.split('|')
    if len(f)>=6 and f[0] in ids:
        assert f[1]=='zixiao';accounting[f[0]]={'state':f[2].split()[0].rstrip('+'),'exit_code':f[3],'allocated_cpus':int(f[4]),'elapsed_seconds':int(f[5])}
issues=[];rows=[]
for row in jobs:
    jid=str(row['job_id']);f=live.get(jid)
    expected={str(x['job_id']) for x in m['main'] if x['node']==row['node']} if row['mode']=='cleanup' else set()
    if f:
        if not f.get('UserId','').startswith('zixiao(1278)'):issues.append({'job_id':jid,'issue':'actual_user_differs'})
        if f.get('NumCPUs')!='24' or f.get('MinMemoryNode')!='32G' or f.get('TimeLimit') not in ('2-00:00:00','48:00:00'):issues.append({'job_id':jid,'issue':'actual_resources_differ','fields':f})
        if f.get('ReqNodeList')!=row['node'] or f.get('NodeList') not in (row['node'],'(null)','None'):issues.append({'job_id':jid,'issue':'actual_node_differs','fields':f})
        if row['mode']=='cleanup':
            deps=f.get('Dependency','(null)')
            pending=set(re.findall(r'afterany:(\d+)',deps))
            # Slurm renders grouped dependency as afterany:ID(state):ID(state).
            if deps.startswith('afterany:'):pending=set(re.findall(r'(?:afterany:|:)(\d+)(?:\(|:|$)',deps))
            if pending-expected:issues.append({'job_id':jid,'issue':'foreign_cleanup_dependency','dependency':deps})
            missing=expected-pending
            for parent in missing:
                if accounting.get(parent,{}).get('state') not in {'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT','DEADLINE','REVOKED'}:
                    issues.append({'job_id':jid,'issue':'missing_nonterminal_own_node_dependency','parent':parent,'dependency':deps})
        rows.append({'job_id':jid,'node':row['node'],'mode':row['mode'],'scheduler_fields':{k:f.get(k) for k in ('UserId','JobState','NumCPUs','MinMemoryNode','TimeLimit','ReqNodeList','NodeList','Dependency')}})
    elif accounting.get(jid,{}).get('state') not in {'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT','DEADLINE','REVOKED'}:
        issues.append({'job_id':jid,'issue':'no_actual_live_or_terminal_evidence'})
if set(accounting)!=ids:issues.append({'issue':'actual78_accounting_missing','ids':sorted(ids-set(accounting),key=int)})
dest=root/'reports/r13_actual78_first_scheduling_audit_v1.json'
report={'schema':'WP5_R13_ACTUAL78_FIRST_SCHEDULING_AUDIT_V1','status':'PASS' if not issues else 'NOT_PASS','time':time.time(),'uid':os.getuid(),'manifest':{'path':str(manifest),'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()},'main_count':72,'cleanup_count':6,'actual_states':dict(collections.Counter(x['state'] for x in accounting.values())),'actual_unique_jobs':78,'science_jobs_started':sum(v['state']=='RUNNING' for v in accounting.values()),'rows':rows,'accounting':accounting,'issues':issues,'scontrol_rc':r.returncode,'sacct_rc':q.returncode,'queue_written':False,'Slurm_submitted':False}
with dest.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'status':report['status'],'report':str(dest),'actual_states':report['actual_states'],'issues':issues}))
raise SystemExit(0 if not issues else 2)
