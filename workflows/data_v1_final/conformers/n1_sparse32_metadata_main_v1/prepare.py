"""Root-approved small-metadata builder; no task/value reads, execution or submit."""
from __future__ import annotations
import argparse,ast,csv,hashlib,io,json,os,re,stat
from pathlib import Path,PurePosixPath
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,REPO,PY,on_login,write_new
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import contract as Q

HERE=REPO/'workflows/data_v1_final/conformers/n1_sparse32_metadata_main_v1'
SCIENCE=REPO/'workflows/data_v1_final/conformers/n1_sparse32_readchain_v1'
V4=REPO/'workflows/data_v1_final/conformers/n1_pprime2_pilot_v4'
ALPHA=PurePosixPath('/gfshome/alpha/codex_data_v1_20261026');SMALL=2<<20;CAP=2<<30
READS=[]

def need(value,message):
    if not value:raise ValueError(message)

def literal(path):
    path=Path(path);need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),
        'EXPLICIT_ABSOLUTE_METADATA_PATH_WITHOUT_SYMLINK');return path

def data_reference(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'} and type(value['bytes']) is int and value['bytes']>0
        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']),'EXACT_NONEMPTY_INPUT_LOCATOR')
    path=PurePosixPath(value['path']);need(path.is_absolute() and '..' not in path.parts,'LITERAL_DATA_LOCATOR_ONLY')
    # This intentionally does not call Path.stat/is_file/resolve/open/hash.
    return dict(value)

def small(path,expected=None):
    path=literal(path);text=str(path)
    need(path.suffix.lower() in ('.json','.py','.md','.txt') and not any(part in path.parts for part in ('tasks','baselines','baseline','packets')),
        'TASK_BASELINE_PACKET_JSONL_LMDB_OR_SCIENTIFIC_CONTAINER_BODY_FORBIDDEN')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size<=SMALL,'OWN_SMALL_METADATA_ONLY')
        raw=stream.read(SMALL+1);after=os.fstat(stream.fileno())
    frame=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(frame(before)==frame(after)==frame(path.stat()) and len(raw)==after.st_size,'SMALL_METADATA_CHANGED')
    reference={'path':text,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if expected is not None:need(reference==expected,'CURRENT_ROOT_SMALL_PIN_MISMATCH')
    if reference not in READS:READS.append(reference)
    return raw,reference

def ref(path):return small(path)[1]
def load(path):
    raw,reference=small(path);return json.loads(raw),reference
def load_ref(reference):
    data_reference(reference);raw,_=small(reference['path'],reference);return json.loads(raw)

def expression(node):
    if isinstance(node,ast.Constant) and type(node.value) in (str,int,bool,type(None)):return node.value
    if isinstance(node,ast.Dict):return {expression(k):expression(v) for k,v in zip(node.keys,node.values)}
    if isinstance(node,ast.List):return [expression(v) for v in node.elts]
    if isinstance(node,ast.Tuple):return tuple(expression(v) for v in node.elts)
    if isinstance(node,ast.BinOp) and isinstance(node.op,ast.LShift):
        left,right=expression(node.left),expression(node.right)
        need(type(left) is int and type(right) is int and 0<=left<=1<<40 and 0<=right<=40,'FINITE_LITERAL_SHIFT_ONLY')
        return left<<right
    raise ValueError('NO_EVAL_EXEC_CALLS_OR_NONLITERAL_SCOPE_EXPRESSIONS')

def constants(path,names):
    raw,_=small(path);tree=ast.parse(raw.decode('utf-8'));out={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in names:
                    need(target.id not in out,'DUPLICATE_LITERAL_NAME');out[target.id]=expression(node.value)
    need(set(out)==set(names),'EXACT_FROZEN_SCOPE_CONSTANTS');return out

def original_parents(review):
    accounting_ref=review['terminal_all_known_accounting_reference'];account=load_ref(accounting_ref)
    raw_reference=account['raw_sacct_reference'];raw,_=small(raw_reference['path'],raw_reference)
    need(account.get('schema')=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and account.get('status')=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and account.get('query_returncode')==0 and account.get('endpoint')=='202.38.247.57:22' and account.get('uid')==1278,
        'ACTUAL_MAIN_ALL_KNOWN_PARENT_ACCOUNTING')
    rows=list(csv.DictReader(io.StringIO(raw.decode()),delimiter='|'));actual={}
    for row in rows:
        jid=row.get('JobIDRaw',row.get('JobID',''))
        if jid.isdecimal():need(jid not in actual,'DUPLICATE_ACTUAL_PARENT');actual[jid]=row
    declared={str(row['job_id']):row for row in account['parents']}
    need(len(declared)==len(account['parents']) and set(declared)==set(actual),'ALL_KNOWN_PARENT_SET_CONSERVATION')
    for jid,row in actual.items():
        other=declared[jid]
        need(row['State'].split()[0]==other['state'] and row['ExitCode']==other['exit_code']
            and int(row['AllocCPUS'])==other['alloc_cpus'] and int(row['ElapsedRaw'])==other['elapsed_raw_seconds'],
            'DECLARED_ACCOUNTING_DIFFERS_FROM_ACTUAL_RAW')
    for jid,review_field in (('4521417','actual_prepare_parent'),('4521418','actual_pilot_parent')):
        row=actual[jid];other=review[review_field]
        need(row['State']=='COMPLETED' and row['ExitCode']=='0:0' and row['AllocCPUS']=='16' and row['UID']=='1278'
            and row['NodeList']=='compute-0-13' and all(row[k]==other[k] for k in ('State','ExitCode','AllocCPUS','UID','NodeList','ElapsedRaw')),
            'EXACT_ACTUAL_CANONICAL_SOURCE1417_PILOT1418_C0')
    return accounting_ref,raw_reference

def frozen_sources(handoff_ref):
    handoff=load_ref(handoff_ref);rows=handoff['files']
    need(handoff.get('schema')=='N1_SPARSE32_READCHAIN_SOURCE_FINAL_DEPLOYMENT_HANDOFF_V1'
        and handoff.get('source_files')==len(rows)==11 and len({r['name'] for r in rows})==11,'FROZEN_ELEVEN_SOURCE_HANDOFF')
    actual=[]
    for row in rows:
        value=row['expected_Root_reference'];need(value['path']==str(SCIENCE/row['name']),'ACTUAL_ROOT_LOCATION_NOT_CHILD_SAME_SHA')
        _,observed=small(value['path'],value);actual.append(observed)
    need({p.name for p in SCIENCE.iterdir() if p.suffix in ('.py','.md')}=={r['name'] for r in rows},'NO_MISSING_OR_EXTRA_FROZEN_SOURCE')
    return actual

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--approve',action='store_true',required=True);p.add_argument('--reason',required=True)
    for name in ('metadata-output','science-output','alpha-input-root'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--job-name',required=True);p.add_argument('--wall-seconds',type=int,default=3600)
    p.add_argument('--pilot-review',type=Path,default=ROOT/'control/n1_actual32_pilot_science_cost_root_review_v1.json')
    p.add_argument('--quota-provider-review',type=Path,default=ROOT/'control/n1_same_storage_quota_provider_root_review_v1.json')
    p.add_argument('--resource-authority',type=Path,default=REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    p.add_argument('--cost-decision',type=Path,default=REPO/'configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json')
    p.add_argument('--source-handoff',type=Path,default=REPO/'docs/data_v1/n1_sparse32_readchain_v1_source_handoff.json')
    a=p.parse_args();on_login();need(Path(__file__).absolute().parent==HERE,'ACTUAL_ROOT_INTEGRATED_BUILDER_ONLY')
    need(a.approve and a.reason.strip() and len(a.reason.encode())<=8192,'EXPLICIT_ROOT_APPROVE_AND_CONCRETE_REASON')
    need(re.fullmatch(r'dv1_q_[A-Za-z0-9_]+',a.job_name),'SAFE_FRESH_JOB_NAME')
    need(120<a.wall_seconds<=3600 and a.wall_seconds%60==0,'FINITE_ONE_HOUR_WHOLE_MINUTE_EXPORT')
    output=literal(a.metadata_output);science_output=literal(a.science_output)
    need(ROOT/'control' in output.parents and not output.exists() and ROOT/'artifacts/conformers/n1_sparse32_readchain_v1' in science_output.parents
        and not science_output.exists(),'FRESH_REVIEW_METADATA_AND_SCIENCE_OUTPUTS')
    alpha=PurePosixPath(str(a.alpha_input_root));need(alpha.is_absolute() and '..' not in alpha.parts
        and ALPHA/'inputs/n1_sparse32_readchain_v1' in alpha.parents,'EXPLICIT_EXPECTED_ALPHA_INPUT_CHILD_NOT_VERIFIED')
    authority=ref(a.resource_authority);Q.validate_authority(authority,read_small=lambda path:small(path)[0])
    cost=ref(a.cost_decision);handoff_ref=ref(a.source_handoff);sources=frozen_sources(handoff_ref)
    values=constants(SCIENCE/'guard.py',{'MAIN_KEY','PARAMETERS'})
    need(values['MAIN_KEY']=='n1_sparse32_readchain_export_v1','EXACT_FROZEN_EXPORT_KEY')
    review,review_ref=load(a.pilot_review)
    need(review.get('schema')=='ROOT_ACTUAL_N1_V4_PILOT32_SCIENCE_COST_REVIEW_V1' and review.get('reviewer')=='root'
        and review.get('endpoint')=='202.38.247.57:22' and review.get('uid')==1278 and review.get('actual_pilot_molecules')==32
        and review.get('new_QM_calls')==0 and review.get('original_baseline_preserved') is True,'ACTUAL_ROOT_CANONICAL32_SOURCE_REVIEW')
    prepared_ref=review['prepared_reference'];prepared=load_ref(prepared_ref);pilot_ref=review['pilot_receipt_reference'];pilot=load_ref(pilot_ref)
    need(prepared.get('schema')=='N1_PPRIME2_PILOT_PREPARED32_V4' and prepared.get('status')=='ACTUAL_INPUT32_READY_NOT_GENERATED'
        and prepared.get('job_id')=='4521417' and prepared.get('selected_count')==32 and len(prepared['tasks'])==len(prepared['baseline_packets'])==32,
        'ACTUAL_V4_PREPARED32_METADATA_HEADER')
    need(pilot.get('schema')=='N1_PPRIME2_PILOT32_RECEIPT_V4' and pilot.get('status')=='ACTUAL32_PACKETS_CLOSED_REQUIRES_SCIENTIFIC_AND_COST_ROOT_REVIEW'
        and pilot.get('job_id')=='4521418' and pilot.get('prepared')==prepared_ref and pilot.get('completed_durable_readback_packets')==32
        and not pilot['unknown_started_task_keys'],'ACTUAL32_RECEIPT_HEADER_NOT_PACKET_BODY')
    account_ref,raw_account_ref=original_parents(review)
    population_ref=prepared['source_population_authority'];population=load_ref(population_ref)
    need(population.get('schema')=='N1_PPRIME2_SOURCE_POPULATION_AUTHORITY_V4' and population.get('job_id')=='4521417'
        and len(population['selected_molecule_ids'])==len(set(population['selected_molecule_ids']))==32,'CANONICAL32_POPULATION_HEADER_ONLY')
    catalog_ref=prepared['catalog'];catalog=load_ref(catalog_ref);c=catalog['references']
    science={'common':c['io'],'legacy':c['graph_stereo_rmsd'],'prepare':c['legacy_prepare_import']};recipe_ref=c['recipe'];recipe=load_ref(recipe_ref)
    need(recipe['science_source_pins']==[science['legacy'],science['prepare']],'ORIGINAL_UNMODIFIED_RECIPE_SOURCE_PINS')
    for value in science.values():small(value['path'],value)
    data=[data_reference(r) for r in [*prepared['tasks'],*prepared['baseline_packets']]]
    need(len({r['path'] for r in data})==64 and all('/prepared_v1/tasks/' in r['path'] for r in data[:32])
        and all('/prepared_v1/baselines/' in r['path'] for r in data[32:]),'EXACT32_TASK32_BASELINE_DATA_LOCATORS_NO_BODY_READ')
    quota_ref=ref(a.quota_provider_review);quota=load_ref(quota_ref)
    need(quota.get('schema')=='ROOT_MAIN_N1_SAME_STORAGE_QUOTA_PROVIDER_REVIEW_V1' and quota.get('status')=='APPROVED_FOR_EXACT_SAME_STORAGE_PROVIDER'
        and quota.get('reviewer')=='root' and set(quota['compute_mount_by_node'])=={'compute-0-13'}
        and quota.get('maximum_age_seconds')==120 and quota.get('cpu_poll_seconds')==60 and quota.get('quota_reserve_bytes')==200000000000,
        'ACTUAL_EXISTING_NODE13_QUOTA_MAPPING_PROVIDER_METADATA')
    quota_refs=[quota_ref,*quota['provider_source_references'],*quota['evidence_references'],quota['marker_reference'],quota['count_correction_authority_reference']]
    for value in quota_refs:small(value['path'],value)
    # All imported scientific reader code is pinned but never imported here.
    source_paths=[*HERE.glob('*.py'),*HERE.glob('*.md'),*[V4/name for name in ('__init__.py','io.py','contract.py','quota_provider.py')],
        *(REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py'),
        *[REPO/'workflows/data_v1_final/execution/queue_v1'/name for name in ('__init__.py','shared.py','queue_contract.py')]]
    for directory in ('workflows','workflows/data_v1_final','workflows/data_v1_final/conformers','workflows/data_v1_final/execution'):
        path=REPO/directory/'__init__.py'
        if path.is_file():source_paths.append(path)
    for path in source_paths:ref(path)
    sources.extend(READS);unique={}
    for value in sources:
        need(value['path'] not in unique or unique[value['path']]==value,'CONFLICTING_SMALL_SOURCE_PIN');unique[value['path']]=value
    need(not {r['path'] for r in data}.intersection(unique),'SCIENTIFIC_JSON_DATA_NEVER_SMALL_SOURCE')
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    plan={'schema':'MAIN_N1_SPARSE32_READCHAIN_EXPORT_PLAN_V1','scope_key':values['MAIN_KEY'],'scope_parameters':values['PARAMETERS'],
        'wall_seconds':a.wall_seconds,'output_cap_bytes':CAP,'selected_input_cap_bytes':CAP,'output_directory':str(science_output),'alpha_input_root':str(alpha),
        'prepared_reference':prepared_ref,'pilot_receipt_reference':pilot_ref,'science_cost_review_reference':review_ref,'accounting_reference':account_ref,
        'catalog_reference':catalog_ref,'recipe_reference':recipe_ref,'quota_provider_review_reference':quota_ref,'science_sources':science}
    plan_ref=write_new(output/'plan.json',plan);unique[plan_ref['path']]=plan_ref
    argv=[PY,'-B','-m','workflows.data_v1_final.conformers.n1_sparse32_readchain_v1.main_export','--plan',plan_ref['path'],'--root-preflight','__ROOT_STARTUP_PROOF__']
    parents=list({r['path']:r for r in [review_ref,prepared_ref,pilot_ref,account_ref,raw_account_ref,population_ref,catalog_ref,quota_ref,handoff_ref,cost]}.values())
    root_review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
        'resource_authority_reference':authority,'kind':'analysis','scope_key':values['MAIN_KEY'],'scope_parameters':values['PARAMETERS'],
        'pilot':False,'wall_seconds':a.wall_seconds,'estimated_peak_output_bytes':CAP,'stage_output_cap_bytes':CAP,'execution_argv':argv,
        'scope_mode':'BOUNDED_METADATA_PREPARATION','source_status_stage':'CANONICAL32_RAW_KV_EXPORT_ORIGINAL_READER_CONTROL_NO_GENERATION',
        'parent_evidence_references':parents,'root_review_reason':a.reason.strip(),'explicit_Root_approve_argument':True,
        'science_task_and_baseline_json_are_DATA_even_if_small':True,'Main_export_only_no_Alpha_startup_or_transfer_acceptance':True,
        'new_UFF_QM_calls':0,'once_ledger_opened':False,'canonical32_reexecuted_as_generation':False,'dataset_membership':False,
        'allocation_core_hours_ceiling_not_forecast':a.wall_seconds*16/3600,'original_UFF32_mean_not_used_as_read_IO_prediction':True}
    rr=write_new(output/'scope_review.json',root_review);unique[rr['path']]=rr
    spec={k:root_review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
        source_references=list(unique.values()),data_references=data,scope={'mode':'BOUNDED_METADATA_PREPARATION','review':rr,'parent_profile':None})
    Q.validate_scope_spec(spec,authority,read_small=lambda path:small(path)[0]);spec_ref=write_new(output/'stage_spec.json',spec)
    command=[PY,'-B','-m','workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.materialize','--spec',spec_ref['path'],
        '--authority',authority['path'],'--node','compute-0-13','--job-name',a.job_name]
    receipt=write_new(output/'metadata_handoff.json',{'schema':'MAIN_SPARSE32_SOURCE_ONLY_METADATA_MATERIALIZATION_V1',
        'status':'ROOT_APPROVED_METADATA_PREPARED_NOT_MATERIALIZED_OR_SUBMITTED','plan':plan_ref,'scope_review':rr,'stage_spec':spec_ref,
        'central_materialize_argv':command,'node':'compute-0-13','cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':a.wall_seconds,
        'metadata_files_actually_read':READS,'task_data_locators':32,'baseline_data_locators':32,'all64_json_body_reads_or_stat':False,
        'LMDB_or_packet_or_scientific_JSONL_opened':False,'scientific_library_imported':False,'new_UFF_QM_calls':0,'once_ledger_opened':False,
        'quota_provider_started_or_refreshed':False,'fresh_actual_quota_still_required_at_CPU_runtime':True,
        'Alpha_target_install_or_body_hash_verified':False,'automatic_transfer_or_request_materialize_or_submit':False})
    print(json.dumps({'plan':plan_ref,'scope_review':rr,'stage_spec':spec_ref,'handoff':receipt,'central_materialize_argv':command,
        'data_refs':64,'new_UFF_QM_calls':0,'submitted':False}))

if __name__=='__main__':main()
