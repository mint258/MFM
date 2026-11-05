"""Only sprime_packed_day_v1, Main13, integerCPU>=16, one86400s parent."""
import hashlib,json,os,re,time
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import contract as O
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import fields,parse_scontrol_jobs
from . import quota_provider as Provider
need=Q.need;ROOT=Q.ROOT;REPO=Q.REPO;PY=Q.PY;PROJECT=Q.PROJECT;fmt=O.fmt
HERE=REPO/'workflows/data_v1_final/execution/cpu_packed_day_v1'
FILES=('__init__.py','contract.py','runtime.py','materialize.py','submit.py','launch.py','observe.py','test_v1.py','quota_provider.py','quota_origin.json','README.md')
KEY='sprime_packed_day_v1';MODULE='workflows.data_v1_final.conformers.sprime_packed_day_v1.run'
BASE=ROOT/'control/cpu_packed_day_v1';REQUEST='CPU_PACKED_DAY_REQUEST_V1';PROOF='FRESH_CPU_PACKED_DAY_EXECUTION_ADMISSION_V1'
MEMORY='SLURM_DEFAULT_UNSPECIFIED';WALL=86400;RESERVE=200000000000;OLD_WAVE=182*(8<<30)
AUTH=REPO/'configs/data_v1/user_day_packed_jobs_20261028_v1.json'

def meta(ref):
    raw=O.pin_bytes(ref,Q.read_small);return json.loads(raw)

def unique(refs):
    out={}
    for r in refs:
        O.pin(r);need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_SMALL_SOURCE_PIN');out[r['path']]=r
    return list(out.values())

def authority(ref):
    need(ref['path']==str(AUTH),'ACTUAL_NEW_PACKED_USER_DECISION_REQUIRED');a=meta(ref)
    need(a['schema']=='USER_AUTHORIZED_DAY_PACKED_DATA_JOBS_V1' and a['status']=='USER_AUTHORIZED' and a['target_job_wall_seconds']==WALL
        and a['minimum_allocated_cpus']==16 and a['CPU_only'] is True and a['memory_request']=='UNSPECIFIED_NO_SBATCH_MEM_OR_EXCLUSIVE'
        and a['quota_reserve_bytes']==RESERVE and a['scientific_data_scope_or_recipe_or_quality_changed'] is False
        and a['one_parent_job_id_truthful_no_fake_child_Slurm_C0'] is True and a['all182_existing_future_cap_carveout_not_added_twice'] is True
        and a['root_auxiliary_resource_choice']['new_packed_only_finite_quota_publisher_maximum_runtime_seconds']==90000
        and a['root_auxiliary_resource_choice']['required_remaining_lease_at_actual_release_seconds']==86700,
        'EXACT_PACKED_ONLY_CPU_MEMORY_25H_RESOURCE_AUTHORITY')
    O.validate_authority(a['persistent_previous_user_cpu_memory_authority_reference'],read_small=Q.read_small)
    return a

def inverse():
    v=Q.load(HERE/'quota_origin.json');raw=Q.read_small(HERE/'quota_provider.py');old=O.pin_bytes(v['original_source_reference'],Q.read_small)
    text=raw.decode();need(text.count(v['new_literal'])==1 and text.replace(v['new_literal'],v['old_literal']).encode()==old,
        'ONLY_QUOTA86400_TO90000_ONE_LITERAL_FULL_SOURCE_INVERSE')
    return v['original_source_reference']

