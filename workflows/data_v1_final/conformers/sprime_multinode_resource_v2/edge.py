"""Actual per-node shared-storage edge;original login quota validation unchanged."""
import os,pathlib,socket,sys,time
from . import contract as C
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1.quota_edge import provider,current
from workflows.data_v1_final.execution.sprime_wave2_metadata_v1 import generate as G
CAP=Q.CAP
def meta(ref):
    C.need(not G.is_data(ref['path']) and G.meta_pin(ref['path'])==ref,'REAL_SMALL_METADATA_ONLY_NOT_DATA');return C.read(ref)
def account(reference,jid,node):
    C.need(G.meta_pin(reference['path'])==reference,'ACTUAL_ACCOUNTING_PIN')
    _,a,rows=G.account(pathlib.Path(reference['path']),[str(jid)],c0=[str(jid)])
    C.need(rows[str(jid)]['node']==node and rows[str(jid)]['alloc_cpus']==16,'ACTUAL_NODE_CPU16_C0_ACCOUNTING');return a['raw_sacct_reference']
def environment():
    import platform,numpy,rdkit,torch,pyarrow
    return {'python':platform.python_version(),'rdkit':rdkit.__version__,'numpy':numpy.__version__,'torch':torch.__version__,'pyarrow':pyarrow.__version__}
def source3(reference):
    closure=meta(reference);C.need(closure['schema']=='ROOT_ACTUAL_SPRIME_RESOURCE_SOURCE3_CLOSURE_V2' and closure['status']=='ACTUAL_C0_SOURCE3_ONLY','REAL_SOURCE3_TERMINAL_CLOSURE')
    t=meta(closure['receipt_reference']);C.need(t['schema']=='ACTUAL_SPRIME_MULTINODE_SOURCE3_V2' and t['status']=='PASS' and t['tests_run']==3 and not any(t[k] for k in ('failures','errors','skips','expected_failures','unexpected_successes'))
        and t['source_references']==C.own_sources() and t['scientific_DATA_or_UFF_QM_called'] is False,'ACTUAL_NEW_SOURCE3_CPU_REQUIRED')
    proof=meta(t['startup_proof_reference']);request=meta(proof['request_reference'])
    C.need(request==proof['request'] and str(proof['job_id'])==t['job_id'] and request['node']==t['node'] and proof['uid']==1278
        and request['scope_key']=='sprime_multinode_resource_source3_v2' and request['cpus']==16,'ACTUAL_SOURCE3_PRIMARY_IDENTITY')
    items=t['synthetic_IO_evidence'];C.need(len(items)==2 and {r['name'] for r in items}=={'all32_success','first_wave_failure'},'ACTUAL_MULTIWORKER_IO_NOT_AST_ONLY')
    observed={r['name']:r for r in items}
    for name,want in (('all32_success',(32,0,32,32,0)),('first_wave_failure',(15,1,16,16,1))):
        row=observed[name];C.need((row['results'],row['errors'],row['collection']['submitted_count'],row['starts'],row['reservations_retained'])==want
            and row['science_worker_init_called'] is False and row['new_UFF_QM_calls']==0,'ACTUAL_SYNTHETIC_SOURCE3_IO_CENSUS')
    account(closure['accounting_reference'],t['job_id'],t['node']);return t
def validate_probe(probe,proof):
    node=C.node(probe['node']);storage=probe['storage'];parsed=Q.parse_mount(storage['findmnt'],storage['df'])
    C.need(proof['request']['node']==node and probe['uid']==proof['uid']==1278 and probe['job_id']==str(proof['job_id'])
        and probe['scientific_DATA_bodies_opened']==0 and probe['new_UFF_QM_calls']==0,'REAL_CPU_NODE_PROBE_NOT_RELABELLED')
    C.need(storage['node']==node and storage['uid']==1278 and storage['endpoint']=='202.38.247.57:22'
        and parsed==storage['mount_selection'] and parsed['active_mount']==storage['mount']
        and parsed['df_active_row']['total_kib']==Q.MAPPING_FILESYSTEM_TOTAL_KIB,'ACTUAL_SAME_SHARED_FILESYSTEM_BY_RAW_FINDMNT_DF')
    C.need(parsed['active_mount']=={'target':'/share/home','source':'nfs:/share/home','fstype':'nfs4','fsroot':'/'}
        and probe['nfs_addresses']==probe['sonmi_addresses']==['10.1.1.1'],'ACTUAL_SHARED_EXPORT_AND_DNS_NOT_ALIAS')
    C.need(all(probe['marker']['stat'][k]==v for k,v in Q.MARKER_IDENTITY.items()) and probe['marker']['reference']==probe['provider_facts']['marker_reference'],'ACTUAL_SHARED_MARKER_IDENTITY')
    C.need(probe['source_references']==C.own_sources() and probe['environment']['rdkit']=='2025.09.5','EXACT_SOURCE_AND_ENV_PROBE')
    return parsed['active_mount']
