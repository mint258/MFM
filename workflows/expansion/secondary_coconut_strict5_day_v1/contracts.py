"""One exact Alpha CPU16 readonly strict5 scope; historical norm stays C0."""
import csv,hashlib,io,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as q
ROOT=q.ROOT;UID=1264;KEY='coconut_strict5_closed_norm_alpha_v1';MODULE='secondary_coconut_strict5_day_v1.run'
STAGE='COCONUT_CLOSED_NORM_STRICT5_CONSERVATIVE_ALL_ROWS';SCHEMA='COCONUT_STRICT5_DAY_PLAN_V1';PROOF='COCONUT_STRICT5_DAY_STARTUP_V1'
HERE=ROOT/'code/secondary_coconut_strict5_day_v1';COUNTS={'molecules':1140133,'entries':1799004};TOTAL=2939137
ENV={'python':'3.11.14','numpy':'2.2.6','RDKit':'2025.09.5','pyarrow':'17.0.0'}
PARAMS={'sanitize':False,'removeHs':False,'parseName':False,'allowCXSMILES':False,'strictCXSMILES':True,'debugParse':False}
RAW_COLUMNS=('source_table','copy_block','source_row_ordinal','source_offset','source_bytes','source_row_sha256','identity_fields_json')
FILES=('__init__.py','contracts.py','io.py','kernel.py','run.py','metadata.py','adapters.py','controller.py','test_v1.py','source_inverse.py','frozen_sources.json','README.md',
    'frozen/__init__.py','frozen/common.py','frozen/decontamination.py')
need=q.need;pin=q.ref;load=q.load;literal=q.literal;write_new=q.write_new