def resources(req,*,now=None,lease=False):
    authority(req['resource_authority_reference']);c=meta(req['root_carveout_review_reference'])
    need(c['schema']=='ROOT_PACKED_DAY_EXISTING182_RESOURCE_CARVEOUT_V1' and c['status']=='APPROVED' and c['reviewer']=='root'
        and c['scope_key']==KEY and c['resource_authority_reference']==req['resource_authority_reference']
        and type(c['old182_reserved_upper_bound_bytes'])is int and c['old182_reserved_upper_bound_bytes']==OLD_WAVE
        and c['old182_task_caps_only_bytes']==OLD_WAVE and c['historical_bound_includes_original_provider_bytes']==0
        and type(c['packed_parent_carveout_bytes'])is int and c['packed_parent_carveout_bytes']>=req['estimated_peak_output_bytes']>0
        and type(c['sprime_other_future_reserve_bytes'])is int and c['sprime_other_future_reserve_bytes']>=0
        and c['packed_parent_carveout_bytes']+c['sprime_other_future_reserve_bytes']<=OLD_WAVE
        and type(c['other_non_sprime_future_reserve_bytes'])is int and c['other_non_sprime_future_reserve_bytes']>=0
        and type(c['quota_provider_future_reserve_bytes'])is int and c['quota_provider_future_reserve_bytes']==64<<20
        and type(c['admin_future_reserve_bytes'])is int and c['admin_future_reserve_bytes']==64<<20
        and type(c['total_future_reserved_bytes'])is int and c['total_future_reserved_bytes']==sum(c[k] for k in (
            'packed_parent_carveout_bytes','sprime_other_future_reserve_bytes','other_non_sprime_future_reserve_bytes',
            'quota_provider_future_reserve_bytes','admin_future_reserve_bytes'))
        and type(c['previous_total_future_reserved_bytes'])is int and c['previous_total_future_reserved_bytes']>=c['total_future_reserved_bytes']
        and c['future_after_carveout_not_greater_than_before'] is True and c['closed_writer_space_is_in_actual_quota_used'] is True
        and c['old_jobs_and_costs_preserved'] is True,'CURRENT_FUTURE_ONLY_OLD182_UPPER_NOT_DOUBLE_CHARGED')
    for key in ('historical_original182_upper_reference','all_prior_ordinary_parent_terminal_evidence_reference',
        'closed_readback_all21_parent_evidence_reference','closed_kraken_projection_evidence_reference','fresh_account_observation_reference'):
        meta(c[key])
    for ref in c['old_failed_compat32_actual_accounting_references']:meta(ref)
    review=Provider.load_review(req['quota_provider_review_reference']);identity=Provider.pinned(req['quota_provider_identity_reference'])
    need(review['maximum_runtime_seconds']==90000 and review['compute_mount_by_node'].keys()=={'compute-0-13'}
        and identity['review_reference']==req['quota_provider_review_reference'] and identity['publisher_output_dir']==review['publisher_output_dir']
        and Path(req['quota_provider_identity_reference']['path'])==Path(review['publisher_output_dir'])/'identity.json',
        'ACTUAL_NEW25H_PROVIDER_IDENTITY_SAME_VERIFIED_NODE13_STORAGE')
    if lease:need(identity['expires_unix_seconds']-(time.time() if now is None else now)>=86700,'WAIT_NEW_FINITE_PROVIDER_REMAINING_MUST_COVER86400_PLUS300')
    return c,review,identity

def shape(r):
    need(r['schema']==REQUEST and r['scope_key']==KEY and r['kind']=='conformer' and r['pilot'] is False
        and r['node']=='compute-0-13' and r['partition']=='cpu' and type(r['cpus'])is int and r['cpus']>=16
        and r['requested_cpus']==r['cpus'] and r['wall_seconds']==WALL and r['memory_policy']==MEMORY
        and r['exclusive_requested'] is False and r['workdir']==str(PROJECT) and r['startup_wait_seconds']==120,
        'ONLY_NEW_PACKED_SCOPE_REAL_INTEGER_CPUS_NODE13_DAY_NO_MEM')
    need(type(r['scope_parameters'])is dict and type(r['estimated_peak_output_bytes'])is int and r['estimated_peak_output_bytes']>0
        and r['execution_argv']==[PY,'-B','-m',MODULE,'--plan',r['producer_plan_reference']['path'],'--startup-proof',r['startup_proof_path']],
        'EXACT_PRODUCER_PLAN_FULL_ARGV_NOT_OLD16_OR_CHILD_JOB')
    need(type(r['job_name'])is str and re.fullmatch('dv1_pack_[a-zA-Z0-9_]+',r['job_name']) and Path(r['startup_proof_path'])==BASE/r['job_name']/'proof.json',
        'UNIQUE_PACKED_METADATA_NAMESPACE')
    need(not O.FORBIDDEN.intersection(r) and not r.get('deferred_authority_references'),'NO_OLD_MEMORY_OR_DEFERRED_FUTURE_AUTHORITY')
    return r