def own_probe_binding(reference,*,active=False,require_compat=False):
    b=meta(reference);C.root(b,'ROOT_MAIN_SPRIME_NODE_RESOURCE_EDGE_V2','APPROVED_ACTUAL_NODE_RESOURCE_EDGE_ONLY');node=C.node(b['node'])
    baseline=source3(b['source3_reference']);closure=meta(b['probe_closure_reference']);p=meta(closure['receipt_reference']);proof=meta(p['startup_proof_reference'])
    C.need(closure['schema']=='ROOT_ACTUAL_SPRIME_NODE_PROBE_CLOSURE_V2' and closure['status']=='ACTUAL_C0_SOURCE_STORAGE_ENV_ONLY'
        and p['schema']=='ACTUAL_MAIN_SPRIME_NODE_PROBE_V2' and validate_probe(p,proof)==b['compute_mount']
        and p['canonical_reference']==b['canonical_reference'] and p['canonical_stat']==b['canonical_expected_frame']
        and p['environment']==b['environment'] and b['source_references']==C.own_sources(),'ACTUAL_SAME_NODE_SOURCE_STORAGE_BINDING')
    C.need(b['environment']==baseline['environment'],'ALL_NODE_VERSIONS_MATCH_REAL_BASELINE_SOURCE3_ENVIRONMENT')
    account(closure['accounting_reference'],p['job_id'],node)
    C.need(b['whole_wave_output_reserve_bytes']==C.WAVE_RESERVE and b['quota_reserve_bytes']==200000000000
        and b['provider_reserve_bytes']==CAP and b['admin_reserve_bytes']==C.ADMIN,'ORIGINAL182CAPS_200GB_NO_NEW_MEMORY_GATE')
    C.need(all(b[k]==p['provider_facts'][k] for k in ('provider_review_reference','publisher_identity_reference','publisher_actual_launch_reference')),'PROBE_AND_BINDING_SAME_ACTUAL_PUBLISHER')
    provider(b,active=active)
    if require_compat:compatibility(b['compat32_closure_reference'],reference)
    return b
def binding(reference,*,active=False,require_compat=False):
    b=meta(reference)
    if 'legacy_node_binding_reference' not in b:return own_probe_binding(reference,active=active,require_compat=require_compat)
    from workflows.data_v1_final.conformers.sprime_multinode_resource_v1 import edge as L,contract as LC
    C.root(b,'ROOT_MAIN_SPRIME_NODE_RESOURCE_EDGE_V2','APPROVED_ACTUAL_NODE_RESOURCE_EDGE_ONLY')
    old=L.binding(b['legacy_node_binding_reference'],active=active);baseline=source3(b['source3_reference'])
    C.need(b['resource_probe_origin_namespace']=='sprime_multinode_resource_v1' and b['legacy_source_context_references']==LC.own_sources()
        and b['source_references']==C.own_sources(),'ACTUAL_OLD_SOURCE18_PROBE_CONTEXT_NOT_RELABELLED_AS_V2')
    for ref in b['legacy_source_context_references']:C.pinned(ref,2<<20)
    for k in ('node','probe_closure_reference','provider_review_reference','publisher_identity_reference','publisher_actual_launch_reference','compute_mount',
              'canonical_reference','canonical_expected_frame','environment','whole_wave_output_reserve_bytes','quota_reserve_bytes','provider_reserve_bytes','admin_reserve_bytes'):
        C.need(b[k]==old[k],'UNCHANGED_REAL_V1_RESOURCE_PROBE_FACT:'+k)
    C.need(b['environment']==baseline['environment'],'CURRENT_V2_SOURCE3_ENV_MATCHES_REUSED_ACTUAL_V1_NODE_ENV')
    if require_compat:compatibility(b['compat32_closure_reference'],reference)
    return b

