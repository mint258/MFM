"""End only this run's superseded v2 pilots after exact ownership and task checks."""
import json,os,socket,subprocess,time
from prepare import ROOT,save
from submit import query,fields,PROJECT

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    out=ROOT/'reports/superseded_pilot_retirement.json'
    if out.exists():raise FileExistsError('Retirement receipt already exists')
    records=[]
    for group,node in [(3,'compute-0-9'),(4,'compute-0-10'),(5,'compute-0-11')]:
        receipt=json.loads((ROOT/f'submission/pilot_group{group}.json').read_text());jid=receipt['job_id']
        p=subprocess.run(['scontrol','show','job',jid,'--oneliner'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        row={'job_id':jid,'group':group,'before_query_rc':p.returncode,'before_metadata':p.stdout,'before_stderr':p.stderr}
        if p.returncode==0:
            info=fields(p.stdout)
            assert info['UserId']=='zixiao(1278)' and info['JobName']=='sprime_pilot_group'+str(group)
            assert info['ReqNodeList']==node and info['WorkDir']==str(PROJECT)
            row['active']=info['JobState'] in {'RUNNING','COMPLETING','PENDING'}
        else:
            accounting=query(['sacct','-j',jid,'--noheader','--parsable2','--format=JobIDRaw,User,State,ExitCode'])
            matches=[line.split('|') for line in accounting.splitlines() if line.split('|')[0]==jid]
            assert len(matches)==1 and matches[0][1]=='zixiao' and matches[0][2] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'}
            row['active']=False;row['terminal_accounting']=accounting
        records.append(row)
    result={'timestamp':time.time(),'reason':'SUPERSEDED_RMSD_METHOD_V2_REPLACED_BY_SOURCE_ATOM_INDEX_KABSCH_V4; work continues through existing afterany v4 jobs; preserve all completed outputs and accounting','uid':os.getuid(),'records':records,'state':'VERIFIED_INTENT','original_data_written':False}
    save(out,result)
    for row in records:
        if row['active']:
            p=subprocess.run(['scancel',row['job_id']],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
            row.update(scancel_rc=p.returncode,scancel_stdout=p.stdout,scancel_stderr=p.stderr)
            save(out,result)
            assert p.returncode==0
    result['state']='OWN_SUPERSEDED_JOBS_ENDED_V4_CONTINUES';save(out,result)
    print(json.dumps({'ended_own_job_ids':[r['job_id'] for r in records if r['active']],'v4_jobs_continue':True}))

if __name__=='__main__':main()
