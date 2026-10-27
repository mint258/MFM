"""Original identities and finite Root resource authorities;no scientific math."""
from workflows.data_v1_final.conformers.formal_cpu_auto_v3.contract import *
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as ORIGINAL
from workflows.data_v1_final.execution.sprime_resource_epoch_v1 import contract as OLD_EPOCH
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
import math,pathlib,time
HERE=Q.REPO/'workflows/data_v1_final/conformers/sprime_multinode_resource_v2'
MODULE='workflows.data_v1_final.conformers.sprime_multinode_resource_v2'
FILES=('__init__.py','contract.py','runtime_io.py','edge.py','probe.py','qa_prepare.py','compat32.py','prepare_batch.py','run_batch.py','close_index.py',
    'close.py','control.py','metadata.py','cutover.py','source_proof.py','test_v1.py','adaptation_manifest.json','README.md')
NODES=tuple('compute-0-%d'%i for i in range(11,20));WAVE_RESERVE=182*CAP
DIAG=BASE/'multinode_resource_v2';META=Q.ROOT/'control/sprime_multinode_resource_v2'
COMPAT_EXTRA_FINALIZATION_HEADROOM=2<<30
def compatibility_minimum_cap(value):return 32*(value['packet_compressed_limit_bytes']+(1<<20))+ADMIN+COMPAT_EXTRA_FINALIZATION_HEADROOM
def own_sources():return [Q.pin(HERE/n) for n in FILES]
def node(value):need(type(value)is str and value in NODES,'EXACT_AUTHORIZED_MAIN_CPU11_19_NODE');return value
def source_inverse_proof():
    from .source_proof import verify
    return verify()
def root(value,schema,status):
    need(value['schema']==schema and value['status']==status and value['reviewer']=='root'
        and value['endpoint']=='202.38.247.57:22' and value['uid']==1278,'EXACT_ROOT_MAIN_RESOURCE_DECISION')
def frame(info):return {'device':info.st_dev,'inode':info.st_ino,'size':info.st_size,'mtime_ns':info.st_mtime_ns,'uid':info.st_uid}
def same_source(origin,actual):
    need(all(origin[k]==actual[k] for k in ('inode','size','mtime_ns','uid')),'SOURCE_FRAME_ONLY_DEVICE_MAY_TRANSLATE')
    need(actual['uid']==1278,'MAIN_SOURCE_OWNER_NOT_ALPHA')
def source_shape(value):
    if value['bytes']!=0:return triple(value)
    need(set(value)=={'path','bytes','sha256'} and type(value['bytes'])is int and value['sha256']=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        and pathlib.Path(value['path']).name=='__init__.py' and Q.REPO in pathlib.Path(value['path']).parents,'EMPTY_SOURCE_INIT_ONLY_NO_ZERO_DATA')
    return value