def exclusion_facts(value):
    """Small start/account/proof evidence only;never task/packet/LMDB bodies."""
    from workflows.data_v1_final.conformers.sprime_multinode_resource_v1 import edge as L,contract as LC
    _,prep=L.preparation_closure(value['original_qa_preparation_closure_reference']);expected={r['molecule_id']:r for r in prep['expected']}
    C.need(prep['eligible_count']==49 and len(expected)==32,'ACTUAL_OLD49_ELIGIBLE32_PREPARED_NOT_NEW_POPULATION')
    runs=value['old_failed_runs'];C.need(len(runs)==3 and {str(r['job_id']) for r in runs}=={'4524501','4524502','4524503'},'EXACT_THREE_OBSERVED_FAILED_COMPAT_PARENTS')
    sets=[]
    for run in runs:
        _,_,parents=G.account(pathlib.Path(run['accounting_reference']['path']),[str(run['job_id'])]);p=parents[str(run['job_id'])]
        C.need(G.meta_pin(run['accounting_reference']['path'])==run['accounting_reference'] and p['state']=='FAILED'
            and p['alloc_cpus']==16 and p['node']==C.node(run['node']),'ACTUAL_FAILED16CPU_PARENT_COST_AND_NODE')
        proof=meta(run['startup_proof_reference']);request=meta(proof['request_reference']);C.need(request==proof['request']
            and str(proof['job_id'])==str(run['job_id']) and proof['uid']==1278 and request['node']==run['node']
            and request['scope_key']=='sprime_multinode_resource_compat32_v1' and request['cpus']==16,'OLD_STARTUP_IDENTITY_NOT_A_NEW_V2_SUCCESS')
        C.need(all(r in request['source_references'] for r in LC.own_sources()),'EXACT_FAILED_V1_SOURCE18')
        output=pathlib.Path(run['output_directory']);argv=request['execution_argv'];C.need(argv.count('--output')==1 and argv[argv.index('--output')+1]==str(output),'FAILED_ACTUAL_OUTPUT_ARGV')
        mids=set();refs=run['start_references'];C.need(len(refs)==16,'EXACT16_DURABLE_START_METADATA_PER_FAILED_PARENT')
        for ref in refs:
            path=pathlib.Path(ref['path']);C.need(path.parent==output/'starts' and path.suffix=='.json' and path.stat().st_uid==1278,'ONLY_FAILED_OWN_SMALL_START_METADATA')
            start=meta(ref);mid=start['molecule_id'];C.need(mid in expected and mid not in mids and start['task_sha256']==expected[mid]['task_sha256']
                and path.name==start['task_sha256']+'.json' and str(start['job_id'])==str(run['job_id']) and start['production_once_accessed'] is False,
                'EXACT_ORIGINAL_TASK_MID_SHA_STARTED_NOT_NATIVE_SUCCESS')
            mids.add(mid)
        sets.append(mids)
    C.need(sets[0]==sets[1]==sets[2] and len(sets[0])==16,'SAME16_UNKNOWN_STARTED_MIDS_ACROSS_THREE_FAILED_NODES')
    return {'excluded_molecule_ids':sorted(sets[0]),'original_eligible_count':49,'excluded_started_mid_count':16,'remaining_eligible_count':33,
        'old_first_wave_scientific_return_status':'UNKNOWN','old_failed_costs_and_intents_preserved':True,'scientific_DATA_read':False}

def exclusions(reference):
    value=meta(reference);C.root(value,'ROOT_SPRIME_COMPAT32_FAILED_START_EXCLUSION_V2','APPROVED_EXACT_OLD_STARTED_MIDS_NO_RETRY')
    facts=exclusion_facts(value)
    for k,v in facts.items():C.need(value[k]==v,'ROOT_EXACT_OLD16_EXCLUSION:'+k)
    C.need(value['authorize_new_independent32_only_from_remaining33'] is True and value['automatic_retry_old_started16'] is False,
        'EXPLICIT_NEW_INTENT_NO_OLD16_REPLAY')
    return value

