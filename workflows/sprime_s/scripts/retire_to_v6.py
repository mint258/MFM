"""Retire only this run's old unbounded-embedding pilots; preserve all closed SCI."""
import json,os,socket,subprocess,time
from prepare import ROOT,save
from submit import query,fields,PROJECT

def main():
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    dest=ROOT/'reports/unbounded_embedding_retirement_v6.json'
    if dest.exists():raise FileExistsError('Retirement already recorded')
    records=[]
    for version in [5,4]:
        for group,node in [(1,2),(2,8),(3,9),(4,10),(5,11)]:
            registered=json.loads((ROOT/f'submission/pilot_v{version}_group{group}.json').read_text());jid=registered['job_id']
            p=subprocess.run(['scontrol','show','job',jid,'--oneliner'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
            item={'job_id':jid,'version':version,'group':group,'metadata':p.stdout,'query_rc':p.returncode,'query_stderr':p.stderr,'active':False}
            if p.returncode==0:
                info=fields(p.stdout)
                assert info['UserId']=='zixiao(1278)' and info['JobName']==f'sprime_v{version}_group{group}' and info['ReqNodeList']==f'compute-0-{node}' and info['WorkDir']==str(PROJECT)
                item['active']=info['JobState'] in {'RUNNING','COMPLETING','PENDING'}
            else:
                ac=query(['sacct','-j',jid,'--noheader','--parsable2','--format=JobIDRaw,User,State,ExitCode']);rows=[line.split('|') for line in ac.splitlines() if line.split('|')[0]==jid]
                assert len(rows)==1 and rows[0][1]=='zixiao' and rows[0][2] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'}
                item['terminal_accounting']=ac
            records.append(item)
    result={'reason':'OWN_PILOT_SOFTWARE_RECOVERY: native stack proves default random-coordinate embedding retry consumes long attempt budgets; replace with deterministic maxIterations=200 and rerun identical 10000-molecule sample','timestamp':time.time(),'uid':os.getuid(),'records':records,'state':'VERIFIED_INTENT','original_data_written':False,'closed_science_deleted':False}
    save(dest,result)
    for row in records:
        if row['active']:
            p=subprocess.run(['scancel',row['job_id']],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30);row.update(scancel_rc=p.returncode,scancel_stdout=p.stdout,scancel_stderr=p.stderr);save(dest,result);assert p.returncode==0
    result['state']='V6_CONTINUATION_REQUIRED';save(dest,result);print(json.dumps({'ended_exact_own_job_ids':[r['job_id'] for r in records if r['active']]}))

if __name__=='__main__':main()
