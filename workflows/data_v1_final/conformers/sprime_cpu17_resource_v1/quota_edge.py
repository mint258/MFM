"""Actual fixed Main17 edge; original login quota/publisher/validator are unchanged."""
import json,pathlib,re,sys,time
from . import contract as C
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
from workflows.data_v1_final.conformers.portable_secondary_uff_v1 import contract as PC
CAP=Q.CAP


def meta(r,schema=None):
    C.need(G.meta_pin(r['path'])==r,'ACTUAL_SMALL_METADATA_PIN');return G.metadata(r['path'],schema)[1]


def root(v,schema,status):
    C.need(v['schema']==schema and v['status']==status and v['reviewer']=='root'
      and v['endpoint']=='202.38.247.57:22' and v['uid']==1278 and v['node']==C.NODE,'EXPLICIT_INDEPENDENT_ROOT_NODE17_REVIEW')


def account(r,jid,node=C.NODE,c0=True):
    C.need(G.meta_pin(r['path'])==r,'ACTUAL_ACCOUNTING_PIN')
    ar,av,rows=G.account(pathlib.Path(r['path']),[str(jid)],c0=[str(jid)] if c0 else [])
    C.need(rows[str(jid)]['node']==node and rows[str(jid)]['alloc_cpus']==16,'ACTUAL_UID1278_NODE_CPU16_ACCOUNTING')
    return av['raw_sacct_reference']


def provider(facts,active=True):
    pr=facts['provider_review_reference'];p=Q.load_review(pr)
    ir=facts['publisher_identity_reference'];i=Q.pinned(ir);launch=meta(facts['publisher_actual_launch_reference'])
    C.need(i['review_reference']==pr and pathlib.Path(ir['path'])==pathlib.Path(p['publisher_output_dir'])/'identity.json'
      and launch['endpoint']=='202.38.247.57:22' and launch['uid']==1278 and launch['review_reference']==pr
      and launch['actual_pid']==i['pid'] and launch['actual_start_ticks']==i['start_ticks']
      and launch['actual_boot_id']==i['boot_id'] and launch['actual_argv']==i['execution_argv']
      and launch['science_jobs_launched_by_publisher']==0,'ACTUAL_FINITE_ROOT_LOGIN_PUBLISHER_NO_NODE_ALIAS')
    old_manifest=G.metadata(G.ROOT/'control/sprime_v3_wave2_freeze_stage_v1/wave2_manifest.json')[1]
    old=meta(old_manifest['quota_reuse_review_reference'])
    C.need(ir!=old['publisher_identity_reference'] and p.get('previous_provider_review_reference')==old['provider_review_reference'],
      'INDEPENDENT_NEW_FINITE_PROVIDER_OLD_IDENTITY_HISTORY_RETAINED')
    C.need(p['maximum_runtime_seconds']==86400 and p['whole_provider_output_cap_bytes']==CAP
      and i['expires_unix_seconds']-i['started_unix_seconds']==86400 and launch['maximum_runtime_seconds']==86400,
      'ORIGINAL24H64MIB_PROVIDER')
    if active:current(facts,p,i)
    return p,i


def current(facts,p=None,i=None,validate=True):
    if p is None:p,i=provider(facts,active=False)
    raw,_=Q.small(pathlib.Path(p['publisher_output_dir'])/'latest.json');latest=json.loads(raw)
    C.need(latest['schema']==Q.LATEST_SCHEMA and latest['identity_reference']==facts['publisher_identity_reference']
      and latest['review_reference']==facts['provider_review_reference'],'LOCKED_EXPLICIT_PUBLISHER_IDENTITY')
    r=latest['snapshot_reference'];path=pathlib.Path(r['path'])
    C.need(path.parent==pathlib.Path(p['publisher_output_dir']) and re.fullmatch(r'observation_[0-9]{6}\.json',path.name),'EXACT_IMMUTABLE_QUOTA_LOCATOR')
    s=Q.pinned(r);parsed=None
    if validate:parsed=Q.validate_observation(s,i,facts['publisher_identity_reference'],p,facts['provider_review_reference'],time.time())
    return s,dict(identity_reference=facts['publisher_identity_reference'],snapshot_reference=r,
      provider_status=s['status'],observed_unix_seconds=s['observed_unix_seconds'],publisher_expires_unix_seconds=i['expires_unix_seconds'],
      parsed_quota=parsed,free_bytes=parsed['free_bytes'] if parsed is not None else None)


