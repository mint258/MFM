"""Real node19 storage edge; unchanged login quota validator and observations."""
import argparse,json,os,pathlib,re,socket,threading,time
from . import contract as C
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as R
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as ADMISSION


def stat_frame(info):return {k:getattr(info,a) for k,a in (('device','st_dev'),('inode','st_ino'),('size','st_size'),('mtime_ns','st_mtime_ns'),('uid','st_uid'))}


def addresses(host):return sorted({r[4][0] for r in socket.getaddrinfo(host,None,socket.AF_INET)})


def provider_resources(reference,identity_reference):
    review=Q.load_review(reference);identity=Q.pinned(identity_reference)
    C.need(identity['review_reference']==reference and identity['publisher_output_dir']==review['publisher_output_dir'],'ACTUAL_ORIGINAL_PUBLISHER_IDENTITY_NOT_NEW_NODE_FACTS')
    return review,identity,[*Q.references(reference),identity_reference]


def login_snapshot(provider,identity,provider_reference,identity_reference):
    root=pathlib.Path(provider['publisher_output_dir']);latest=json.loads(Q.small(root/'latest.json')[0])
    C.need(latest['schema']==Q.LATEST_SCHEMA and latest['review_reference']==provider_reference
        and latest['identity_reference']==identity_reference,'EXACT_EXISTING_LOGIN_PUBLISHER_POINTER')
    r=latest['snapshot_reference'];path=pathlib.Path(r['path'])
    C.need(path.parent==root and re.fullmatch(r'observation_[0-9]{6}\.json',path.name),'ONLY_OWN_IMMUTABLE_PROVIDER_OBSERVATIONS')
    value=Q.pinned(r)
    evidence={'snapshot_reference':r,'identity_reference':identity_reference,'provider_status':value.get('status'),
        'provider_error':value.get('error'),'observed_unix_seconds':value.get('observed_unix_seconds'),
        'publisher_expires_unix_seconds':identity['expires_unix_seconds']}
    return value,evidence


def validate_edge(probe,provider):
    C.need(probe['schema']=='PM7_NODE19_STORAGE_METADATA_PROBE_RECEIPT_V1'
        and probe['status']=='ACTUAL_NODE19_METADATA_OBSERVED_REQUIRES_ROOT_SAME_STORAGE_REVIEW'
        and probe['uid']==1278 and probe['node']==C.NODE and probe['endpoint']==C.ENDPOINT,'REAL_NODE19_METADATA_PROBE')
    observed=probe['storage'];parsed=Q.parse_mount(observed['findmnt'],observed['df'])
    C.need(observed['uid']==1278 and observed['node']==C.NODE and observed['endpoint']==C.ENDPOINT
        and parsed==observed['mount_selection'] and parsed['active_mount']==observed['mount']
        and parsed['df_active_row']['total_kib']==Q.MAPPING_FILESYSTEM_TOTAL_KIB,'REAL_NODE19_ACTIVE_FILESYSTEM_AND_SHARED_BLOCK_TOTALS')
    C.need(observed['mount']['fstype']=='nfs4' and observed['mount']['source']=='nfs:/share/home'
        and observed['mount']['target']=='/share/home' and observed['mount']['fsroot']=='/'
        and probe['nfs_addresses']==probe['login_hostname_addresses']==['10.1.1.1'],'ACTUAL_MAIN_NFS_EXPORT_AND_SERVER_RESOLUTION')
    marker=probe['marker'];C.need(marker['reference']==provider['marker_reference'] and marker['bytes_checked']==marker['reference']['bytes']
        and all(marker['stat'][k]==v for k,v in Q.MARKER_IDENTITY.items()),'ACTUAL_SHARED_MARKER_BYTES_UID_INODE_MTIME')
    return observed['mount']