def exclusion_references(reference):
    value=exclusions(reference);refs=[reference,value['original_qa_preparation_closure_reference']]
    from workflows.data_v1_final.conformers.sprime_multinode_resource_v1 import edge as L
    close,prep=L.preparation_closure(value['original_qa_preparation_closure_reference']);refs += [close['receipt_reference'],close['accounting_reference'],meta(close['accounting_reference'])['raw_sacct_reference'],
        prep['startup_proof_reference'],meta(prep['startup_proof_reference'])['request_reference'],prep['plan_reference']]
    for run in value['old_failed_runs']:
        proof=meta(run['startup_proof_reference']);refs += [run['accounting_reference'],meta(run['accounting_reference'])['raw_sacct_reference'],run['startup_proof_reference'],proof['request_reference'],*run['start_references']]
    return list({r['path']:r for r in refs}.values())
def compatibility(reference,node_binding_reference):
    c=meta(reference);r=meta(c['receipt_reference']);proof=meta(r['startup_proof_reference']);request=meta(proof['request_reference'])
    C.need(c['schema']=='ROOT_ACTUAL_SPRIME_NODE_COMPAT32_CLOSURE_V2' and c['status']=='ACTUAL_C0_32_EXACT_SCIENTIFIC_PACKET_SHA_MATCH'
        and r['status']=='EXACT32_ORIGINAL_SCIENTIFIC_SHA_MATCH' and r['completed']==r['matched']==32 and not r['errors']
        and r['node_binding_reference']==node_binding_reference and r['production_once_accessed'] is False and r['new_training_members']==0
        and r['source_references']==C.own_sources() and request==proof['request'] and request['node']==r['node']
        and str(proof['job_id'])==r['job_id'] and proof['uid']==r['uid']==1278
        and request['scope_key']=='sprime_multinode_resource_compat32_v2' and request['cpus']==16 and request['pilot'] is True
        and request['estimated_peak_output_bytes']==C.CAP and request['wall_seconds']==14400 and r['top_level_failure'] is None
        and r['collection']['submitted_count']==32 and r['collection']['drained_wave_starts']==[0,16]
        and len({x['pid'] for x in r['results']})==16 and all(x['matches'] for x in r['results']),'REAL_INDEPENDENT32_COMPAT_NOT_PROBE_OR_SCIENCE_RELEASE')
    budget=r['budget'];C.need(budget['stop_new_dispatch'] is None and budget['observation_failure'] is None
        and budget['actual_memory_observations'] and budget['actual_quota_observations'] and budget['whole_wave_output_reserved_bytes']==C.WAVE_RESERVE
        and budget['signals_sent_to_science'] is False and budget['natural_drain'] is True,'ACTUAL_ORIGINAL_BUDGET_HEALTHY32_COMPAT')
    b=binding(node_binding_reference);_,prep=preparation_closure(r['qa_preparation_closure_reference']);expected={x['molecule_id']:x for x in prep['expected']}
    C.need(r['environment']==b['environment'] and r['node']==b['node'] and request['scope_parameters']==C.parameters('compat32',b['node'])
        and {x['molecule_id'] for x in r['results']}==set(expected)
        and all(x['task_sha256']==expected[x['molecule_id']]['task_sha256'] and x['scientific_sha256']==expected[x['molecule_id']]['scientific_sha256_excluding_elapsed_seconds'] for x in r['results']),
        'ALL32_ACTUAL_TASK_AND_SCIENTIFIC_SHA_VALUES_INDEPENDENT_READBACK')
    plan=meta(r['plan_reference'])
    for result in r['results']:
        initialized=meta(result['worker_initialization_reference']);C.need(initialized['status']=='INITIALIZED_NOT_INVOKED'
            and initialized['pid']==result['pid'] and initialized['job_id']==r['job_id'] and initialized['science_reference']==C.sources()['science']
            and initialized['run_pilot_reference']==plan['qa_sources']['run_pilot'] and initialized['original_loader_initialization_calls']==1
            and initialized['extra_science_worker_init_calls']==0 and initialized['R_SESSION_PROOF_OUT_VALUE_bound'] is True,'ACTUAL_PER_PID_ORIGINAL_RUNNER_IO_WIRING')
    account(c['accounting_reference'],r['job_id'],r['node']);return c,r
