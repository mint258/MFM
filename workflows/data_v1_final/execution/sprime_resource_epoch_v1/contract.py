"""Finite Main resource metadata only; unchanged scientific primaries and ledgers."""
from __future__ import annotations
import copy, math, pathlib, time
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as F, runtime_io as R
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
from workflows.data_v1_final.execution.sprime_wave2_controller_v3 import controller as V
from workflows.data_v1_final.execution.sprime_wave2_controller_v4 import controller as W
from workflows.data_v1_final.execution.sprime_wave2_controller_v4.recovery import Recovery, exact
from workflows.data_v1_final.execution.sprime_wave2_recovery96_v1 import contract as K

HERE=pathlib.Path(__file__).absolute().parent
FILES=('__init__.py','contract.py','metadata.py','probe.py','controller.py','test_contract.py','README.md')
EPOCH_SCHEMA='ACTUAL_FINITE_SPRIME_RESOURCE_EPOCH_V1'
BIND_SCHEMA='ROOT_EXPLICIT_SPRIME_RESOURCE_EPOCH_BINDING_V1'
CONTROLLER_SCHEMA='ROOT_FINITE_SPRIME_RESOURCE_EPOCH_CONTROLLER_REVIEW_V1'
PROBE_KEY='sprime_new_resource_epoch_cpu13_probe_v1'
PROBE_CAP=128<<20
FUTURE=tuple('batch-%05d'%i for i in range(97,180))
PROBE_PARAMS={'new_resource_epoch_required':True,'original_Budget_and_Client':True,'scientific_records':0,
 'new_UFF_calls':0,'new_QM_calls':0,'scientific_bodies_read':0,'whole_wave_reserve_182_caps':True,
 'quota_freshness_seconds':120,'CPU13_only':True,'signals_sent':False,'request_kind':'analysis'}


def sources():return [G.meta_pin(HERE/n) for n in FILES]


def own_path(path,base=G.ROOT/'control',fresh=False):
    p=pathlib.Path(path)
    F.need(p.is_absolute() and base in p.parents and '..' not in p.parts
      and not any(q.is_symlink() for q in (p,*p.parents)),'OWN_LITERAL_EPOCH_METADATA_PATH')
    if fresh:F.need(not p.exists(),'FRESH_METADATA_OUTPUT_NO_REGENERATION')
    return p


def refread(reference,schema=None):
    F.need(G.meta_pin(reference['path'])==reference,'IMMUTABLE_EPOCH_METADATA_PIN')
    value=G.metadata(reference['path'],schema)[1]
    return value


def root(value,schema,status):
    F.need(value.get('schema')==schema and value.get('status')==status and value.get('reviewer')=='root'
      and value.get('endpoint')=='202.38.247.57:22' and value.get('uid')==1278,'EXPLICIT_ACTUAL_ROOT_EPOCH_REVIEW')


def replace_quota(argv,old_path,new_path):
    out=list(argv)
    F.need(out.count('--quota-reuse-review')==1,'ONE_EXPLICIT_QUOTA_OPTION_REQUIRED')
    i=out.index('--quota-reuse-review')
    F.need(i+1<len(out) and out[i+1]==old_path,'EXACT_OLD_RESOURCE_OPTION_REQUIRED')
    out[i+1]=new_path
    return out


def same_provider_scope(old,new):
    # The only policy delta is the fresh publisher directory and review provenance.
    mutable={'publisher_output_dir','root_scope_notes','previous_provider_review_reference'}
    F.need(all(new.get(k)==v for k,v in old.items() if k not in mutable),'ORIGINAL_PROVIDER_SCOPE_POLICY_CHANGED')
    F.need(new['publisher_output_dir']!=old['publisher_output_dir'],'NEW_INDEPENDENT_PROVIDER_DIRECTORY_REQUIRED')
    F.need(new['maximum_runtime_seconds']==86400 and new['maximum_age_seconds']==120
      and new['refresh_seconds']==30 and new['cpu_poll_seconds']==60
      and new['quota_reserve_bytes']==200000000000,'ORIGINAL_FINITE_PROVIDER_LIMITS_UNCHANGED')


def deadline(value,identity,now):
    F.need(type(value) in (int,float) and math.isfinite(value) and now<value<=identity['expires_unix_seconds']-300,
      'FIXED_ABSOLUTE_DEADLINE_WITH_ORIGINAL300_SECOND_RESERVE')
    return value