def probe_chain(probe,receipt_reference):
    proof=C.meta(probe['startup_proof_reference']);request=proof['request'];plan=C.meta(probe['plan_reference'])
    C.need(C.meta(proof['request_reference'])==request and request['startup_proof_path']==probe['startup_proof_reference']['path']
        and proof['job_id']==probe['job_id'] and proof['uid']==1278 and proof['boot_id']==probe['boot_id']
        and request['node']==C.NODE and request['cpus']==16 and request['pilot'] is False
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and request['scope_key']==C.key('probe')
        and request['scope_parameters']==C.scope('probe'),'REAL_REGISTERED_NODE19_PROBE_REQUEST_PROOF_CHAIN')
    ADMISSION.validate_request(request,read_small=ADMISSION.read_small,script_text=ADMISSION.read_small(request['script_reference']['path']).decode())
    ADMISSION.validate_bound_request(request,read_small=ADMISSION.read_small)
    expected=[Q.PY,'-B','-m','workflows.data_v1_final.conformers.pm7_multinode_compat32_v1.resources',
        '--plan',probe['plan_reference']['path'],'--root-preflight',probe['startup_proof_reference']['path'],
        '--output',str(pathlib.Path(receipt_reference['path']).parent)]
    # The output is the actual receipt parent, never inferred from a future plan.
    C.need(C.meta(receipt_reference)==probe and pathlib.Path(receipt_reference['path']).name=='receipt.json'
        and request['execution_argv']==expected and C.BASE in pathlib.Path(expected[9]).parents
        and C.M.pin(C.HERE/'resources.py') in request['source_references'] and probe['plan_reference'] in request['source_references']
        and plan['schema']==C.SCHEMA and plan['mode']=='probe' and plan['status']=='APPROVED_QA_ONLY'
        and plan['reviewer']=='root','FIXED_REGISTERED_PROBE_PRIMARY_ALL_OPTIONS_AND_APPROVED_PLAN')
    return proof,plan


def binding(reference):
    value=C.meta(reference);C.need(value['schema']==C.BINDING and value['status']==C.RESOURCE_STATUS and value['reviewer']=='root'
        and value['endpoint']==C.ENDPOINT and value['uid']==1278 and value['node']==C.NODE
        and value['compatibility_controls_only'] is True and value['full_dispatch_authorized'] is False
        and value['QA_output_cap_bytes']==C.CAP and type(value['other_future_output_reserve_bytes']) is int
        and value['other_future_output_reserve_bytes']>=0,'INDEPENDENT_ROOT_NODE19_RESOURCE_EDGE_NOT_PRODUCTION_AUTHORITY')
    provider,identity,refs=provider_resources(value['provider_review_reference'],value['publisher_identity_reference'])
    probe=C.meta(value['probe_receipt_reference']);account=C.actual_account(value['probe_accounting_reference'],probe['job_id'])
    proof,plan=probe_chain(probe,value['probe_receipt_reference'])
    C.need(plan['provider_review_reference']==value['provider_review_reference']
        and plan['publisher_identity_reference']==value['publisher_identity_reference']
        and plan['other_future_output_reserve_bytes']==value['other_future_output_reserve_bytes'],
        'ROOT_BINDING_IS_FOR_THE_ACTUAL_PROBED_EXISTING_PROVIDER_AND_RESERVATION')
    mount=validate_edge(probe,provider);C.need(value['compute_mount']==mount and value['canonical_expected_frame']==probe['canonical_stat']
        and value['canonical_reference']==probe['canonical_reference'],'EXACT_ACTUAL_REVIEWED_NODE19_FRAME_AND_MOUNT')
    refs.extend((reference,value['probe_receipt_reference'],value['probe_accounting_reference'],account,probe['startup_proof_reference'],probe['plan_reference']))
    refs.extend(proof['request']['source_references'])
    return value,provider,identity,C.unique(refs)


