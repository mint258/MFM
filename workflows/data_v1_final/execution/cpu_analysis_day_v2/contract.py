"""Two explicit final Common analysis day parents; no scientific or old-resource edits."""
import hashlib,json,re,time
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q,contract as O
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.slurm_format import fields,parse_scontrol_jobs
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as Provider
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import contract as ORIGINAL
need=Q.need;ROOT=Q.ROOT;REPO=Q.REPO;PY=Q.PY;PROJECT=Q.PROJECT;fmt=O.fmt
HERE=REPO/'workflows/data_v1_final/execution/cpu_analysis_day_v2'
FILES=('__init__.py','contract.py','runtime.py','materialize.py','submit.py','launch.py','observe.py','test_v1.py','README.md')
SCOPES={'common_train_normalization_day_v1':'workflows.data_v1_final.labels.common_train_normalization_day_v1.run',
        'd5_inputs_compound_day_v1':'workflows.data_v1_final.export.d5_inputs_compound_day_v1.run'}
BASE=ROOT/'control/cpu_analysis_day_v2';REQUEST='CPU_ANALYSIS_DAY_REQUEST_V2';PROOF='FRESH_CPU_ANALYSIS_DAY_EXECUTION_ADMISSION_V2'
MEMORY='SLURM_DEFAULT_UNSPECIFIED';WALL=86400;RESERVE=200000000000
AUTH=REPO/'configs/data_v1/user_day_packed_jobs_20261028_v1.json'

def meta(ref):return json.loads(O.pin_bytes(ref,Q.read_small))

def unique(refs):
    out={}
    for r in refs:
        O.pin(r);need(r['path'] not in out or out[r['path']]==r,'CONFLICTING_SOURCE_OR_SMALL_PARENT_PIN');out[r['path']]=r
    return list(out.values())

def authority(ref):
    need(ref['path']==str(AUTH),'REAL_USER_DAY_PACKING_DECISION_REQUIRED');a=meta(ref)
    need(a['schema']=='USER_AUTHORIZED_DAY_PACKED_DATA_JOBS_V1' and a['status']=='USER_AUTHORIZED'
        and a['target_job_wall_seconds']==WALL and a['minimum_allocated_cpus']==16 and a['CPU_only'] is True
        and a['memory_request']=='UNSPECIFIED_NO_SBATCH_MEM_OR_EXCLUSIVE' and a['quota_reserve_bytes']==RESERVE
        and a['scientific_data_scope_or_recipe_or_quality_changed'] is False
        and a['one_parent_job_id_truthful_no_fake_child_Slurm_C0'] is True,'ORIGINAL_DAY_NO_MEM_NO_SCIENCE_CHANGE_AUTHORITY')
    O.validate_authority(a['persistent_previous_user_cpu_memory_authority_reference'],read_small=Q.read_small);return a

def inverse():return ORIGINAL.inverse()

def carveout(c,req):
    need(c['schema']=='ROOT_ANALYSIS_DAY_CURRENT_FUTURE_CARVEOUT_V1' and c['status']=='APPROVED' and c['reviewer']=='root'
        and c['scope_key']==req['scope_key'] and c['node']==req['node'] and c['resource_authority_reference']==req['resource_authority_reference'],
        'THIS_EXACT_ANALYSIS_SCOPE_NODE_ROOT_FUTURE_ACCOUNTING')
    keys=('parent_output_cap_bytes','other_future_reserved_bytes','quota_provider_future_reserve_bytes','admin_future_reserve_bytes')
    need(all(type(c[k])is int and c[k]>=0 for k in keys) and c['parent_output_cap_bytes']>=req['estimated_peak_output_bytes']>0
        and c['quota_provider_future_reserve_bytes']==64<<20 and c['admin_future_reserve_bytes']==64<<20
        and type(c['total_future_reserved_bytes'])is int and c['total_future_reserved_bytes']==sum(c[k] for k in keys)
        and type(c['previous_total_future_reserved_bytes'])is int and c['previous_total_future_reserved_bytes']>=0
        and type(c['approved_additional_future_reserve_bytes'])is int and c['approved_additional_future_reserve_bytes']>=0
        and c['total_future_reserved_bytes']<=c['previous_total_future_reserved_bytes']+c['approved_additional_future_reserve_bytes']
        and c['future_within_previous_plus_explicit_Root_increment'] is True and c['parent_included_exactly_once'] is True
        and c['all_other_active_and_future_writers_included'] is True and c['closed_writer_space_is_in_actual_quota_used'] is True
        and c['old_jobs_and_costs_and_UNKNOWN_preserved'] is True,'WHOLE_CURRENT_FUTURE_ONCE_PLUS_REAL_QUOTA_NO_RECLAIM_UNKNOWN')
    need(c['accounting_basis_references'],'NONEMPTY_ACTUAL_CURRENT_RESERVE_BASIS')
    return c