def live_metadata(epoch):
    review_ref=epoch['provider_review_reference'];review=Q.load_review(review_ref)
    provider=pathlib.Path(review['publisher_output_dir'])
    raw,_=Q.small(provider/'latest.json');import json
    latest=json.loads(raw)
    F.need(latest['schema']==Q.LATEST_SCHEMA and latest['review_reference']==review_ref
      and latest['identity_reference']==epoch['publisher_identity_reference'],'EXACT_NEW_EPOCH_CURRENT_POINTER')
    snapshot_ref=latest['snapshot_reference']
    import re
    F.need(pathlib.Path(snapshot_ref['path']).parent==provider
      and re.fullmatch(r'observation_[0-9]{6}\.json',pathlib.Path(snapshot_ref['path']).name),'BOUNDED_ORIGINAL_SNAPSHOT_LOCATOR')
    identity=refread(epoch['publisher_identity_reference'],Q.IDENTITY_SCHEMA)
    snapshot=Q.pinned(snapshot_ref)
    Q.validate_observation(snapshot,identity,epoch['publisher_identity_reference'],review,review_ref,time.time())
    return identity,snapshot_ref


def epoch_inputs(reference,active=True):
    e=refread(reference,EPOCH_SCHEMA)
    F.need(e['status']=='ACTUAL_PUBLISHER_BOUND_CPU_PROBE_STILL_REQUIRED'
      and e['original_manifest_reference']==V.MANIFEST and e['original_plan_reference']==V.PLAN
      and e['source_references']==sources() and e['reused_source_references']==V.sources()+W.extra_sources()
      and e['whole_wave_output_reserve_bytes']==G.WAVE_RESERVE
      and e['provider_output_reserve_bytes']==64<<20 and e['admin_output_reserve_bytes']==F.ADMIN
      and e['quota_reserve_bytes']==200000000000 and e['no_auto_renew'] is True,'EXACT_UNCHANGED_FINITE_RESOURCE_EPOCH')
    b=refread(e['root_binding_reference']);root(b,BIND_SCHEMA,'APPROVED_NEW_FINITE_RESOURCE_FACTS_ONLY')
    for k in ('provider_review_reference','publisher_identity_reference','publisher_actual_launch_reference','first_healthy_snapshot_reference'):
        F.need(e[k]==b[k],'EPOCH_AND_ROOT_ACTUAL_PUBLISHER_BINDING_DIFFER');refread(e[k])
    original_manifest,_,_,_=V.fixed_inputs()
    F.need(e['previous_quota_reuse_review_reference']==b['previous_quota_reuse_review_reference']
      ==original_manifest['quota_reuse_review_reference'],'EXACT_OLD_RESOURCE_HISTORY_RETAINED')
    old_reuse=refread(e['previous_quota_reuse_review_reference'])
    same_provider_scope(refread(old_reuse['provider_review_reference']),Q.load_review(e['provider_review_reference']))
    reuse=refread(e['quota_reuse_review_reference'])
    R.quota_reuse(e['quota_reuse_review_reference'],F.sources())
    F.need(reuse['provider_review_reference']==e['provider_review_reference']
      and reuse['publisher_identity_reference']==e['publisher_identity_reference']
      and reuse['provider_actual_launch_reference']==e['publisher_actual_launch_reference']
      and reuse['resource_epoch_root_binding_reference']==e['root_binding_reference']
      and reuse['whole_wave_output_reserve_bytes']==G.WAVE_RESERVE,'EXACT_NEW_QUOTA_REUSE_CHAIN')
    identity=refread(e['publisher_identity_reference'],Q.IDENTITY_SCHEMA)
    if active:identity,_=live_metadata(e)
    return e,identity


def add_epoch(refs,reference,e):
    refs.add(reference)
    for k in ('root_binding_reference','provider_review_reference','publisher_identity_reference','publisher_actual_launch_reference',
              'first_healthy_snapshot_reference','quota_reuse_review_reference','previous_quota_reuse_review_reference',
              'original_manifest_reference','original_plan_reference'):
        refs.add(e[k])
    for item in [*sources(),*V.sources(),*W.extra_sources()]:refs.add(item)
    for item in Q.references(e['provider_review_reference']):refs.add(item)
    manifest,plan,old_identity,_=V.fixed_inputs()
    old_quota=refread(manifest['quota_reuse_review_reference'])
    for item in (manifest['quota_reuse_review_reference'],manifest['mapping_review_reference'],plan['draft'],plan['root_review'],
      plan['config'],old_identity,old_quota['provider_review_reference'],old_quota['provider_actual_launch_reference']):refs.add(item)