class Client:
    """Old login freshness/quota semantics; a separately approved actual19 edge."""
    def __init__(self,reference,request):
        self.binding_ref=reference;self.binding,self.provider,self.publisher,self.refs=binding(reference);self.request=request
        C.need(request['node']==C.NODE,'ACTUAL_NODE19_REQUEST_NOT_A_NODE13_ALIAS');self.last=None;self.sequence=-1
    def observe(self):
        C.need(C.meta(self.binding_ref)==self.binding,'IMMUTABLE_RESOURCE_EDGE_REVIEW')
        observed=Q.storage_observation();C.need(observed['node']==self.request['node'],'ACTUAL_COMPUTE_NODE19_STORAGE_OBSERVATION')
        # Explicit separate edge view, never a modified old review / Client.
        view={'compute_mount_by_node':{C.NODE:self.binding['compute_mount']},'marker_reference':self.provider['marker_reference']}
        marker=Q.verify_storage(view,observed,login=False)
        value,evidence=login_snapshot(self.provider,self.publisher,self.binding['provider_review_reference'],self.binding['publisher_identity_reference'])
        self.last=dict(evidence,cpu_storage=observed,cpu_marker=marker)
        parsed=Q.validate_observation(value,self.publisher,self.binding['publisher_identity_reference'],self.provider,self.binding['provider_review_reference'],time.time())
        C.need(value['sequence']>=self.sequence,'NO_PROVIDER_ROLLBACK');self.sequence=value['sequence'];self.last.update(parsed_quota=parsed,free_bytes=parsed['free_bytes'])
        return self.last