def parameters(p):
    return {'purpose':'FULL_COCONUT_STRICT5_CONSERVATIVE_DECONTAMINATION_ONLY','norm_parent_job_id':'1884790',
      'norm_receipt_reference':p['norm_parent']['receipt'],'expected_physical_rows_by_table':COUNTS,'physical_rows':TOTAL,
      'closed_norm_parts':46,'original_properties_identity_projection_rows':1140133,'input_body_count':47,
      'workers':16,'maximum_pending':32,'input_batch_rows':16,'persistent_pool':True,'per_row_fsync':False,
      'output_commit_rows':65536,'SQL_commit_records':4096,'all_original_variants_union':True,'stored_key_disagreements_preserved':True,
      'status_invalid_or_missing_key_filter':False,'FK_orphan_or_NULL_invented_parent':False,
      'unresolved_without_identity_or_composition_must_HOLD':True,'formula_sources':'ORIGINAL_PROPERTIES_AND_STANDARD_INCHI_FORMULA_LAYER_ONLY',
      'native_composition':'EXACT_POSITIVE_INTEGER_NON_H_COUNTS_ALL_FRAGMENTS','molecular_weight_used':False,
      'new_UFF_QM_calls':0,'source_identity_norm_recomputed':False,'graph_repair_neutralization_or_tautomer_edit':False,
      'role':p['role'],'subdatasets':['molecules','entries'],'environment':ENV,'wall_seconds':86400,'output_cap_bytes':p['output_cap_bytes'],
      'global_decontamination_or_pool_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}

def norm_parent(plan):
    from .io import triple
    pp=plan['norm_parent']
    need(set(pp)=={'receipt','plan','proof','accounting','outputs','A_receipt'},'EXACT_ACTUAL_NORM_PARENT_CHAIN')
    for r in pp.values():q.verify(r)
    r=q.load_ref(pp['receipt']);p=q.load_ref(pp['plan']);s=q.load_ref(pp['proof']);a=q.load_ref(pp['accounting']);outputs=q.load_ref(pp['outputs']);native=q.load_ref(pp['A_receipt'])
    need(r['schema']=='SECONDARY_COCONUT_IDENTITY_NORM_FULL_RECEIPT_V1' and r['status']=='FULL_PHYSICAL_IDENTITY_KEY_OBSERVATIONS_COMPLETE_UNKNOWNS_PRESERVED'
      and r['job_id']=='1884790' and r['uid']==UID and r['endpoint']==q.ENDPOINT and r['allocated_cpus']==16
      and r['physical_rows']==TOTAL and r['expected_physical_rows_by_table']==COUNTS and r['saved_rows_by_table']==COUNTS
      and r['source_block_ordinal_coverage'] is True and r['technical_errors']==[] and r['durability_failures']==0
      and r['all_physical_status_invalid_variants_and_no_key_rows_retained'] is True,'REAL_COMPLETE_NORM1884790_ALL_UNKNOWN_RETAINED')
    need(r['plan']==pp['plan'] and r['startup_proof']==pp['proof'] and r['outputs_manifest']==pp['outputs'] and r['A_full_receipt']==pp['A_receipt']
      and s['job_id']=='1884790' and s['uid']==UID and s['node']==r['node'] and s['plan_reference']==pp['plan']
      and p['scope_key']=='coconut_identity_norm_full_alpha_v1' and p['cpus']==16 and s['request']['cpus']==16,
      'HISTORICAL_NORM_PLAN_PROOF_NOT_CURRENT_FRESH_PROOF')
    rows=[x for x in a['actual_parents'] if x['JobIDRaw']=='1884790'];need(len(rows)==1 and a['uid']==UID and a['endpoint']==q.ENDPOINT and a['query_returncode']==0
      and a['actual_receipt_reference']==pp['receipt'] and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
      and rows[0]['UID']=='1264' and rows[0]['AllocCPUS']=='16' and rows[0]['NodeList']==r['node'],'ACTUAL_NORM_C0_COST_NOT_SOURCE_ONLY')
    need(a['query_argv']==['sacct','-X','-P','-n','-j','1884790','--format=JobIDRaw,JobName,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,UID,User,Partition'],'ACTUAL_NOHEADER_SACCT_FIELD_ORDER');raw=list(csv.DictReader(io.StringIO(a['raw_sacct']),fieldnames=('JobIDRaw','JobName','State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','UID','User','Partition'),delimiter='|'));rr=[x for x in raw if x.get('JobIDRaw')=='1884790']
    need(len(rr)==1 and all(rr[0][k]==rows[0][k] for k in ('State','ExitCode','UID','AllocCPUS','NodeList','ElapsedRaw')),'ORIGINAL_NORM_RAW_ACCOUNT_PARITY')
    need(r['actual_environment']['actual_versions']==ENV and plan['frozen_identity_source_references']==p['frozen_identity_source_references'],'SAME_FROZEN_ENVIRONMENT_AND_IDENTITY_KERNEL')
    files={x['path']:triple(x) for x in outputs};parts=[];mass={'molecules':0,'entries':0}
    for x in r['closed_parts']:
        path=x['Parquet_path'];need(x['schema']=='COCONUT_NORM_FULL_CLOSED_PART_V1' and x['table'] in mass and path in files,'ACTUAL_CLOSED_PART_FINAL_PRODUCER_SHA')
        parts.append({'reference':files[path],'table':x['table'],'rows':x['rows']});mass[x['table']]+=x['rows']
    need(len(parts)==46 and mass==COUNTS and len({x['reference']['path'] for x in parts})==46,'EXACT46_CLOSED_NORM_PARTS_ALL_TABLE_ROWS')
    properties=[x for x in native['physical_output_references'] if x['path'].endswith('/properties.raw_identity.parquet')]
    need(len(properties)==1 and native['status']=='FULL_SQL_PHYSICAL_IDENTITY_FIELD_INVENTORY_COMPLETE'
      and native['inventory']['reconciliation']['projected_rows_by_table']['properties']==1140133,'ACTUAL_ORIGINAL_FORMULA_IDENTITY_PRODUCER')
    bodies=[x['reference'] for x in parts]+[triple(properties[0])]
    need(plan['data_references']==bodies,'EXACT46_NORM_PLUS_ORIGINAL_PROPERTIES47_LOCATORS')
    return r,p,parts,properties[0],native

def startup(plan_path,proof_path,primary):
    plan=load(plan_path);proof=load(proof_path);review=q.load_ref(plan['root_review_reference']);wall=plan['wall_seconds'];cap=plan['output_cap_bytes']
    source=HERE/'run.py';argv=[plan['python'],'-B','-m',MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)]
    need(plan.get('schema')=='COCONUT_STRICT5_DAY_PLAN_V1' and plan.get('producer_key')==plan.get('scope_key')==KEY and
      plan.get('stage')==STAGE and plan.get('mode')=='full' and plan.get('pilot') is False and plan.get('scope_parameters')==parameters(plan) and
      plan.get('endpoint')==q.ENDPOINT and plan.get('uid')==UID and plan.get('run_root')==str(ROOT) and plan.get('node') in q.NODES and plan.get('cpus')==16 and
      plan.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED' and type(wall) is int and wall==86400 and wall%60==0 and plan.get('output_cap_bytes')==cap,
      'EXACT_INDEPENDENT_FULL_PHYSICAL_SCOPE_REQUIRED')
    need(Path(primary).absolute()==source==Path(sys.modules['__main__'].__file__).absolute() and Path(sys.executable).absolute()==Path(plan['python']).absolute() and
      sys.argv==[str(source),*argv[4:]] and plan['execution_argv']==argv and plan['startup_proof_path']==str(proof_path),'ACTUAL_FULL_PRIMARY_AND_ALL_ARGV')
    need(review.get('schema')=='EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1' and review.get('status')=='APPROVED_FOR_EXACT_STAGE' and review.get('reviewer')=='root',
      'EXACT_ROOT_FULL_STAGE_REVIEW')
    for key in ('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','pilot','wall_seconds','output_cap_bytes',
      'execution_argv','data_references','parent_evidence_references'):need(plan[key]==review[key],'ROOT_FULL_FIELD_DIFFERS:'+key)
    need(plan['source_references']==review['approved_source_references'] and review.get('actual_norm_parent_and_unknowns_reviewed') is True and
      review.get('all_physical_rows_including_no_key_authorized') is True,'EXACT_APPROVED_FULL_SOURCES_AND_QUALITY_REVIEW')
    need(proof.get('schema')=='COCONUT_STRICT5_DAY_STARTUP_V1' and proof.get('endpoint')==q.ENDPOINT and proof.get('uid')==os.getuid()==UID and
      proof['node']==plan['node']==socket.gethostname().split('.')[0] and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and
      0<=time.time()-proof['observed_unix_seconds']<=120 and proof['plan_reference']==pin(plan_path) and proof['root_review_reference']==plan['root_review_reference'],
      'ACTUAL_FRESH_ALPHA_FULL_PROOF')
    need(proof['request']=={'kind':'analysis','pilot':False,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':wall,'execution_argv':argv} and
      proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False and proof.get('bounded_readonly_scope_only') is True and
      proof.get('bounded_source_acquisition_scope_only',False) is False,'FULL_DEFAULT_MEMORY_READONLY_NOT_ACQUISITION_REQUEST')
    env=os.environ;need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('SLURM_CPUS_PER_TASK')=='16' and
      env.get('CUDA_VISIBLE_DEVICES')=='' and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'REAL_CPU16_LIBRARY_THREADS')
    declared={r['path']:{k:r[k] for k in ('path','bytes','sha256')} for r in proof['source_target_verification']}
    for ref in [*plan['source_references'],*plan['parent_evidence_references'],plan['root_review_reference'],pin(plan_path)]:
        need(declared.get(ref['path'])==ref,'ACTUAL_FULL_SOURCE_NOT_BOUND');q.verify(ref)
    for path in [*source.parent.glob('*.py'),Path(q.__file__),Path(q.__file__).parent/'__init__.py']:need(pin(path) in plan['source_references'],'ACTUAL_NEW_FULL_AND_BASE_CODE_REQUIRED')
    signer=proof['controller_evidence'];need(signer['endpoint']==q.ENDPOINT and signer['uid']==UID and signer['hostname']=='sonmi' and signer['proof_is_not_created_by_scientific_worker'] is True and
      signer['actual_script_reference']==proof['script_reference'],'REAL_LOGIN_CONTROLLER_SIGNER')
    for line in q.read_small(q.verify(proof['script_reference'])).decode().splitlines():
        if line.strip().startswith('#SBATCH'):need(not any(x in line for x in ('--mem','--exclusive','--gres','--gpu')),'NO_MEMORY_EXCLUSIVE_GPU')
    job=q.fields(proof['job_metadata']);need(job.get('JobId')==str(proof['job_id']) and job.get('UserId')=='alpha(1264)' and job.get('JobState')=='RUNNING' and
      job.get('NodeList')==plan['node'] and job.get('Partition')=='cpu' and job.get('NumCPUs')=='16' and job.get('NumTasks')=='1' and job.get('Requeue')=='0' and
      job.get('Command')==proof['script_reference']['path'] and q.duration(job.get('TimeLimit',''))==wall,'ACTUAL_FULL_JOB_SCRIPT_WALL')
    gate=proof['actual_gate_process'];tail=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split();need(gate['pid']==os.getpid() and gate['uid']==UID and
      gate['start_ticks']==int(tail[19]) and gate['pgid']==os.getpgrp() and gate['sid']==os.getsid(0) and gate['cgroup_sha256']==hashlib.sha256(Path('/proc/self/cgroup').read_bytes()).hexdigest(),
      'SAME_ACTUAL_EXEC_GATE_IDENTITY')
    storage=proof['storage_observation'];q.load_ref(proof['storage_observation_reference']);need(proof['account_free_bytes']==storage['effective_free_bytes'] and
      proof['account_free_bytes']-cap>=200000000000 and storage['whole_output_caps_reserved_bytes']>=cap and 0<=time.time()-storage['observed_unix_seconds']<=120,'FRESH_ALL_CAPS200GB_STORAGE')
    for key in ('resource_authority_reference','cost_decision_reference'):need(plan[key] in plan['source_references'],'ACTUAL_APPROVED_AUTHORITY')
    authority=q.load_ref(plan['resource_authority_reference']);need(authority.get('schema')=='USER_AUTHORIZED_SECONDARY_DATA_CLUSTER_V1' and authority.get('status')=='USER_AUTHORIZED' and
      authority.get('endpoint')==q.ENDPOINT and authority.get('observed_uid')==UID and authority.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','REAL_ALPHA_AUTHORITY')
    cost=q.load_ref(plan['cost_decision_reference']);need(cost.get('schema')=='USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1' and cost.get('status')=='USER_AUTHORIZED' and
      cost.get('on_overrun')=='REPORT_AND_CONTINUE' and cost.get('scientific_quality_thresholds_unchanged') is True,'REAL_COST_CONTINUE_QUALITY_UNCHANGED')
    need(type(cap)is int and 2<<30<=cap<=32<<30,'ROOT_FINITE_STRICT5_OUTPUT_CAP')
    norm_parent(plan)
    return plan,proof
# ORIGINAL_STARTUP_PREFIX_END
