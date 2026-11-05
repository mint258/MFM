"""Pure V3 identities and exact bounded-wave authorities; no runtime guessing."""
from __future__ import annotations
import csv,hashlib,importlib.util,io,json,math,os,pathlib,re,sys

HERE=pathlib.Path(__file__).absolute().parent
REPO=HERE.parents[3];RUN=REPO.parent
KERNEL_SHA='2476767636d97b2a334dcf1f8b8e789e137a268acc6404ade61b7162690d211f'
LEDGER=RUN/'artifacts/conformers/formal_v1/attempt_ledger'
BASE=RUN/'artifacts/conformers/formal_cpu_auto_v3'
CPUS=16;CAP=8<<30;ADMIN=64<<20
FORECAST='RIGHT_CENSORED_NO_VALIDATED_FULL_FORECAST'
SCHEMAS={'pilot_review':'SPRIME_CENSORED_PILOT_ROOT_REVIEW_V3','draft':'SPRIME_FORMAL_CPU_DRAFT_V3',
    'wave_review':'ROOT_SPRIME_NODE17_FINITE_WAVE_REVIEW_V1','plan':'SPRIME_FORMAL_CPU_PLAN_V3',
    'prepared':'SPRIME_FORMAL_CPU_BATCH_INPUTS_V3','completion':'SPRIME_FORMAL_CPU_COMPLETION_INDEX_V3'}
STAGES={'draft':'analysis','freeze':'analysis','prepare':'analysis','run':'conformer','close':'analysis','index':'analysis','finalize':'analysis'}


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def sha_value(value):return hashlib.sha256(canonical(value)).hexdigest()
def q(value):return "'"+str(value).replace("'","''")+"'"


def triple(value):
    need(isinstance(value,dict) and {'path','bytes','sha256'}<=set(value),'REFERENCE_REQUIRED')
    result={k:value[k] for k in ('path','bytes','sha256')};path=pathlib.Path(result['path'])
    need(path.is_absolute() and '..' not in path.parts and type(result['bytes']) is int and result['bytes']>0
        and re.fullmatch('[0-9a-f]{64}',result['sha256']),'EXACT_ABSOLUTE_POSITIVE_REFERENCE_REQUIRED')
    return result


def ref(path):
    path=pathlib.Path(path).absolute();h=hashlib.sha256()
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
        after=os.fstat(stream.fileno())
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),
        'SOURCE_CHANGED_DURING_HASH')
    return {'path':str(path),'bytes':after.st_size,'sha256':h.hexdigest()}


def pinned(reference,limit=None):
    reference=triple(reference);path=pathlib.Path(reference['path'])
    need(path.is_file() and not path.is_symlink(),'REGULAR_PINNED_INPUT_REQUIRED')
    if limit is not None:need(reference['bytes']<=limit,'BOUNDED_INPUT_REQUIRED')
    need(ref(path)==reference,'ACTUAL_SHA_OR_BYTES_CHANGED');return path


def read(reference,limit=2<<20):return json.loads(pinned(reference,limit).read_text())


def module(name,reference):
    path=pinned(reference,2<<20)
    if name in sys.modules:
        need(pathlib.Path(sys.modules[name].__file__).absolute()==path,'WRONG_FROZEN_MODULE_ALREADY_LOADED:'+name)
        return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def sources():
    value=read(ref(HERE/'frozen_sources.json'));need(value['schema']=='SPRIME_FORMAL_CPU_AUTO_SOURCE_PINS_V3','SOURCE_CATALOG_REQUIRED')
    for value_ref in value['references'].values():pinned(value_ref,2<<20)
    need(value['references']['science']['sha256']==KERNEL_SHA,'ORIGINAL_SCIENCE_KERNEL_REQUIRED')
    return value['references']


