"""Real local PID/time and direct account quota; no invented Slurm context."""
import inspect,json,os,pathlib,socket,subprocess,textwrap,time,types
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import resource as R
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1 import quota_provider as Q

def local_wall_clock(proof,seconds):
    now=time.time();mono=time.monotonic();elapsed=max(0,now-proof['local_started_unix_seconds'])
    remaining=max(0,seconds-elapsed)
    return dict(schema='ACTUAL_LOCAL_PID_MONOTONIC_WALL_BUDGET_V1',execution_kind='LOCAL_HEADNODE',
      execution_id=proof['execution_id'],actual_pid=proof['pid'],actual_start_ticks=proof['start_ticks'],
      cpu_wall_at_anchor=now,cpu_monotonic_anchor=mono,cpu_monotonic_deadline=mono+remaining,
      remaining_at_anchor_seconds=remaining,effective_wall_seconds=seconds,
      proof_to_budget_seconds_including_startup_and_fixtures=elapsed,Slurm_job_id=None)

class LocalQuotaClient:
    def __init__(self,review_reference,request):
        self.review=R.C.meta(review_reference);self.identity=request['local_quota_identity_reference']
        self.identity_body=R.C.meta(self.identity);self.sequence=0;self.last=None
        R.C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
          and self.review['execution_kind']=='LOCAL_HEADNODE' and self.identity_body['pid']==os.getpid(),
          'ACTUAL_USER_AUTHORIZED_MAIN_LOCAL_QUOTA_CLIENT')
    def observe(self):
        a=Q.query(Q.QUOTA_ARGV)
        quota=Q.parse_quota(a,'/dev/sda1');now=time.time();self.sequence+=1
        R.C.need(now<self.identity_body['expires_unix_seconds'],'FINITE_LOCAL_QUOTA_CLIENT_EXPIRED')
        marker=pathlib.Path(self.review['storage_marker_path']);s=marker.lstat()
        R.C.need(s.st_uid==1278 and s.st_nlink==1 and not marker.is_symlink(),'ACTUAL_LOCAL_STORAGE_MARKER')
        root=pathlib.Path(self.review['snapshot_root']);root.mkdir(exist_ok=True)
        path=root/('quota_%06d.json'%self.sequence)
        record=dict(quota)
        record.update(schema='ACTUAL_MAIN_HEAD_ACCOUNT_QUOTA_V1',execution_kind='LOCAL_HEADNODE',
          uid=os.getuid(),pid=os.getpid(),observed_unix_seconds=now,raw_quota=a['stdout'])
        path.write_text(json.dumps(record,sort_keys=True)+'\n');snapshot=I.pin(path)
        self.last=dict(free_bytes=quota['free_bytes'],observed_unix_seconds=now,
          publisher_expires_unix_seconds=self.identity_body['expires_unix_seconds'],
          snapshot_reference=snapshot,identity_reference=self.identity,provider_status='RUNNING',
          execution_kind='LOCAL_HEADNODE',raw_free_bytes_rewritten=False,
          cpu_marker=dict(stat=dict(device=s.st_dev,inode=s.st_ino,uid=s.st_uid)))
        return self.last

LOCAL_PROVIDER=types.SimpleNamespace(Client=LocalQuotaClient)

def local_private(original,census,**bindings):
    if original is not I.Budget.__init__:return R.private(original,census,**bindings)
    source=textwrap.dedent(inspect.getsource(original))
    old=("    provider=QP\n"
      "    if plan['node'] not in ('compute-0-14','compute-0-18'):\n"
      "        from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1 import quota_provider as provider\n")
    new='    provider=LOCAL_PROVIDER\n'
    R.C.need(source.count(old)==1,'ONE_EXACT_QUOTA_PROVIDER_ROLE_BINDING')
    changed=source.replace(old,new,1)
    R.C.need(changed.replace(new,old,1)==source,'ONLY_LOCAL_PROVIDER_ROLE_BINDING_CHANGED')
    namespace=dict(original.__globals__,unique_bytes=census,wall_clock=local_wall_clock,
      LOCAL_PROVIDER=LOCAL_PROVIDER,**bindings)
    exec(compile(changed,__file__+'::local_budget_initialization','exec'),namespace)
    f=namespace[original.__name__];f.__defaults__=original.__defaults__;f.__kwdefaults__=original.__kwdefaults__
    return f

class LocalBudget(R.ResourceBudget):
    def __init__(self,plan,proof,root):
        original=R.ResourceBudget.__init__
        namespace=dict(original.__globals__,private=local_private)
        types.FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)(self,plan,proof,root)