def frame(info):return dict(device=info.st_dev,inode=info.st_ino,size=info.st_size,mtime_ns=info.st_mtime_ns,uid=info.st_uid)


def validate_probe(probe,proof):
    C.need(probe['schema']=='ACTUAL_MAIN17_ZERO_SCI_STORAGE_ENV_PROBE_V1' and probe['new_UFF_calls']==probe['new_QM_calls']==0
      and probe['DATA_bodies_opened']==0 and probe['production_ledger_accessed'] is False
      and probe['node']==C.NODE and probe['uid']==1278 and probe['job_id']==str(proof['job_id'])
      and proof['request']['node']==C.NODE and proof['request']['cpus']==16,'REAL_ZERO_SCI_NODE17_PROBE')
    observed=probe['storage'];parsed=Q.parse_mount(observed['findmnt'],observed['df'])
    C.need(observed['node']==C.NODE and observed['uid']==1278 and observed['endpoint']=='202.38.247.57:22'
      and parsed==observed['mount_selection'] and parsed['active_mount']==observed['mount']
      and parsed['active_mount']=={'target':'/share/home','source':'nfs:/share/home','fstype':'nfs4','fsroot':'/'}
      and parsed['df_active_row']['total_kib']==Q.MAPPING_FILESYSTEM_TOTAL_KIB
      and probe['nfs_addresses']==probe['sonmi_addresses']==['10.1.1.1'],'ACTUAL17_NFS_EXPORT_DNS_NOT_NODE13_RELABEL')
    marker=probe['marker']
    C.need(all(marker['stat'][k]==v for k,v in Q.MARKER_IDENTITY.items())
      and marker['reference']==probe['provider_facts']['marker_reference'],'ACTUAL_SHARED_MARKER_IDENTITY')
    C.need(probe['environment']['rdkit']=='2025.09.5' and probe['source_references']==C.own_sources(),'REAL_ENVIRONMENT_AND_SOURCE_IDENTITY')
    return parsed['active_mount']


def probe_closure(r):
    c=meta(r,'ROOT_ACTUAL_MAIN17_ZERO_SCI_PROBE_CLOSURE_V1')
    C.need(c['status']=='ACTUAL_C0_CLOSED_NOT_COMPATIBILITY_PASS','PROBE_C0_NOT_SCIENCE_COMPATIBILITY')
    p=meta(c['receipt_reference']);proof=meta(p['startup_proof_reference']);request=meta(proof['request_reference'])
    C.need(request==proof['request'] and p['plan_reference'] in request['source_references']
      and p['source_references']==C.own_sources(),'ACTUAL_SOURCE_PLAN_PROOF_REQUEST')
    plan=meta(p['plan_reference']);C.need(plan['mode']=='probe' and plan['source_references']==C.own_sources(),'ACTUAL_PROBE_PLAN')
    expected=[Q.PY,'-B','-m',C.MODULE+'.probe','--plan',p['plan_reference']['path'],'--root-preflight',request['startup_proof_path'],
      '--output',str(pathlib.Path(c['receipt_reference']['path']).parent)]
    C.need(request['execution_argv']==expected and request['kind']=='analysis' and request['wall_seconds']==900
      and request['scope_key']=='sprime_cpu17_storage_env_probe_v1','ACTUAL_PROBE_PRIMARY_SCOPE_ALL_OPTIONS')
    validate_probe(p,proof);account(c['accounting_reference'],p['job_id'])
    return c,p,proof


