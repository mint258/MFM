"""Read-only same-cluster accounting: compute nodes query the verified sonmi login.
No QM or queue mutation. Strict key authentication; query receipts preserve all text.
"""
from __future__ import annotations
import argparse,getpass,json,os,shlex,socket,subprocess,time,uuid
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
LOGIN='zixiao@10.1.1.1'

def command_for(args,node=None):
    args=[str(x) for x in args]
    if args and Path(args[0]).name=='sacct':args=args[1:]
    if not args or any('\x00' in arg for arg in args):raise ValueError('Nonempty read-only sacct arguments required')
    command=['sacct',*args];node=(node or socket.gethostname()).split('.')[0]
    if node.startswith('compute-'):
        return ['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=20',LOGIN,shlex.join(command)],command,'COMPUTE_TO_VERIFIED_SONMI_LOGIN'
    return command,command,'LOCAL_LOGIN_SACCT'

def run_sacct(args,timeout=60,evidence_path=None):
    if getpass.getuser()!='zixiao':raise ValueError('WP5_ACCOUNTING_REQUIRES_SAME_ZIXIAO_USER')
    argv,query,transport=command_for(args);started=time.monotonic()
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        def decoded(value):return value.decode('utf8','replace') if isinstance(value,bytes) else value or ''
        result=subprocess.CompletedProcess(argv,124,decoded(exc.stdout),decoded(exc.stderr)+'\nOWN_ACCOUNTING_QUERY_TIMEOUT; no QM process signalled\n')
    evidence={'schema':'WP5_ACCOUNTING_QUERY_V1','time_epoch':time.time(),'seconds':time.monotonic()-started,
      'job_id':os.environ.get('SLURM_JOB_ID'),'node':socket.gethostname().split('.')[0],'user':getpass.getuser(),
      'uid':os.getuid(),'transport':transport,'login_destination':LOGIN if transport.startswith('COMPUTE') else None,
      'sacct_argv':query,'execution_argv':argv,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
      'key_authentication':True,'strict_host_key_checking':True,'same_cluster_only':True,'QM_started':False}
    if evidence_path is None:
        evidence_path=ROOT/'gates/accounting'/('job_'+os.environ.get('SLURM_JOB_ID','login'))/(str(time.time_ns())+'_'+uuid.uuid4().hex[:8]+'.json')
    target=Path(evidence_path).absolute()
    if not target.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Accounting receipt writes only to this new WP5 root')
    target.parent.mkdir(parents=True,exist_ok=True)
    # Every query receipt is new; no old result or source file can be overwritten.
    with target.open('x') as stream:
        json.dump(evidence,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    result.evidence=evidence;result.evidence_path=str(target)
    return result

def check():
    local,q,t=command_for(['sacct','-X','-n','-P','-j','4513901','--format=JobID,User,State'],'sonmi')
    assert local==q and t=='LOCAL_LOGIN_SACCT'
    remote,q,t=command_for(['-X','-n','-P','-j','4513901','--format=JobID,User,State'],'compute-0-14')
    assert remote[:3]==['ssh','-o','BatchMode=yes'] and 'StrictHostKeyChecking=yes' in remote and LOGIN in remote
    assert shlex.split(remote[-1])==q and t=='COMPUTE_TO_VERIFIED_SONMI_LOGIN'
    print('ACCOUNTING_ROUTE_FIXTURES_PASS_NO_SSH_NO_SACCT_NO_QM')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--job-id');a=p.parse_args()
    if a.check:check()
    elif a.job_id:
        r=run_sacct(['-X','-n','-P','-j',a.job_id,'--format=JobID,User,State'])
        print(json.dumps({'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'evidence_path':r.evidence_path}))