def resources(req,*,now=None,lease=False):
    authority(req['resource_authority_reference']);c=carveout(meta(req['root_carveout_review_reference']),req)
    for ref in c['accounting_basis_references']:meta(ref)
    review=Provider.load_review(req['quota_provider_review_reference']);identity=Provider.pinned(req['quota_provider_identity_reference'])
    need(review['maximum_runtime_seconds']==90000 and set(review['compute_mount_by_node'])=={req['node']}
        and identity['review_reference']==req['quota_provider_review_reference'] and identity['publisher_output_dir']==review['publisher_output_dir']
        and Path(req['quota_provider_identity_reference']['path'])==Path(review['publisher_output_dir'])/'identity.json',
        'REAL_NEW25H_ANALYSIS_NODE_STORAGE_IDENTITY_NOT_RUNNING_SPRIME_LEASE')
    if lease:need(identity['expires_unix_seconds']-(time.time() if now is None else now)>=86700,'WAIT_ACTUAL_REMAINING_LEASE_COVER86400_PLUS300')
    return c,review,identity

def shape(r):
    need(r['schema']==REQUEST and r['scope_key'] in SCOPES and r['kind']=='analysis' and r['pilot'] is False
        and r['node'] in ('compute-0-14','compute-0-18') and r['partition']=='cpu' and type(r['cpus'])is int and r['cpus']>=16
        and r['requested_cpus']==r['cpus'] and r['wall_seconds']==WALL and r['memory_policy']==MEMORY
        and r['exclusive_requested'] is False and r['workdir']==str(PROJECT) and r['startup_wait_seconds']==120,
        'ONLY_TWO_FINAL_COMMON_ANALYSIS_DAY_SCOPES_CPUS_GE16_NODE14_OR18_NO_MEM_GPU_EXCLUSIVE')
    need(type(r['scope_parameters'])is dict and type(r['estimated_peak_output_bytes'])is int and r['estimated_peak_output_bytes']>0
        and r['execution_argv']==[PY,'-B','-m',SCOPES[r['scope_key']],'--plan',r['producer_plan_reference']['path'],'--startup-proof',r['startup_proof_path']],
        'EXACT_SOURCE_PLAN_FULL_OS_ARGV_ONE_REAL_PARENT')
    need(type(r['job_name'])is str and re.fullmatch('dv1_aday_[a-zA-Z0-9_]+',r['job_name'])
        and Path(r['startup_proof_path'])==BASE/r['job_name']/'proof.json','FRESH_SEPARATE_ANALYSIS_DAY_METADATA_NAMESPACE')
    need(not O.FORBIDDEN.intersection(r) and not r.get('deferred_authority_references'),'NO_FUTURE_PIN_OR_OLD_MEMORY_SCOPE');return r