def compatibility_references(reference,node_binding_reference):
    c,r=compatibility(reference,node_binding_reference);proof=meta(r['startup_proof_reference']);pc,prep=preparation_closure(r['qa_preparation_closure_reference'])
    return [reference,c['receipt_reference'],c['accounting_reference'],meta(c['accounting_reference'])['raw_sacct_reference'],r['startup_proof_reference'],proof['request_reference'],r['plan_reference'],
        r['qa_preparation_closure_reference'],pc['receipt_reference'],pc['accounting_reference'],meta(pc['accounting_reference'])['raw_sacct_reference'],
        prep['startup_proof_reference'],meta(prep['startup_proof_reference'])['request_reference'],prep['plan_reference'],*exclusion_references(prep['excluded_mid_authority_reference']),*(x['worker_initialization_reference'] for x in r['results'])]
def preparation_closure(reference):
    close=meta(reference);C.need(close['schema']=='ROOT_ACTUAL_SPRIME32_PREPARATION_CLOSURE_V2' and close['status']=='ACTUAL_C0_32_TASKS_BOUND_NO_UFF','ACTUAL_32_PREPARE_CLOSURE_NOT_FUTURE')
    prep=meta(close['receipt_reference']);proof=meta(prep['startup_proof_reference']);request=meta(proof['request_reference'])
    C.need(prep['schema']=='ACTUAL_SPRIME_MULTINODE_CONTROL32_PREPARATION_V2' and prep['status']=='ORIGINAL32_TASKS_AND_BASELINES_CLOSED_NO_UFF'
        and len(prep['expected'])==32 and prep['source_references']==C.own_sources() and prep['new_UFF_QM_calls']==0
        and str(proof['job_id'])==prep['job_id'] and proof['uid']==prep['uid']==1278 and request==proof['request']
        and request['scope_key']=='sprime_multinode_resource_qa_prepare_v2' and request['node']==prep['node']
        and prep['plan_reference'] in request['source_references'],'EXACT_CURRENT32_SOURCE_PLAN_PROOF_C0')
    C.need(prep['eligible_count']==49 and prep['remaining_eligible_count']==33 and prep['excluded_mid_count']==16,'NEW_PREPARATION_EXCLUDES_OLD16_FROM_REAL49')
    ex=exclusions(prep['excluded_mid_authority_reference']);C.need(not {r['molecule_id'] for r in prep['expected']}&set(ex['excluded_molecule_ids']),'NO_OLD_STARTED_MID_IN_NEW_PREPARED32')
    account(close['accounting_reference'],prep['job_id'],prep['node']);return close,prep
def references(reference,*,include_compat=False):
    b=binding(reference,require_compat=include_compat);sc=meta(b['source3_reference']);t=meta(sc['receipt_reference']);tp=meta(t['startup_proof_reference'])
    refs=[reference,b['source3_reference'],sc['receipt_reference'],t['startup_proof_reference'],tp['request_reference'],sc['accounting_reference'],meta(sc['accounting_reference'])['raw_sacct_reference']]
    c=meta(b['probe_closure_reference']);p=meta(c['receipt_reference']);proof=meta(p['startup_proof_reference'])
    refs += [b['probe_closure_reference'],c['receipt_reference'],c['accounting_reference'],meta(c['accounting_reference'])['raw_sacct_reference'],p['startup_proof_reference'],proof['request_reference'],p['plan_reference'],
        b['publisher_identity_reference'],b['publisher_actual_launch_reference'],*Q.references(b['provider_review_reference'])]
    if 'legacy_node_binding_reference' in b:
        old=meta(b['legacy_node_binding_reference']);old_sc=meta(old['source3_reference']);old_t=meta(old_sc['receipt_reference'])
        refs += [b['legacy_node_binding_reference'],*b['legacy_source_context_references'],old['source3_reference'],old_sc['receipt_reference'],old_sc['accounting_reference'],
            meta(old_sc['accounting_reference'])['raw_sacct_reference'],old_t['startup_proof_reference'],meta(old_t['startup_proof_reference'])['request_reference'],old_t['plan_reference']]
    if include_compat:
        cc,rr=compatibility(b['compat32_closure_reference'],reference);refs += compatibility_references(b['compat32_closure_reference'],reference)
    return list({r['path']:r for r in refs}.values())