class Budget(R.Budget):
    """Reuse old observe/monitor/report objects, without its13-only constructor."""
    def __init__(self,proof,session,out):
        self.client=Client(session['resource_binding_reference'],proof['request']);self.Q=Q
        self.value={'algorithm_rss_soft_cap_bytes':64<<30,'minimum_MemAvailable_bytes':4<<30};self.out=out
        self.reserve=self.client.binding['other_future_output_reserve_bytes']+C.CAP;self.started=time.monotonic();self.next=0
        self.stop=None;self.samples=[];self.quota=[];self.failure=None;self.proof=proof
        wall=proof['request']['wall_seconds'];self.wall_dispatch_cutoff_seconds=wall-min(600,max(1,wall//10))
        self.workers={};self.mutex=threading.RLock();self.finished=threading.Event();self.monitor=None
        # Deliberately do not assign R.ACTIVE_BUDGET / OUT / PROOF or any old globals.
    def observe(self,processes=()):
        result=super().observe(processes)
        try:
            if R.disk_bytes(self.out)+R.reserved_bytes(self.out)+C.ADMIN>C.CAP:self.stop=self.stop or 'QA2GIB_OUTPUT_STOP_NEW_DISPATCH'
        except Exception as exc:self.failure={'error':repr(exc),'last_quota_evidence':self.client.last};self.stop=self.stop or 'QA_RESOURCE_OBSERVATION_UNAVAILABLE'
        return self.stop
    def report(self):
        return dict(super().report(),QA_output_cap_bytes=C.CAP,legacy_managed_disk_soft_stop_bytes=8<<30,
            effective_owned_disk_soft_stop_bytes=min(C.CAP,8<<30),old_budget_constructor_or_globals_modified=False)


def continuation(session):
    proof=C.meta(session['proof_reference']);req=proof['request']
    C.need(os.getppid()==session['parent_pid'] and R.proc_ticks(os.getppid())==session['parent_start_ticks']
        and os.getuid()==1278 and socket.gethostname().split('.')[0]==req['node']==C.NODE
        and os.environ.get('SLURM_JOB_ID')==session['job_id']==str(proof['job_id']) and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id']
        and req['execution_argv']==session['execution_argv'] and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and M_pin(session['main_source']['path'])==session['main_source'],'SAME_LIVE_NEW_ADMITTED_PARENT_NO_OLD_PROOF_AGE_WAIVER')
    for r in session['source_references']:C.need(M_pin(r['path'])==r,'ADMITTED_QA_SOURCE_CHANGED')
    return proof


def M_pin(path):return C.M.pin(path)


def probe_main():
    p=argparse.ArgumentParser(description='Actual CPU19 metadata only, no canonical body hash')
    for name in C.OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=True)
    a=p.parse_args();plan=C.M.load(a.plan);control=C.controls();_,_,resources=provider_resources(plan['provider_review_reference'],plan['publisher_identity_reference'])
    argv=[Q.PY,'-B','-m',__package__+'.resources','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=ADMISSION.require_startup(a.root_preflight,expected_scope_key=C.key('probe'),expected_scope_parameters=C.scope('probe'),expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[M_pin(a.plan),*C.request_sources(control),*plan['source_references'],*resources])
    req=proof['request'];C.need(plan['schema']==C.SCHEMA and plan['mode']=='probe' and plan['status']=='APPROVED_QA_ONLY'
        and plan['reviewer']=='root' and req['node']==C.NODE and req['cpus']==16
        and req['pilot'] is False and req['estimated_peak_output_bytes']==req['stage_output_cap_bytes']==C.PROBE_CAP
        and 600<=req['wall_seconds']<=900 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['data_references']==[control['base']['formal_source']] and not a.output.exists(),'EXACT_NEW_CPU19_STORAGE_PROBE')
    C.need(C.BASE in a.output.parents and '..' not in a.output.parts,'OWN_NEW_PROBE_OUTPUT');a.output.mkdir(parents=True,mode=0o700)
    provider,identity,_=provider_resources(plan['provider_review_reference'],plan['publisher_identity_reference'])
    value,evidence=login_snapshot(provider,identity,plan['provider_review_reference'],plan['publisher_identity_reference'])
    quota=Q.validate_observation(value,identity,plan['publisher_identity_reference'],provider,plan['provider_review_reference'],time.time())
    C.need(quota['free_bytes']-plan['other_future_output_reserve_bytes']-C.PROBE_CAP-Q.CAP-C.ADMIN>=200000000000
        and time.time()+req['wall_seconds']+300<=identity['expires_unix_seconds'],'ACTUAL_FRESH_SHARED_ACCOUNT200GB_AND_FINITE_EXISTING_PUBLISHER')
    observed=Q.storage_observation();raw,ref=Q.small(provider['marker_reference']['path'])
    marker_info=pathlib.Path(ref['path']).stat();canonical=pathlib.Path(control['base']['formal_source']['path']);info=canonical.lstat()
    C.need(not canonical.is_symlink() and info.st_uid==1278 and info.st_size==control['base']['formal_source']['bytes'],'CANONICAL_STAT_ONLY_UID_SIZE')
    marker={'reference':ref,'bytes_checked':len(raw),'stat':{'device':marker_info.st_dev,'inode':marker_info.st_ino,'uid':marker_info.st_uid,'bytes':marker_info.st_size,'mtime_ns':marker_info.st_mtime_ns}}
    record={'schema':'PM7_NODE19_STORAGE_METADATA_PROBE_RECEIPT_V1','status':'ACTUAL_NODE19_METADATA_OBSERVED_REQUIRES_ROOT_SAME_STORAGE_REVIEW',
        'endpoint':C.ENDPOINT,'uid':os.getuid(),'node':socket.gethostname().split('.')[0],'job_id':str(proof['job_id']),
        'boot_id':proof['boot_id'],'allocated_cpus':req['cpus'],'memory_policy':req['memory_policy'],
        'storage':observed,'marker':marker,'fresh_login_quota_evidence':dict(evidence,parsed_quota=quota),
        'nfs_addresses':addresses('nfs'),'login_hostname_addresses':addresses('sonmi'),
        'canonical_reference':control['base']['formal_source'],'canonical_stat':stat_frame(info),'canonical_body_opened_or_hashed':False,
        'production_ledger_opened':False,'startup_proof_reference':M_pin(a.root_preflight),'plan_reference':M_pin(a.plan),'new_science_calls':0}
    C.M.write(a.output/'receipt.json',record)


if __name__=='__main__':probe_main()