def validate(r):
    shape(r);resources(r);inverse();src=unique(r['source_references']);data=[O.pin(v,small=False) for v in r['data_references']]
    need(len(data)==len({v['path'] for v in data}) and not {v['path'] for v in data}&{v['path'] for v in src},'EXACT_SOURCE_DATA_DISJOINT_NO_LOGIN_BODY_IO')
    for v in src:need(Q.pin(v['path'])==v,'SOURCE_OR_SMALL_PARENT_CHANGED')
    need(all(r[k] in src for k in ('producer_plan_reference','resource_authority_reference','root_carveout_review_reference',
        'quota_provider_review_reference','quota_provider_identity_reference')),'ALL_ACTUAL_PLAN_RESOURCE_PARENTS_BOUND')
    review=meta(r['root_review_reference']);expected=review['request_fields']
    need(review['schema']=='ROOT_EXACT_ANALYSIS_DAY_REVIEW_V1' and review['status']=='APPROVED' and review['reviewer']=='root',
        'ONE_CONCRETE_ROOT_ANALYSIS_DAY_REVIEW')
    need(set(expected)==set(r)-{'root_review_reference'},'COMPLETE_EXACT_ROOT_REQUEST_FIELD_SET')
    for k,v in expected.items():
        if k!='source_references':need(O.same(r[k],v),'EXACT_ROOT_DAY_FIELD:'+k)
    need(all(v in src for v in expected['source_references']) and r['root_review_reference'] in src,'REVIEW_AND_SOURCE_CLOSURE')
    text=O.pin_bytes(r['script_reference'],Q.read_small).decode();d=fmt._directives(text)
    wanted={'job-name':r['job_name'],'partition':'cpu','nodelist':r['node'],'nodes':'1','ntasks':'1','cpus-per-task':str(r['cpus'])}
    need(all(d.get(k)==v for k,v in wanted.items()) and set(d)<=set(wanted)|{'time','output','chdir'}
        and fmt._wall(d.get('time',''))==WALL and not any(k.startswith(('mem','gpu')) or k in {'exclusive','gres'} for k in d),
        'EXACT_PARENT_SBATCH_NO_MEMORY_GPU_EXCLUSIVE');return r

def job_identity(r,raw,jid,held=False):
    j=fields(raw) if isinstance(raw,str) else raw
    need(j['JobId']==str(jid) and fmt._uid(j)==1278 and j['JobName']==r['job_name'] and j['Partition']=='cpu'
        and j['NumCPUs']==str(r['cpus']) and j.get('NumTasks','1')=='1' and j['Requeue']=='0'
        and j['Command']==r['script_reference']['path'] and j['WorkDir']==str(PROJECT) and fmt._wall(j['TimeLimit'])==WALL,'ACTUAL_SINGLE_ANALYSIS_PARENT_IDENTITY')
    need(not any('gpu' in str(j.get(k,'')).lower() for k in ('TRES','TresPerNode','TresPerTask','Gres')),'NO_GPU_ALLOCATION')
    if held:need(j['JobState']=='PENDING' and j['Reason']=='JobHeldUser' and j['Priority']=='0' and j['ReqNodeList']==r['node'],'EXACT_OWN_HELD_PARENT')
    else:need(j['JobState']=='RUNNING' and fmt._nodes(j['NodeList'])=={r['node']} and j['NumNodes']=='1','ACTUAL_EXPECTED_ANALYSIS_NODE_PARENT')
    return j

def free_cpu(r,raw):
    n=fields(raw);total=int(n['CPUTot']);allocated=int(n['CPUAlloc'])
    need(n['NodeName']==r['node'] and 'cpu' in n['Partitions'].split(',') and 0<=allocated<=total and total-allocated>=r['cpus'],'WAIT_TRUE_REQUESTED_FREE_CPUS')
    return {'node':r['node'],'total_cpus':total,'allocated_cpus':allocated,'free_cpus':total-allocated,'raw':raw,'memory_admission_evaluated':False}

def sources():
    paths=[*(HERE/n for n in FILES)]
    for part in ('cpu_auto_memory_queue_v2','queue_v1'):paths.extend((REPO/'workflows/data_v1_final/execution'/part).glob('*.py'))
    paths.extend(ORIGINAL.sources())
    return list(dict.fromkeys(paths))
