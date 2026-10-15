"""Root-only actual G6 resume submission, replacing only unstarted obsolete tests."""
import hashlib,json,os,re,subprocess,time
from pathlib import Path
from wp5_monitor_v2 import ROOT,atomic
PYTHON='/share/home/zixiao/.conda/envs/chemprop/bin/python'
FROZEN={'wp5_accounting_v2.py':'8ccf483791458817d26bfdcddb2bcca69f6929cdacbcccc8d8ed3f8999a66aa5',
 'wp5_runner_v6.py':'85560d96a67e16387916e2667f3512ad9e1189c865e0d945ac0ff138a821cd8d',
 'wp5_g6_recover_v6.py':'68217dbd8083e27f12556df584afd201773d3ab0fa97a05648aaa54c0270b311',
 'wp5_g6_recover_v6.sbatch':'1d4c2ae1f6a5f2aeba8d1c3653d7956e8ea147cd307771b1a36989c8e6173581'}
def run(args):
    process=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
    obj={'argv':args,'returncode':process.returncode,'stdout':process.stdout,'stderr':process.stderr}
    if process.returncode:raise RuntimeError(json.dumps(obj))
    return obj

def main():
    if os.getuid()!=1278 or os.uname().nodename.split('.')[0]!='sonmi':raise ValueError('Root actual login required')
    target=ROOT/'gates/g6_recovery/v6_root_submission.json'
    if target.exists():raise ValueError('This root submission phase already exists; inspect exact receipts')
    for name,digest in FROZEN.items():
        if hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest()!=digest:raise ValueError('Prepared binding changed:'+name)
    result={'time':time.time(),'status':'G6_V6_SUBMISSION_IN_PROGRESS','sources':FROZEN,
        'reason':'Compute sacct localhost6819 and compute to login SSH unavailable; verified actual Root login publisher snapshot replaces accounting only',
        'cancelled_unstarted':[],'jobs':[],'error':None}
    atomic(target,result)
    try:
        for jid,node in [('4513913','compute-0-15'),('4513914','compute-0-16')]:
            matches=[]
            for path in (ROOT/'logs').glob('*_submission.json'):
                receipt=json.loads(path.read_text())
                if str(receipt['job_id'])==jid:matches.append((path,receipt))
            if len(matches)!=1 or matches[0][1]['node']!=node:raise ValueError('Obsolete job receipt not exact:'+jid)
            before=run(['scontrol','show','job','-o',jid]);fields=dict(re.findall(r'(\w+)=([^\s]+)',before['stdout']))
            if fields.get('UserId')!='zixiao(1278)' or fields.get('JobState')!='PENDING' or fields.get('RunTime')!='00:00:00':
                raise ValueError('Obsolete job started or ownership/state changed; preserve:'+jid)
            if fields.get('ReqNodeList')!=node or fields.get('JobName')!='wp5_g6_v4_'+node.rsplit('-',1)[1]:
                raise ValueError('Obsolete test name or requested node differs:'+jid)
            cancelled=run(['scancel',jid]);after=run(['sacct','-X','-n','-P','-j',jid,'--format=JobID,User,State,ElapsedRaw'])
            result['cancelled_unstarted'].append({'job_id':jid,'receipt':str(matches[0][0]),'before':before,'cancel':cancelled,'after':after})
            atomic(target,result)
        for number in range(14,20):
            node='compute-0-'+str(number);old={14:'4513901',17:'4513904',18:'4513905',19:'4513906'}.get(number)
            environment=dict(os.environ)
            environment.update(WP5_DICTIONARIES=str(ROOT/'dictionaries/job_4513894/dictionary_manifest.json'),
                WP5_G6_RETRY_DIAGNOSIS=str(ROOT/'gates/g6_retry_diagnosis/job_4513910/report.json'),
                WP5_G6_SOURCE_RUN=str(ROOT/'gates/g6'/node/('job_'+old)) if old else '')
            argv=[PYTHON,'-B',str(ROOT/'scripts/submit_wp5_job.py'),
              '--script',str(ROOT/'scripts/wp5_g6_recover_v6.sbatch'),'--name','wp5_g6_v6_'+str(number),
              '--node',node,'--cpus','24','--memory-gb','32','--time','48:00:00','--kind','quantum','--allow-pending']
            process=subprocess.run(argv,env=environment,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
            if process.returncode:raise RuntimeError(node+': '+process.stderr)
            receipt=json.loads(process.stdout)
            result['jobs'].append({**receipt,'source_run':environment['WP5_G6_SOURCE_RUN'],
                'report':str(ROOT/'gates/g6_recovery'/node/('job_'+receipt['job_id'])/'report.json')})
            atomic(target,result);print(json.dumps(result['jobs'][-1]),flush=True)
        result['status']='ALL_SIX_G6_V6_REGISTERED';atomic(target,result)
    except BaseException as exc:
        result['error']=repr(exc);result['status']='SUBMISSION_REQUIRES_ROOT_RECONCILIATION';atomic(target,result);raise
if __name__=='__main__':main()