class Client:
    def __init__(self,reference,request):
        self.reference=reference;self.binding=binding(reference);self.request=request;self.last=None;self.sequence=-1
        C.need(request['node']==self.binding['node'],'ACTUAL_REQUEST_NODE_CANNOT_USE_OTHER_NODE_BINDING')
    def observe(self):
        C.need(meta(self.reference)==self.binding,'FROZEN_PER_NODE_BINDING');n=C.node(self.request['node']);observed=Q.storage_observation()
        C.need(observed['node']==socket.gethostname().split('.')[0]==n,'ACTUAL_CURRENT_NODE_STORAGE')
        p,i=provider(self.binding,active=False);view={'compute_mount_by_node':{n:self.binding['compute_mount']},'marker_reference':p['marker_reference']}
        marker=Q.verify_storage(view,observed,login=False);value,evidence=current(self.binding,p,i,validate=False)
        self.last=dict(evidence,cpu_storage=observed,cpu_marker=marker)
        parsed=Q.validate_observation(value,i,self.binding['publisher_identity_reference'],p,self.binding['provider_review_reference'],time.time())
        C.need(value['sequence']>=self.sequence,'NO_QUOTA_SEQUENCE_ROLLBACK');self.sequence=value['sequence']
        physical=os.statvfs(C.Q.ROOT);free=physical.f_bavail*physical.f_frsize
        C.need(free-C.WAVE_RESERVE-CAP-C.ADMIN>=200000000000,'CURRENT_PHYSICAL_FULL_WAVE200GB_SEPARATE_FROM_QUOTA')
        self.last.update(parsed_quota=parsed,free_bytes=parsed['free_bytes'],physical_available_bytes=free);return self.last
def quota_reuse(reference,refs):
    r=meta(reference);C.root(r,'ROOT_SPRIME_MULTINODE_QUOTA_REUSE_V2','APPROVED_RESOURCE_FACTS_ONLY');b=binding(r['node_binding_reference'])
    C.need(r['compute_node']==b['node'] and r['provider_review_reference']==b['provider_review_reference']
        and r['provider_source_reference']==refs['quota_provider'] and r['whole_wave_output_reserve_bytes']==C.WAVE_RESERVE
        and r['scientific_authority_is_separate'] is True,'ACTUAL_NODE_QUOTA_REUSE_NOT_POPULATION_OR_RETRY_AUTHORITY')
    return r,sys.modules[__name__],[reference,*references(r['node_binding_reference'])]
def execution(reuse,request,active=False):
    e=C.epoch(reuse['epoch_reference'],active=active);n=C.node(request['node'])
    C.need(n==reuse['compute_node'] and e['node_binding_references'][n]==reuse['node_binding_reference']
        and request['scope_key'].startswith('sprime_multinode_resource_v2_'),'REAL_ROOT_CUTOVER_AND_EXACT_NODE_SCIENCE_AUTHORITY')
    return e
def strict_preprobe(proof,session,save):
    from workflows.data_v1_final.conformers.formal_cpu_auto_close_index_v2.admission import future_delay
    reuse,_,_=quota_reuse(session['quota_reuse_review_reference'],C.sources());client=Client(reuse['node_binding_reference'],proof['request'])
    began=time.monotonic();identity=None
    for attempt in range(2):
        before=time.time()
        try:
            value=client.observe();save({'attempt':attempt,'status':'ORIGINAL_VALIDATION_PASS','cpu_begin':before,'cpu_end':time.time(),'last':client.last});return value
        except Exception as exc:
            now=time.time();last=client.last or {};gap=future_delay(exc,last,now)
            save({'attempt':attempt,'status':'ORIGINAL_VALIDATION_FAILED','error':repr(exc),'cpu_begin':before,'cpu_end':now,'last':last,'eligible_wait':gap})
            if identity is not None:C.need(last.get('identity_reference')==identity,'IDENTITY_CHANGED_DURING_WAIT')
            identity=last.get('identity_reference')
            if attempt or gap is None or time.monotonic()-began>10:raise
            time.sleep(min(2,gap+.02))