def healthy_probe_budget(b,identity_reference):
    F.need(b['stop_new_dispatch'] is None and b['observation_failure'] is None
      and b['signals_sent_to_science'] is False and b['natural_drain'] is True
      and b['whole_wave_output_reserved_bytes']==G.WAVE_RESERVE and b['publisher_reserved_bytes']==64<<20
      and b['actual_memory_observations'] and b['actual_quota_observations'],'UNCHANGED_HEALTHY_ORIGINAL_BUDGET_REQUIRED')
    F.need(all(r['identity_reference']==identity_reference for r in b['actual_quota_observations']),
      'OLD_OR_MIXED_EPOCH_PROBE_REJECTED')


def probe_closure(reference,epoch_reference):
    return validate_probe_closure(refread(reference,'ACTUAL_NEW_SPRIME_EPOCH_CPU13_PROBE_CLOSURE_V1'),epoch_reference)


def validate_probe_closure(c,epoch_reference):
    F.need(c['status']=='ACTUAL_C0_HEALTHY_NEW_EPOCH_PROBE_CLOSED' and c['epoch_reference']==epoch_reference
      and c['source_references']==sources(),'ACTUAL_NEW_EPOCH_CPU_PROBE_REQUIRED')
    report=refread(c['report_reference']);proof=refread(c['startup_proof_reference'])
    request=refread(proof['request_reference'])
    F.need(proof['request']==request and c['request_reference']==proof['request_reference']
      and request['kind']=='analysis' and request['node']=='compute-0-13' and request['cpus']==16
      and request['wall_seconds']==900 and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and proof['uid']==1278 and request['scope_key']==PROBE_KEY and request['scope_parameters']==PROBE_PARAMS,
      'EXACT_REAL_CPU13_NEW_EPOCH_PROBE_IDENTITY')
    e,_=epoch_inputs(epoch_reference,active=False)
    F.need(report['schema']=='ACTUAL_NEW_SPRIME_RESOURCE_EPOCH_CPU_PROBE_V1'
      and report['status']=='HEALTHY_ORIGINAL_RESOURCE_OBSERVATION_NOT_SCIENTIFIC_SUCCESS'
      and report['epoch_reference']==epoch_reference and report['job_id']==str(proof['job_id'])
      and report['uid']==1278 and report['node']=='compute-0-13' and report['source_references']==sources()
      and report['startup_proof_reference']==c['startup_proof_reference']
      and report['new_UFF_QM_calls']==0 and report['scientific_bodies_read']==0
      and report['science_primary_or_load_science_called'] is False and report['failure'] is None,'NEW_CHAIN_PROBE_REPORT_ONLY')
    cfg=refread(report['config_reference'],'SPRIME_NEW_RESOURCE_EPOCH_CPU_PROBE_CONFIG_V1')
    F.need(cfg['epoch_reference']==epoch_reference and cfg['quota_reuse_review_reference']==e['quota_reuse_review_reference']
      and cfg['original_config_reference']==V.fixed_inputs()[0]['config_reference'],'EXACT_PROBE_CONFIG_RESOURCE_CHAIN')
    expected=[G.PY,'-B','-m','workflows.data_v1_final.execution.sprime_resource_epoch_v1.probe',
      '--config',report['config_reference']['path'],'--startup-proof',request['startup_proof_path']]
    F.need(request['execution_argv']==expected and proof['request_reference']==c['request_reference']
      and pathlib.Path(c['report_reference']['path'])==pathlib.Path(cfg['output_directory'])/'resource_probe.json',
      'ACTUAL_PROBE_FULL_ARGV_OUTPUT_BINDING')
    allowed=request['source_references']+request['data_references']
    F.need(all(r in allowed for r in [epoch_reference,report['config_reference'],e['quota_reuse_review_reference'],*sources()]),
      'EXACT_SOURCE_AND_EPOCH_REQUEST_DECLARATION')
    began=report['cpu_observation_begin_unix_seconds'];ended=report['cpu_observation_end_unix_seconds']
    F.need(type(began) in (int,float) and type(ended) in (int,float) and math.isfinite(began) and math.isfinite(ended)
      and 0<=ended-began<=900,'ACTUAL_CPU_OBSERVATION_TIME_WINDOW')
    b=report['original_budget_report']
    healthy_probe_budget(b,e['publisher_identity_reference'])
    for row in b['actual_quota_observations']:
        F.need(row['identity_reference']==e['publisher_identity_reference'],'OLD_OR_MIXED_EPOCH_PROBE_REJECTED')
        snapshot=Q.pinned(row['snapshot_reference']);identity=refread(e['publisher_identity_reference'])
        Q.validate_observation(snapshot,identity,e['publisher_identity_reference'],Q.load_review(e['provider_review_reference']),
          e['provider_review_reference'],ended)
    _,_,parents=G.account(pathlib.Path(c['accounting_reference']['path']),[str(proof['job_id'])],c0=[str(proof['job_id'])])
    F.need(parents[str(proof['job_id'])]['node']=='compute-0-13','ACTUAL_PROBE_NODE13_ACCOUNTING')
    F.need(refread(c['accounting_reference'])['raw_sacct_reference']==c['raw_accounting_reference'],'ACTUAL_PROBE_RAW_ACCOUNTING_PIN')
    return c