def binding(r,active=True):
    b=meta(r);root(b,'ROOT_MAIN17_ACTUAL_STORAGE_EDGE_V1','APPROVED_ACTUAL_NODE17_RESOURCE_EDGE_ONLY')
    c,p,proof=probe_closure(b['probe_closure_reference'])
    provider(b,active=active)
    C.need(all(b[k]==p['provider_facts'][k] for k in ('provider_review_reference','publisher_identity_reference','publisher_actual_launch_reference'))
      and b['compute_mount']==p['storage']['mount'] and b['canonical_reference']==p['canonical_reference']
      and b['canonical_expected_frame']==p['canonical_stat'] and b['environment']==p['environment']
      and b['whole_wave_output_reserve_bytes']==C.WAVE_RESERVE
      and b['provider_reserve_bytes']==CAP and b['admin_reserve_bytes']==C.ADMIN and b['quota_reserve_bytes']==200000000000,
      'ACTUAL17_EDGE_AND_ORIGINAL182CAPS_PROVIDER_ADMIN200GB')
    check=meta(b['source_check_reference']);C.need(check['status']=='PASS' and check['tests_run']==3
      and check['failures']==check['errors']==0 and check['source_references']==C.own_sources(),'THREE_ACTUAL_NEW_SOURCE_BOUNDARIES_REQUIRED')
    cp=meta(check['startup_proof_reference']);rq=meta(cp['request_reference']);pl=meta(check['plan_reference'])
    C.need(cp['request']==rq and str(cp['job_id'])==check['job_id'] and pl['mode']=='source3'
      and rq['node']==C.NODE and rq['kind']=='analysis' and rq['cpus']==16 and rq['wall_seconds']==900
      and rq['scope_key']=='sprime_cpu17_resource_source3_v1' and check['plan_reference'] in rq['source_references']
      and rq['execution_argv']==[Q.PY,'-B','-m',C.MODULE+'.test_binding','--plan',check['plan_reference']['path'],
        '--root-preflight',rq['startup_proof_path'],'--output',str(pathlib.Path(b['source_check_reference']['path']).parent)],
      'ACTUAL_SOURCE3_PROOF_PRIMARY_ARGV_REQUIRED')
    account(b['source_check_accounting_reference'],check['job_id'])
    return b


def references(r):
    b=binding(r,active=False);c,p,proof=probe_closure(b['probe_closure_reference'])
    refs=[r,b['probe_closure_reference'],c['receipt_reference'],c['accounting_reference'],meta(c['accounting_reference'])['raw_sacct_reference'],
      p['startup_proof_reference'],p['plan_reference'],proof['request_reference'],b['source_check_reference'],b['source_check_accounting_reference'],
      meta(b['source_check_accounting_reference'])['raw_sacct_reference'],
      meta(b['source_check_reference'])['startup_proof_reference'],meta(meta(b['source_check_reference'])['startup_proof_reference'])['request_reference'],
      meta(b['source_check_reference'])['plan_reference'],b['publisher_identity_reference'],b['publisher_actual_launch_reference']]
    old_ref=G.meta_pin(G.ROOT/'control/sprime_v3_wave2_freeze_stage_v1/wave2_manifest.json');old=meta(old_ref)
    return [*refs,old_ref,old['quota_reuse_review_reference'],*Q.references(b['provider_review_reference']),*C.own_sources()]


class Client:
    def __init__(self,r,request):
        self.reference=r;self.binding=binding(r,active=False);self.request=request
        C.need(request['node']==C.NODE,'REAL17_REQUEST_NOT13_ALIAS');self.publisher_ref=self.binding['publisher_identity_reference'];self.last=None;self.sequence=-1
    def observe(self):
        C.need(meta(self.reference)==self.binding,'SAME_IMMUTABLE_NODE17_EDGE')
        observed=Q.storage_observation();C.need(observed['node']==self.request['node']==C.NODE,'ACTUAL_NODE17_STORAGE')
        p,i=provider(self.binding,active=False)
        view={'compute_mount_by_node':{C.NODE:self.binding['compute_mount']},'marker_reference':p['marker_reference']}
        marker=Q.verify_storage(view,observed,login=False)
        value,evidence=current(self.binding,p,i,validate=False)
        self.last=dict(evidence,cpu_storage=observed,cpu_marker=marker)
        parsed=Q.validate_observation(value,i,self.publisher_ref,p,self.binding['provider_review_reference'],time.time())
        evidence.update(parsed_quota=parsed,free_bytes=parsed['free_bytes'])
        C.need(evidence['identity_reference']==self.publisher_ref and value['sequence']>=self.sequence,'NO_IDENTITY_SWITCH_OR_ROLLBACK')
        self.sequence=value['sequence'];self.last=dict(evidence,cpu_storage=observed,cpu_marker=marker);return self.last


def execution_references(r):
    e=execution(r,active=False);c,p=compatibility(e['compatibility_closure_reference']);proof=meta(p['startup_proof_reference']);plan=meta(p['plan_reference'])
    prep=meta(plan['controls_preparation_reference'])
    refs=[r,e['compatibility_closure_reference'],c['receipt_reference'],c['accounting_reference'],
      meta(c['accounting_reference'])['raw_sacct_reference'],p['startup_proof_reference'],proof['request_reference'],
      p['plan_reference'],plan['controls_preparation_reference'],plan['qa_authority_reference'],
      prep['root_preflight_reference'],meta(prep['root_preflight_reference'])['request_reference']]
    return refs