def validate(r):
    shape(r);resources(r);inverse()
    sources=unique(r['source_references']);data=[O.pin(v,small=False) for v in r['data_references']]
    need(len(data)==len({v['path'] for v in data}) and not {v['path'] for v in data}&{v['path'] for v in sources},'DISJOINT_EXACT_DATA_LOCATORS_NO_LOGIN_BODY_IO')
    for v in sources:need(Q.pin(v['path'])==v,'CURRENT_SOURCE_SMALL_PARENT_PIN')
    need(r['producer_plan_reference'] in sources and r['resource_authority_reference'] in sources
        and all(r[k] in sources for k in ('root_carveout_review_reference','quota_provider_review_reference','quota_provider_identity_reference')),'ALL_ACTUAL_RESOURCE_AND_PLAN_PINS')
    review=meta(r['root_review_reference']);expected=review['request_fields']
    need(review['schema']=='ROOT_EXACT_SPRIME_PACKED_DAY_REVIEW_V1' and review['status']=='APPROVED' and review['reviewer']=='root',
        'ONE_CONCRETE_INDEPENDENT_ROOT_PACKED_REVIEW')
    for k,v in expected.items():
        if k!='source_references':need(O.same(r[k],v),'EXACT_ROOT_PACKED_FIELD:'+k)
    need(all(v in sources for v in expected['source_references']) and r['root_review_reference'] in sources,'ROOT_REVIEW_SOURCE_PARENT_CLOSURE')
    text=O.pin_bytes(r['script_reference'],Q.read_small).decode();d=fmt._directives(text)
    wanted={'job-name':r['job_name'],'partition':'cpu','nodelist':r['node'],'nodes':'1','ntasks':'1','cpus-per-task':str(r['cpus'])}
    need(all(d.get(k)==v for k,v in wanted.items()) and set(d)<=set(wanted)|{'time','output','chdir'}
        and fmt._wall(d.get('time',''))==WALL and not any(k.startswith(('mem','gpu')) or k in {'exclusive','gres'} for k in d),
        'EXACT_REAL_PACKED_SBATCH_CPUS_WALL_NO_MEMORY_GPU_EXCLUSIVE')
    return r

def job_identity(r,raw,jid,held=False):
    j=fields(raw) if isinstance(raw,str) else raw
    need(j['JobId']==str(jid) and fmt._uid(j)==1278 and j['JobName']==r['job_name'] and j['Partition']=='cpu'
        and j['NumCPUs']==str(r['cpus']) and j.get('NumTasks','1')=='1' and j['Requeue']=='0'
        and j['Command']==r['script_reference']['path'] and j['WorkDir']==str(PROJECT) and fmt._wall(j['TimeLimit'])==WALL,
        'ACTUAL_ONE_PACKED_PARENT_CPU_COUNT_SCRIPT_WALL_UID')
    need(not any('gpu' in str(j.get(k,'')).lower() for k in ('TRES','TresPerNode','TresPerTask','Gres')),'NO_ACTUAL_GPU_ALLOCATION')
    if held:need(j['JobState']=='PENDING' and j['Reason']=='JobHeldUser' and j['Priority']=='0' and j['ReqNodeList']==r['node'],'EXACT_OWN_HELD_JOB')
    else:need(j['JobState']=='RUNNING' and fmt._nodes(j['NodeList'])=={r['node']} and j['NumNodes']=='1','ACTUAL_RUNNING_NODE13_PARENT')
    return j

def free_cpu(r,raw):
    n=fields(raw);total=int(n['CPUTot']);allocated=int(n['CPUAlloc'])
    need(n['NodeName']==r['node'] and 'cpu' in n['Partitions'].split(',') and 0<=allocated<=total
        and total-allocated>=r['cpus'],'WAIT_ACTUAL_REQUESTED_FREE_CPU_NO_ASSUMED64')
    return {'node':r['node'],'total_cpus':total,'allocated_cpus':allocated,'free_cpus':total-allocated,'raw':raw,'memory_admission_evaluated':False}

def sources():
    paths=[*(HERE/n for n in FILES)]
    for part in ('cpu_auto_memory_queue_v2','queue_v1'):
        paths.extend((REPO/'workflows/data_v1_final/execution'/part).glob('*.py'))
    paths.append(Path(inverse()['path']));paths.append(REPO/'workflows/data_v1_final/conformers/n1_pprime2_pilot_v4/contract.py')
    return list(dict.fromkeys(paths))