def scope(stage,config_reference):return ORIGINAL.scope(stage,config_reference)
def parameters(mode,node_name):
    node(node_name);need(mode in ('source3','probe','qa_prepare','compat32'),'EXACT_INDEPENDENT_DIAGNOSTIC_MODE')
    return {'mode':mode,'node':node_name,'cpus':16,'new_QM_calls':0,'production_once_accessed':False,'new_training_members':0,
        'scientific_recipe_or_numeric_tolerances_changed':False,'compatibility_controls':32 if mode in ('qa_prepare','compat32') else 0,
        'source3_before_DATA_or_native':True,'whole_wave_reserve_bytes':WAVE_RESERVE,'quota_reserve_bytes':200000000000,
        'deferred_original_baseline_locators':'ONLY_PRODUCER_PINNED_COMPLETE334_AUTHORITY_READ_ON_CPU',
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','automatic_retry':False}
def binding(reference,*,active=False,require_compat=False):
    from . import edge
    return edge.binding(reference,active=active,require_compat=require_compat)
def epoch(reference,*,active=False):
    e=read(reference);root(e,'ROOT_MAIN_MULTINODE_SPRIME_EPOCH_V2','APPROVED_FINITE_RESOURCE_EPOCH')
    need(e['original_manifest_reference']==OLD_EPOCH.V.MANIFEST and e['original_plan_reference']==OLD_EPOCH.V.PLAN
        and e['own_source_references']==own_sources() and e['maximum_seconds']<=72000 and type(e['maximum_seconds'])is int and e['maximum_seconds']>0
        and e['whole_wave_output_reserve_bytes']==WAVE_RESERVE and e['original_batch_ids']==list(OLD_EPOCH.G.BATCHES)
        and e['production_once_namespace_changed'] is False and e['automatic_retry_or_lease_renewal'] is False,'EXACT_ORIGINAL179_FINITE20H_NO_ONCE_CHANGE')
    limits=e['maximum_science_per_node'];need(limits and set(limits)<=set(NODES) and all(type(v)is int and 1<=v<=16 for v in limits.values()),'EXPLICIT_NODE_LOCAL_CONCURRENCY_LIMITS')
    need(type(e['maximum_nonterminal_science'])is int and 1<=e['maximum_nonterminal_science']<=sum(limits.values())
        and type(e['maximum_nonterminal_aux'])is int and 1<=e['maximum_nonterminal_aux']<=9
        and type(e['maximum_owned_data_run_pending'])is int and e['maximum_owned_data_run_pending']>=1,'EXPLICIT_GLOBAL_LIMITS_NOT_IMPLIED_BY_ALLOWLIST')
    from . import edge
    publisher_expiries=[]
    for n,r in e['node_binding_references'].items():
        b=binding(r,active=active);need(n in limits and b['node']==n,'ACTUAL_PER_NODE_STORAGE_BINDING_REQUIRED')
        _,identity=edge.provider(b,active=False);publisher_expiries.append(identity['expires_unix_seconds'])
        edge.compatibility(e['node_compat32_closure_references'][n],r)
    need(set(e['node_binding_references'])==set(limits),'ALL_ENABLED_NODES_MUST_HAVE_REAL_C0_BINDINGS')
    need(e['allowed_initial_batch_ids'] and len(set(e['allowed_initial_batch_ids']))==len(e['allowed_initial_batch_ids'])
        and set(e['allowed_initial_batch_ids'])<=set(OLD_EPOCH.G.BATCHES),'ONLY_EXPLICIT_ORIGINAL_INITIAL_BATCHES_NO_RETRY_DOMAIN')
    for bid,decision in e.get('preserved_HOLD_dispositions',{}).items():
        need(bid in OLD_EPOCH.G.BATCHES and bid not in e['allowed_initial_batch_ids'] and decision['action']=='KEEP_HOLD_NO_RETRY_CONTINUE_INDEPENDENT',
            'HOLD_BATCH_CANNOT_BE_REENABLED_BY_RESOURCE_EPOCH')
        _,_,parents=OLD_EPOCH.G.account(pathlib.Path(decision['accounting_reference']['path']),[str(decision['job_id'])])
        p=parents[str(decision['job_id'])];need(p['state']==decision['state'] and p['state']!='COMPLETED','ACTUAL_SPECIFIC_FAILED_PARENT_DISPOSITION')
    need(set(e['maximum_aux_per_node'])==set(limits) and all(type(v)is int and 1<=v<=16 for v in e['maximum_aux_per_node'].values())
        and type(e['minimum_reserved_free_CPU_total'])is int and e['minimum_reserved_free_CPU_total']>=0,'EXPLICIT_AUX_AND_CPU_RESERVE_LIMITS')
    reservations=read(e['whole_wave_reservation_inventory_reference']);root(reservations,'ROOT_ACTUAL_SPRIME_MULTINODE_OUTPUT_RESERVATIONS_V2','APPROVED_CURRENT_ACCOUNT_SCOPE')
    need(reservations['original179_science_caps_unchanged'] is True and reservations['failed_and_opaque_outputs_retained'] is True
        and reservations['independent_other_data_task_caps_retained'] is True and reservations['whole_wave_upper_bound_bytes']==WAVE_RESERVE
        and sum(r['reserved_or_actual_closed_bytes'] for r in reservations['items'])<=WAVE_RESERVE
        and all(type(r['reserved_or_actual_closed_bytes'])is int and r['reserved_or_actual_closed_bytes']>=0 for r in reservations['items']),
        'CLOSED_ACTUAL_PLUS_REMAINING_SCIENCE_QA_METADATA_PROVIDER_WITHIN_ORIGINAL182CAPS')
    cut=read(e['cutover_reference']);need(cut['schema']=='ACTUAL_MAIN_SPRIME_MULTINODE_CUTOVER_V2' and cut['status']=='OLD_METADATA_STOPPED_LOCKS_OBSERVED_ADOPTION_PENDING_ROOT'
        and cut['old_controller_reference']==e['old_controller_identity_reference'] and cut['production_jobs_signalled']==0,'REAL_OLD_METADATA_STOP_AND_MANUAL_ADOPTION_REQUIRED')
    adoption=read(e['adoption_reference']);root(adoption,'ROOT_SPRIME_MULTINODE_ACTUAL_ADOPTION_V2','APPROVED_ALL_ACTUAL_REGISTRATIONS_AFTER_CUTOVER')
    need(adoption['cutover_reference']==e['cutover_reference'] and adoption['old_latest_state_reference']==cut['old_latest_state_reference']
        and adoption['all_179_stage_paths_reconciled_after_old_stop'] is True and adoption['running_science_untouched'] is True
        and adoption['pending_actions_only_explicit_keep_existing'] is True,'EXACT_POSTSTOP_REGISTRY_AND_PENDING_ADOPTION')
    for field in ('deadline_unix_seconds','started_unix_seconds'):need(type(e[field])in (int,float) and math.isfinite(e[field]),'FINITE_ABSOLUTE_EPOCH_TIMES')
    need(0<e['deadline_unix_seconds']-e['started_unix_seconds']<=e['maximum_seconds'],'FIXED20H_EPOCH_NO_AUTORENEW')
    need(e['deadline_unix_seconds']<=min(publisher_expiries)-300,'DECLARED_DEADLINE_WITHIN_ACTUAL_PUBLISHER_EXPIRY_NO_SILENT_EXTENSION')
    if active:need(e['started_unix_seconds']<=time.time()<e['deadline_unix_seconds'],'NOT_YET_ACTIVE_OR_EXPIRED_RESOURCE_EPOCH_NO_MORE_DISPATCH')
    return dict(e,_reference=reference)

def authorize_slot(plan,proof,out):
    """Original approved job row stays byte-identical;only new actual resource binding changes."""
    from . import runtime_io as R
    request=proof['request'];reuse=read(R.SESSION['quota_reuse_review_reference']);e=epoch(reuse['epoch_reference'],active=False)
    matches=[j for j in plan['jobs'] if j['job_name']==request['job_name']];need(len(matches)==1,'ORIGINAL_UNIQUE_JOB_SLOT')
    slot=matches[0];need(slot['batch_id'] in e['allowed_initial_batch_ids'] and request['node'] in e['node_binding_references']
        and reuse['node_binding_reference']==e['node_binding_references'][request['node']] and request['cpus']==slot['cpus']==16
        and request['wall_seconds']==slot['wall_seconds']<=172800 and str(out)==slot['output_root']
        and slot['whole_output_cap_bytes']==CAP,'EXACT_OLD_SLOT_NEW_REVIEWED_NODE_NOT_NEW_SCIENCE')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import parse_scontrol_jobs
    raw=Q.query(['scontrol','show','job','--oneliner']);names={j['job_name'] for j in plan['jobs']}
    running=[j for j in parse_scontrol_jobs(raw) if j.get('JobName',j.get('Name')) in names and j.get('JobState')=='RUNNING']
    need(len(running)<=e['maximum_nonterminal_science'] and sum(j.get('NodeList')==request['node'] for j in running)<=e['maximum_science_per_node'][request['node']],
        'ACTUAL_RUNTIME_GLOBAL_AND_NODE_SCIENCE_CONCURRENCY_LIMITS')
    return slot,{'resource_epoch_reference':reuse['epoch_reference'],'node_binding_reference':reuse['node_binding_reference'],
        'original_slot_node':slot['node'],'actual_node':request['node'],'same_original_job_slot_and_output':True,'actual_running_wave_jobs':raw}