def quota_reuse(r,refs):
    v=meta(r);root(v,'ROOT_MAIN17_SPRIME_QUOTA_REUSE_V1','APPROVED_RESOURCE_FACTS_ONLY')
    C.need(v['compute_node']==C.NODE and v['provider_source_reference']==refs['quota_provider']
      and v['whole_wave_output_reserve_bytes']==C.WAVE_RESERVE and v['scientific_authority_is_separate'] is True
      and v['N1_population_authority_is_not_Sprime_authority'] is True,'UNCHANGED_SCIENCE_AND_FULL_WAVE_RESERVATION')
    b=binding(v['node17_binding_reference'],active=False)
    C.need(v['provider_review_reference']==b['provider_review_reference']
      and v['publisher_identity_reference']==b['publisher_identity_reference'],'SAME_ACTUAL17_RESOURCE_EPOCH')
    extra=[] if v['execution_authority_reference'] is None else execution_references(v['execution_authority_reference'])
    return v,sys.modules[__name__],[r,*references(v['node17_binding_reference']),*extra]


def compatibility(r):
    c=meta(r,'ROOT_MAIN17_CONTROL16_ACTUAL_CLOSURE_V1');p=meta(c['receipt_reference'])
    C.need(c['status']=='ACTUAL_C0_CONTROL16_EXACT_MATCH' and p['schema']=='MAIN17_ORIGINAL_UFF_CONTROL16_RECEIPT_V1'
      and p['status']=='EXACT16_ORIGINAL_SCIENTIFIC_SHA_MATCH' and p['completed']==p['matched']==16
      and p['errors']==[] and p['population_members_added']==0 and p['production_once_accessed'] is False
      and p['source_references']==C.own_sources()
      and p['whole_LMDB_SHA']=='WHOLE_LMDB_SHA_NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED',
      'ACTUAL16_UFF_NOT_PM7_GOLDEN_OR_ALPHA')
    budget=p['budget'];C.need(budget['stop_new_dispatch'] is None and budget['observation_failure'] is None
      and budget['actual_memory_observations'] and budget['actual_quota_observations']
      and budget['whole_wave_output_reserved_bytes']==C.WAVE_RESERVE and budget['publisher_reserved_bytes']==CAP
      and budget['wall_dispatch_cutoff_seconds']==C.QA_WALL-7200 and budget['natural_drain'] is True and budget['signals_sent_to_science'] is False,'ACTUAL_ORIGINAL_BUDGET_182_RESERVE_UNRELAXED')
    proof=meta(p['startup_proof_reference']);req=meta(proof['request_reference']);plan=meta(p['plan_reference'])
    C.need(req==proof['request'] and req['kind']=='conformer' and req['node']==C.NODE and req['cpus']==16
      and req['scope_key']=='sprime_cpu17_original_uff16_qa_v1' and req['wall_seconds']==C.QA_WALL
      and plan['mode']=='compat16' and plan['source_references']==C.own_sources(),'ACTUAL17_COMPATIBILITY_REQUEST_SOURCE')
    expected=[Q.PY,'-B','-m',C.MODULE+'.compat16','--plan',p['plan_reference']['path'],'--root-preflight',req['startup_proof_path'],
      '--output',str(pathlib.Path(c['receipt_reference']['path']).parent)]
    C.need(req['execution_argv']==expected and p['job_id']==str(proof['job_id']),'REAL_COMPATIBILITY_ALL_OPTIONS_JOB')
    prep=meta(plan['controls_preparation_reference']);expected_rows=PC.prep_metadata(prep)
    C.need(p['control_ids']==prep['molecule_ids'] and len(p['results'])==16
      and {x['molecule_id'] for x in p['results']}==set(expected_rows)
      and len({x['pid'] for x in p['results']})==16
      and p['environment']==binding(p['node17_binding_reference'],active=False)['environment']
      and all(x['task_sha256']==expected_rows[x['molecule_id']]['task_sha256']
        and x['scientific_sha256']==expected_rows[x['molecule_id']]['scientific_sha256_excluding_elapsed_seconds'] for x in p['results']),
      'SAME_FROZEN_ORIGINAL16_TASKS_AND_PACKET_SHA')
    binding(p['node17_binding_reference'],active=False);account(c['accounting_reference'],p['job_id'])
    return c,p