def add_probe(refs,reference,c):
    refs.add(reference)
    for k in ('report_reference','startup_proof_reference','request_reference','accounting_reference','raw_accounting_reference'):
        refs.add(c[k])


def actual_tests(reference,expected_sources,count):
    t=refread(reference)
    F.need(t['status']=='PASS' and t['tests_run']==count and t['failures']==t['errors']==0
      and t['source_references']==expected_sources,'ACTUAL_EXACT_NEW_PURE_TEST_SOURCE_EVIDENCE')
    _,_,parents=G.account(pathlib.Path(t['accounting_reference']['path']),[str(t['job_id'])],c0=[str(t['job_id'])])
    return t


def controller_inputs(reference,active=True):
    return validate_controller_value(refread(reference),active=active)


def validate_controller_value(review,active=True):
    root(review,CONTROLLER_SCHEMA,'APPROVED_FINITE_METADATA_CONTROLLER')
    er=review['resource_epoch_reference'];e,identity=epoch_inputs(er,active=active)
    pc=probe_closure(review['probe_closure_reference'],er)
    F.need(review['manifest_reference']==V.MANIFEST and review['plan_reference']==V.PLAN
      and review['source_references']==V.sources() and review['continuation_source_references']==W.extra_sources()
      and review['resource_epoch_source_references']==sources() and review['publisher_identity_reference']==e['publisher_identity_reference']
      and review['maximum_nonterminal_science']==2 and review['maximum_nonterminal_aux']==1
      and review['maximum_owned_data_run_pending']==4 and review['stop_before_publisher_expiry_seconds']==300
      and review['allowed_future_batch_ids']==list(FUTURE)
      and review['authorize_exact_metadata_stages_for_listed_future_batches'] is True
      and review['automatic_retry'] is False and review['publisher_auto_renew'] is False,'EXACT_BOUNDED_NEW_RESOURCE_CONTROLLER_SCOPE')
    if active:deadline(review['deadline_unix_seconds'],identity,time.time())
    else:F.need(review['deadline_unix_seconds']<=identity['expires_unix_seconds']-300,'ORIGINAL300_SECOND_DEADLINE_RESERVE')
    prior=refread(review['supersedes_review_reference']);W.prior_review(prior)
    F.need(review['adoption_reference']==prior['adoption_reference'],'ALL_ORIGINAL_MANUAL_ADOPTIONS_RETAINED')
    recovery=Recovery(review['continuation_repair_map_reference'],review,prior)
    # New96 is already actually closed; neither old epoch nor the old2070 can authorize future97.
    F.need(recovery.bundle['resource_epoch_reference']==er
      and recovery.bundle['probe_closure_reference']==review['probe_closure_reference'],'ACTUAL96_SAME_NEW_RESOURCE_EPOCH')
    for key in ('replacement96_run_registration','replacement96_close_registration'):
        req=refread(recovery.value[key]['request_reference']);argv=req['execution_argv']
        F.need(argv.count('--quota-reuse-review')==1 and argv[argv.index('--quota-reuse-review')+1]==e['quota_reuse_review_reference']['path']
          and er in req['source_references'],'ACTUAL96_REGISTERED_NEW_EPOCH_RESOURCE_OPTIONS')
    actual_tests(review['pure_recovery_cpu_test_reference'],[V.pin(W.HERE/n) for n in W.FILES],3)
    actual_tests(review['pure_epoch_cpu_test_reference'],sources(),3)
    return review,e,identity,pc,recovery
