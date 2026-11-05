"""New queued-admission and recovery boundaries only; no science or corpus reads."""
import os,pathlib,subprocess
from .shared import ROOT,REPO,PY,need,write_new,now

def main():
    jid=os.environ.get('SLURM_JOB_ID','');need(jid.isdecimal(),'REAL_QUEUED_CPU_JOB_REQUIRED')
    stages=[['-m','unittest','workflows.data_v1_final.execution.queue_v1.test_queue_contract','-v'],
        ['-m','unittest','discover','-s',str(REPO/'workflows/data_v1_final/conformers/recovery_v1'),'-p','test_recovery.py','-v'],
        ['-m','unittest','workflows.data_v1_final.pprime.queued_retention_v1.test_v1','-v']]
    rows=[]
    for args in stages:
        r=subprocess.run([PY,'-B',*args],stdin=subprocess.DEVNULL);rows.append({'argv':[PY,'-B',*args],'returncode':r.returncode})
        if r.returncode:break
    status='ALL_NEW_QUEUED_BOUNDARIES_PASSED' if len(rows)==len(stages) and all(v['returncode']==0 for v in rows) else 'NEW_BOUNDARY_FAILURE_NO_SCIENCE'
    write_new(ROOT/'control/queue_checks'/(jid+'.json'),{'schema':'NEW_QUEUE_AND_RECOVERY_CHECKS_V1','job_id':jid,
        'status':status,'stages':rows,'observed_at':now(),'scientific_calls':0,'source_records_read':0})
    return 0 if status=='ALL_NEW_QUEUED_BOUNDARIES_PASSED' else 1
if __name__=='__main__':raise SystemExit(main())