def execution(r,active=True):
    e=meta(r);root(e,'ROOT_MAIN17_SPRIME_EXECUTION_AUTHORITY_V1','APPROVED_ACTUAL17_COMPAT16_REMAINING_ONLY')
    b=binding(e['node17_binding_reference'],active=active);c,p=compatibility(e['compatibility_closure_reference'])
    C.need(p['node17_binding_reference']==e['node17_binding_reference'] and e['allowed_batch_ids']==list(C.MIGRATABLE)
      and e['old_0_through95_new_science_authorized'] is False and e['automatic_retry'] is False
      and e['whole_wave_output_reserve_bytes']==C.WAVE_RESERVE,'ONLY_ORIGINAL96_TO179_AFTER_REAL_COMPATIBILITY')
    return e


def authorize_execution(reuse,request):
    e=execution(reuse['execution_authority_reference'],active=False)
    C.need(e['node17_binding_reference']==reuse['node17_binding_reference'] and request['node']==C.NODE
      and request['scope_key']=='sprime_cpu17_resource_v1_run','ACTUAL_FIXED17_SCIENCE_AUTHORITY')
    return e


def authorize_wave(wave_ref,reuse_ref):
    wave=meta(wave_ref);reuse=meta(reuse_ref)
    C.need(wave['execution_authority_reference']==reuse['execution_authority_reference'],'WAVE_AND_QUOTA_SAME_ROOT_SCIENCE_AUTHORITY')
    return execution(reuse['execution_authority_reference'],active=False)


def formal_source(value,proof,review_path):
    from . import runtime_io as R
    rr=R.input_ref(pathlib.Path(proof['request']['startup_proof_path']),review_path);review=meta(rr)
    root(review,'ROOT_MAIN17_CANONICAL_SOURCE_MAPPING_V1','APPROVED_ACTUAL_CANONICAL_MAPPING')
    b=binding(review['node17_binding_reference']);receipt=meta(value['formal_source_receipt'])
    row=next(x for x in receipt['outputs'] if x['name']=='formal_population');reference=row['reference']
    C.need(review['formal_source_receipt']==value['formal_source_receipt'] and b['canonical_reference']==reference
      and receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED','ORIGINAL_CANONICAL_SOURCE_AUTHORITY')
    R.authorized(proof,[rr,review['node17_binding_reference'],value['formal_source_receipt'],reference])
    path=pathlib.Path(reference['path']);before=path.stat();f=frame(before)
    C.need(f==b['canonical_expected_frame'] and all(f[k]==row['after'][k] for k in ('inode','size','mtime_ns','uid')),
      'ACTUAL17_DEVICE_AND_UNCHANGED_CROSS_MOUNT_STABLE_FIELDS')
    C.pinned(reference);C.need(frame(path.stat())==f,'WHOLE_SHA_CURRENT17_FRAME_STABLE')
    R.write_json_new(R.OUT/'canonical_source_current_mount_identity.json',{'schema':'ACTUAL_MAIN17_CANONICAL_IDENTITY_V1',
      'reference':reference,'current_frame':f,'root_mapping_review':rr,'whole_SHA_verified_on_actual_CPU':True,'device_translation_only':True})
    return reference


def strict_preprobe(proof,session,save):
    from workflows.data_v1_final.conformers.formal_cpu_auto_close_index_v2.admission import future_delay
    reuse,_,_=quota_reuse(session['quota_reuse_review_reference'],C.sources());client=Client(reuse['node17_binding_reference'],proof['request'])
    began=time.monotonic();identity=None
    for attempt in range(2):
        before=time.time()
        try:
            v=client.observe();save({'attempt':attempt,'status':'ORIGINAL_VALIDATION_PASS','cpu_begin':before,'cpu_end':time.time(),'last':client.last});return v
        except Exception as exc:
            now=time.time();last=client.last or {};gap=future_delay(exc,last,now)
            save({'attempt':attempt,'status':'ORIGINAL_VALIDATION_FAILED','error':repr(exc),'cpu_begin':before,'cpu_end':now,'last':last,'eligible_wait':gap})
            if identity is not None:C.need(last.get('identity_reference')==identity,'IDENTITY_CHANGED_DURING_WAIT')
            identity=last.get('identity_reference')
            if attempt or gap is None or time.monotonic()-began>10:raise
            time.sleep(min(2,gap+0.02))