def config(reference):
    value=read(reference);need(value['schema']=='DATA_V1_SPRIME_FORMAL_CPU_AUTO_V3','EXACT_V3_CONFIG_REQUIRED')
    need(value['formal_cpus']==16 and value['maximum_parallel_science_workers']==16
        and value['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and 'formal_memory_gib' not in value
        and 'memory_gib' not in value and value['cost_policy']=='REPORT_AND_CONTINUE','CURRENT_CPU_RESOURCE_AND_COST_AUTHORITY_REQUIRED')
    need(type(value['wall_seconds']) is int and value['wall_seconds']%60==0 and 60<=value['wall_seconds']<=172800
        and 0<value['stop_dispatch_before_wall_seconds']<value['wall_seconds'],'FINITE_MINUTE_WALL_MAX48H_REQUIRED')
    need(value['max_output_bytes']==CAP and value['quota_reserve_bytes']==200000000000
        and value['exclusion_policy']=={'overall_max':0.02,'element_max':0.2,'approved_element_exceptions':[34]},
        'ORIGINAL_OUTPUT_AND_FINAL_SCIENTIFIC_THRESHOLDS_REQUIRED')
    need(type(value['max_molecules_per_batch']) is int and 0<value['max_molecules_per_batch']<=500
        and type(value['packet_uncompressed_limit_bytes']) is int and 0<value['packet_uncompressed_limit_bytes']<=256<<20
        and type(value['packet_compressed_limit_bytes']) is int and 0<value['packet_compressed_limit_bytes']<=128<<20,
        'FINITE_BATCH_AND_FULL_PACKET_BOUNDS_REQUIRED')
    expected={'expected_original_deficit_molecules':99351,'expected_unsupported_molecules':9282,
        'expected_non_unsupported_deficits':90069,'expected_pilot_consumed_deficits':320,'expected_unstarted_deficits':89749,
        'expected_source_molecules':1220466,'expected_train_val_molecules':1214218}
    need(all(value[k]==n for k,n in expected.items()) and value['full_forecast_status']==FORECAST
        and value['estimated_full_core_hours'] is None,'EXACT_SOURCE_COUNTS_AND_HONEST_CENSORED_FORECAST_REQUIRED')
    need(pathlib.Path(value['attempt_ledger_root'])==LEDGER and pathlib.Path(value['external_output_root'])==BASE,
        'ORIGINAL_CANONICAL_ONCE_LEDGER_AND_NEW_OUTPUT_NAMESPACE_REQUIRED')
    for name in ('recipe_config','roles_authority','formal_source_receipt','sprime_manifest'):pinned(value[name],2<<20)
    triple(value['per_molecule']);refs=sources();need(value['recipe_config']==refs['recipe'],'UNCHANGED_RECIPE_PIN_REQUIRED')
    return value


def task_key(mid,cohort):
    return hashlib.sha256(('sprime-fill-once-v1:'+KERNEL_SHA+':'+mid+':'+cohort).encode()).hexdigest()


def seed_for(mid,retry):
    prefix='sprime-ETKDGv3-v1:' if not retry else 'sprime-ETKDGv3-v1-retry1:'
    seed=int.from_bytes(hashlib.sha256((prefix+mid).encode()).digest()[:4],'big')
    return max(seed&0x7fffffff,1)


def cohort(row):
    if row['Sprime_status']=='UFF_UNSUPPORTED':return 'unsupported'
    return 'fill_10N' if row['Sprime_status']=='INSUFFICIENT_UNIQUE_CONFORMERS' else 'retry_once'


def ledger_path(key):
    need(isinstance(key,str) and re.fullmatch('[0-9a-f]{64}',key),'EXACT_CANONICAL_TASK_KEY_REQUIRED')
    need(not any(p.is_symlink() for p in (LEDGER,*LEDGER.parents)),'NO_LEDGER_SYMLINKS')
    return LEDGER/(key+'.json')


def import_outcome(outcome,task,closure_reference,recipe_reference=None):
    meta=task['meta'];mid=meta['molecule_id'];kind=meta['cohort']
    need(outcome['molecule_id']==mid and outcome['cohort']==kind and kind in {'retry_once','fill_10N'}
        and outcome['original_task_sha256']==sha_value(task) and outcome['original_task_seed']==seed_for(mid,kind=='retry_once')
        and outcome['expected_conformers']==meta['expected_conformers'],'ORIGINAL_TASK_BODY_COHORT_N_SEED_BINDING_REQUIRED')
    package=outcome['package_reference'];observed=outcome['science_result_observed']
    need((observed is True and package is not None and isinstance(outcome['scientific_status'],str)
            and outcome['execution_resolution']=='DURABLE_PACKAGE_VALIDATED')
        or (observed is False and package is None and outcome['scientific_status'] is None
            and outcome['execution_resolution']=='UNRESOLVED_AFTER_PARENT_TIMEOUT'),
        'UNKNOWN_MUST_REMAIN_WITHOUT_PACKAGE_OR_SCIENTIFIC_STATUS')
    return {'schema':'SPRIME_HISTORICAL_ATTEMPT_IMPORTED_V3','task_key':task_key(mid,kind),'molecule_id':mid,'cohort':kind,
        'original_task_sha256':outcome['original_task_sha256'],'seed':outcome['original_task_seed'],
        'expected_conformers':meta['expected_conformers'],'kernel_sha256':KERNEL_SHA,'recipe_config':recipe_reference if recipe_reference is not None else sources()['recipe'],
        'closure_reference':closure_reference,'package_reference':package,'science_result_observed':observed,
        'scientific_status':outcome['scientific_status'],'execution_resolution':outcome['execution_resolution'],
        'historical_parent_ids':['4520364','4521110'],'worker_identity':None,'formal_start':None,
        'new_scientific_attempt':False,'new_seed':False}


def accounting(reference,required_ids=()):
    value=read(reference);need(value['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
        and value['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and value['query_returncode']==0,'REAL_PARENT_ACCOUNTING_REQUIRED')
    raw=pinned(value['raw_sacct_reference'],8<<20).read_text();rows={}
    for row in csv.DictReader(io.StringIO(raw),delimiter='|'):
        jid=row.get('JobIDRaw',row.get('JobID',''))
        if not jid.isdecimal():continue
        need(jid not in rows,'DUPLICATE_RAW_PARENT_ACCOUNTING');rows[jid]=row
    declared={str(row['job_id']):row for row in value['parents']}
    need(len(declared)==len(value['parents']) and set(rows)==set(declared) and set(map(str,required_ids))<=set(rows),
        'EXACT_ALL_DECLARED_RAW_PARENT_SET_REQUIRED')
    for jid,row in declared.items():
        actual=rows[jid];need(row['state'] in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}
            and actual['State'].split()[0]==row['state'] and actual['ExitCode']==row['exit_code']
            and int(actual['AllocCPUS'])==int(row['alloc_cpus'])>=0 and int(actual['ElapsedRaw'])==int(row['elapsed_raw_seconds'])>=0,
            'TERMINAL_ACCOUNTING_MUST_MATCH_RAW_WITH_FAILURE_CLEANUP_COST')
    return declared


def pilot_review(reference):
    review=read(reference);need(review['schema']==SCHEMAS['pilot_review'] and review['status']=='ACCEPTED_FOR_BOUNDED_PLANNING'
        and review['reviewer']=='root' and review['accept_scientific_failure_disclosure'] is True
        and review['accept_execution_unknown_as_consumed'] is True and review['full_forecast_status']==FORECAST
        and review['formal_generation_authorized'] is False,'EXPLICIT_CENSORED_EVIDENCE_ROOT_REVIEW_REQUIRED')
    report=read(review['closure_report']);need(report['schema']=='SPRIME336_PACKAGE_OR_TIMEOUT_OUTCOME_AUDIT_V2'
        and report['status']=='CLOSED_WITH_TWO_EXECUTION_UNRESOLVED_REQUIRES_ROOT_REVIEW'
        and report['validated_original_packages']==334 and report['unresolved_execution_failures']==2
        and report['controls_validated_exact_excluding_only_summary_elapsed']==14
        and report['readback334_real_packages']['records']==929
        and report['readback334_real_packages']['status']=='ALL_PILOT_GEOMETRIES_FLOAT64_SHA_READBACK_PASSED'
        and report['scientific_success_packages']==102 and report['formal_generation_authorized'] is False,
        'ACTUAL_UNMODIFIED_1321_CLOSURE_REQUIRED')
    parent_rows=accounting(review['actual_accounting'],['4520364','4521110','4521321'])
    need(parent_rows['4520364']['state']==parent_rows['4521110']['state']=='TIMEOUT'
        and parent_rows['4521321']['state']=='COMPLETED' and parent_rows['4521321']['exit_code']=='0:0',
        'TWO_ACTUAL_TIMEOUTS_AND_REAL_CLOSURE_C0_MUST_REMAIN_DISTINCT')
    refs=sources();need(review['resource_authority']==refs['resource_authority'] and review['cost_authority']==refs['cost_authority'],
        'NEW_USER_RESOURCE_AND_REPORT_CONTINUE_COST_DECISIONS_REQUIRED')
    need(review['terminal_outcomes'] in report['outputs'],'TERMINAL336_MUST_BE_BOUND_TO_REAL_CLOSURE')
    return review,report,parent_rows


def approve_wave(draft_reference,draft,review_reference,config_reference):
    review=read(review_reference)
    need(review['schema']==SCHEMAS['wave_review'] and review['status']=='APPROVED_BOUNDED_WAVE'
        and review['reviewer']=='root' and review['draft_reference']==draft_reference and review['config_reference']==config_reference
        and review['full_forecast_status']==FORECAST and review['estimated_full_core_hours'] is None
        and review['approved_over_500_core_hours'] is True and review['scientific_quality_thresholds_unchanged'] is True,
        'ROOT_EXPLICIT_FINITE_WAVE_AND_OVER500_REVIEW_REQUIRED_WITHOUT_FALSE_FORECAST')
    jobs=review['jobs'];need(jobs and len({j['job_name'] for j in jobs})==len(jobs)
        and len({j['batch_id'] for j in jobs})==len(jobs),'EXACT_UNIQUE_BOUNDED_WAVE_JOBS_REQUIRED')
    batches={b['batch_id']:b for b in draft['batches']}
    configuration=config(config_reference)
    for job in jobs:
        need(job['batch_id'] in batches and job['cpus']==16 and job['node']=='compute-0-17' and job['batch_id'] in MIGRATABLE
            and type(job['wall_seconds']) is int and 60<=job['wall_seconds']<=172800 and job['wall_seconds']%60==0
            and job['wall_seconds']>configuration['stop_dispatch_before_wall_seconds']
            and job['whole_output_cap_bytes']==CAP and job['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
            and 'memory_gib' not in job and 'job_id' not in job
            and pathlib.Path(job['output_root']).is_absolute() and BASE in pathlib.Path(job['output_root']).parents
            and '..' not in pathlib.Path(job['output_root']).parts,
            'EXACT_FINITE_REQUEST_SLOTS_NOT_FUTURE_JOB_RESULTS')
    requested=sum(j['cpus']*j['wall_seconds'] for j in jobs)
    need(review['requested_allocation_core_seconds_ceiling']==requested
        and review['ceiling_is_not_full_forecast_or_actual_cost_guarantee'] is True
        and type(review['maximum_concurrent_jobs']) is int and 0<review['maximum_concurrent_jobs']<=len(jobs),
        'REQUEST_CEILING_AND_BOUNDED_CONCURRENCY_ARE_NOT_RUNTIME_ESTIMATES')
    need(review['resource_authority']==sources()['resource_authority'] and review['cost_authority']==sources()['cost_authority'],
        'ORIGINAL_QUALITY_CURRENT_RESOURCES_AND_COST_AUTHORITY_REQUIRED')
    return review


def scope(stage,config_reference):
    need(stage in STAGES,'KNOWN_EXACT_STAGE_REQUIRED')
    return {'stage':stage,'config_reference':triple(config_reference),'original_deficits':99351,'unsupported':9282,
        'non_unsupported_deficits':90069,'historical_consumed_deficits':320,'maximum_workers':16,'new_QM_calls':0,
        'automatic_retry':False,'full_forecast_status':FORECAST,'cost_policy':'REPORT_AND_CONTINUE',
        'scientific_quality_thresholds_unchanged':True,'whole_output_cap_bytes':CAP}

# Independent fixed-node resource context. Original scientific constants remain above.
NODE='compute-0-17'
MIGRATABLE=tuple('batch-%05d'%i for i in range(96,180))
FUTURE=MIGRATABLE[1:]
FILES=('__init__.py','contract.py','runtime_io.py','run_batch.py','prepare_batch.py','mapping.py','close_index.py','close.py',
 'quota_edge.py','probe.py','compat16.py','metadata.py','controller.py','capacity_gate.py','recovery.py','source_proof.py',
 'test_binding.py','frozen_sources.json','root_review_schemas.json','adaptation_manifest.json','README.md')
ORIGINAL=REPO/'workflows/data_v1_final/conformers/formal_cpu_auto_v3'
MODULE='workflows.data_v1_final.conformers.sprime_cpu17_resource_v1'
PROBE_CAP=128<<20;QA_CAP=2<<30;QA_WALL=7800
WAVE_RESERVE=182*CAP


def own_sources():
    source_pinned({'path':str(EMPTY_SOURCE_PATH),'bytes':0,'sha256':EMPTY_SOURCE_SHA})
    return [ref(HERE/n) for n in FILES]


def source_inverse_proof():
    from .source_proof import verify
    return verify()


def verify_original_science(science):
    import sys
    expected=sources()['science']
    need(ref(science.__file__)==expected and pathlib.Path(science.process_task.__code__.co_filename).absolute()==pathlib.Path(expected['path'])
      and science.process_task is sys.modules['science'].process_task,'ACTUAL_ORIGINAL_PROCESS_TASK_CALLABLE_REQUIRED')
    return expected


def future_slot(slot):
    need(slot['batch_id'] in MIGRATABLE and slot['node']==NODE and slot['cpus']==16 and slot['wall_seconds']==28800
      and slot['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and slot['whole_output_cap_bytes']==CAP,'EXACT_REMAINING_NODE17_SCIENCE_SLOT')
    return slot

# Revision2: SOURCE-only empty imported package support. DATA triple() stays positive.
EMPTY_SOURCE_SHA='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
EMPTY_SOURCE_PATH=REPO/'workflows/data_v1_final/conformers/portable_secondary_uff_v1/__init__.py'


def source_triple(value):
    need(isinstance(value,dict) and {'path','bytes','sha256'}<=set(value),'SOURCE_REFERENCE_REQUIRED')
    result={k:value[k] for k in ('path','bytes','sha256')}
    if type(result['bytes']) is int and result['bytes']>0:return triple(result)
    p=pathlib.PurePosixPath(result['path']) if isinstance(result['path'],str) else None
    need(type(result['bytes']) is int and result['bytes']==0 and result['sha256']==EMPTY_SOURCE_SHA
      and p is not None and p.is_absolute() and str(p)==result['path'] and '..' not in p.parts
      and not any(c in result['path'] for c in ('\x00','\n','\r')) and p.name=='__init__.py'
      and pathlib.PurePosixPath(str(REPO)) in p.parents,'ONLY_EXACT_EMPTY_SOURCE_INIT_NO_ZERO_DATA')
    return result


def empty_source_frame(before,after):
    import stat
    keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns','st_uid')
    need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==0
      and tuple(getattr(before,k) for k in keys)==tuple(getattr(after,k) for k in keys),'EMPTY_SOURCE_REGULAR_UID_FRAME_CHANGED')
    return tuple(getattr(after,k) for k in keys)


def source_pinned(value):
    reference=source_triple(value)
    if reference['bytes']>0:return pinned(reference,2<<20)
    path=pathlib.Path(reference['path'])
    need(not any(p.is_symlink() for p in (path,*path.parents)),'EMPTY_SOURCE_NO_SYMLINKS')
    original=path.lstat()
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());empty_source_frame(original,before)
        raw=stream.read(1);after=os.fstat(stream.fileno());empty_source_frame(before,after)
    need(raw==b'' and hashlib.sha256(raw).hexdigest()==reference['sha256'],'EMPTY_SOURCE_ACTUAL_BYTES_SHA_CHANGED')
    empty_source_frame(original,path.lstat())
    need(not any(p.is_symlink() for p in (path,*path.parents)),'EMPTY_SOURCE_NO_SYMLINKS')
    return path