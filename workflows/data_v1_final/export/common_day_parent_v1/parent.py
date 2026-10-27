"""True variable-CPU Common producer chain; no DATA, fake16, or Root signing."""
import csv,io
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as PRODUCER
HERE=Q.REPO/'workflows/data_v1_final/export/common_day_parent_v1'
FILES=('__init__.py','parent.py','test_boundaries.py','README.md')
need=Q.need

def meta(r):
    PRODUCER.F.triple(r);need(Q.pin(r['path'])==r,'ACTUAL_SMALL_PARENT_PIN');return Q.load(r['path'])
def unique(refs):return PRODUCER.unique(refs)
def sources():return [Q.pin(HERE/n) for n in FILES]

def c0_row(row,job,node,cpus):
    need(type(cpus) is int and cpus>=16 and row['job_id']==str(job) and row['node']==node and row['alloc_cpus']==cpus
      and row['state']=='COMPLETED' and row['exit_code']=='0:0','TRUE_ACTUAL_PARENT_C0_AND_REAL_CPUS_NEVER_PRETEND16')
    return row

def account(ref,job,node,cpus):
    a=meta(ref);raw=a['raw_sacct_reference'];need(Q.pin(raw['path'])==raw,'ACTUAL_RAW_ACCOUNTING_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(raw['path']).decode()),delimiter='|') if r.get('JobIDRaw','').isdecimal()]
    by={r['JobIDRaw']:r for r in rows};need(len(by)==len(rows)==len(a['parents']) and a['endpoint']=='202.38.247.57:22'
      and a['uid']==1278 and a['query_returncode']==0 and a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
      and a['failed_timeout_startup_cleanup_elapsed_retained'] is True,'ACTUAL_COMPLETE_MAIN_PARENT_ACCOUNTING')
    total=0
    for p in a['parents']:
        r=by[p['job_id']];need(p['state']==r['State'].split()[0] and p['exit_code']==r['ExitCode'] and p['node']==r['NodeList']
          and p['alloc_cpus']==int(r['AllocCPUS']) and p['elapsed_raw_seconds']==int(r['ElapsedRaw']) and r['UID']=='1278','ALL_PARENT_ROWS_MATCH_ACTUAL_RAW')
        total+=p['alloc_cpus']*p['elapsed_raw_seconds']
    need(total==a['allocated_core_seconds'],'ALL_FAILURE_STARTUP_CLEANUP_COST_RETAINED');p=next(p for p in a['parents'] if p['job_id']==str(job));c0_row(p,job,node,cpus)
    return a,raw

def fixture_gate(f):
    need(f['schema']=='POSTPROCESS_ANALYSIS_DAY_PREFLIGHT_V1' and type(f['tests_run']) is int and f['tests_run']==28
      and all(type(f[k]) is int and f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'REAL28_COMPLETE_NO_SKIP_NO_FAKE_OLD8')
    s=f['source_inverse'];need(s['status']=='ACTUAL_SOURCE_FULL_INVERSE_AND_DIRECT_OBJECTS' and s['common_complete_inverse_bytes_AST'] is True
      and s['old_common_math_SQL_merge_exclusion_sparse_physical_ID_logic_unchanged'] is True and s['packet_reader_only_explicit_value'] is True
      and s['original_parent64_and_old_parent16_both_truthful'] is True,'ACTUAL_COMPLETE_SOURCE_INVERSE_NOT_CANDIDATE')
    return f

def approved(r,c):
    need(r['schema']=='ROOT_CONFORMERS_POSTPROCESS_COMPONENT_ACCEPTANCE_V1' and r['status']=='APPROVED_EXACT_ACTUAL_COMPONENTS'
      and r['reviewer']=='root' and r['approve_common'] is True and c['original_quality_hold'] is None
      and c['ordinary_Common_D7_geometry_complete'] is True and type(c['unknown_molecules']) is int and c['unknown_molecules']==0,'ROOT_REAL_COMMON_GATES_AND_FULL_GEOMETRY_READBACK')

def common_parent(chain):
    need(type(chain) is dict and set(chain)=={'manifest','entry','accounting'},'EXACT_ACTUAL_COMMON_DAY_CHAIN')
    m=meta(chain['manifest']);entry=meta(chain['entry']);env=m['runtime'];proof=meta(entry['startup_proof_reference']);req=proof['request'];plan=meta(entry['plan_reference'])
    need(m['schema']==m['status']=='COMMON_POPULATION_V1_FROZEN' and m['pilot_only'] is False and env['uid']==1278
      and type(env['cpus']) is int and env['cpus']>=16 and env['node'] in ('compute-0-14','compute-0-18'),'ACTUAL_ROOT_ACCEPTED_DAY_COMMON_NOT_PENDING_OR_PILOT')
    need(entry['schema']=='CONFORMERS_POSTPROCESS_DAY_RECEIPT_V1' and entry['status']=='ONE_PARENT_DRAINED_ACTUAL_TERMINAL_AND_ROOT_REVIEW_REQUIRED'
      and str(entry['job_id'])==str(env['job_id'])==str(proof['job_id']) and entry['runtime']=={'job_id':str(env['job_id']),'node':env['node'],'uid':1278,'cpus':env['cpus']}
      and entry['no_new_UFF_or_QM'] is True and entry['no_child_Slurm_jobs'] is True,'TRUE_ONE_DAY_ENTRY_NO_CHILD_C0')
    need(proof['uid']==1278 and proof['schema']=='FRESH_CPU_ANALYSIS_DAY_EXECUTION_ADMISSION_V1' and req['scope_key']=='conformers_postprocess_day_v1'
      and req['kind']=='analysis' and req['pilot'] is False and req['cpus']==req['requested_cpus']==env['cpus']
      and req['node']==env['node'] and req['wall_seconds']==86400 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and req['producer_plan_reference']==entry['plan_reference'] and meta(proof['request_reference'])==req
      and req['scope_parameters']==plan['scope_parameters']==PRODUCER.parameters(plan),'ACTUAL_ANALYSIS_DAY_REQUEST_SOURCE_PLAN_BINDING')
    argv=[Q.PY,'-B','-m',PRODUCER.MODULE,'--plan',entry['plan_reference']['path'],'--startup-proof',entry['startup_proof_reference']['path']]
    need(req['execution_argv']==argv and Path(chain['entry']['path'])==Path(plan['output_directory'])/'receipt.json'
      and m['actual_entry_reference']==chain['entry'] and m['actual_entry_startup_proof_reference']==entry['startup_proof_reference']
      and m['actual_entry_preflight_reference']==entry['preflight_reference'],'EXACT_PRIMARY_OPTIONS_AND_REAL_ENTRY_LOCATORS')
    gate=meta(entry['preflight_reference']);fixture_gate(gate)
    for name in PRODUCER.FILES:need(Q.pin(PRODUCER.HERE/name) in req['source_references'],'ALL15_REAL_PRODUCER_SOURCE_PINS')
    a,raw=account(chain['accounting'],env['job_id'],env['node'],env['cpus']);review=meta(m['root_component_review']);candidate=meta(review['candidate_reference']);approved(review,candidate)
    need(candidate['schema']=='CONFORMERS_POSTPROCESS_ACTUAL_C0_COMPONENT_CANDIDATE_V1' and candidate['receipt_reference']==chain['entry']
      and candidate['accounting_reference']==m['actual_parent_accounting']==chain['accounting'] and candidate['common_candidate_reference']==m['source_producer_manifest']
      and candidate['startup_proof_reference']==entry['startup_proof_reference'] and candidate['preflight_reference']==entry['preflight_reference']
      and entry['common_candidate_reference']==m['source_producer_manifest'],'EXACT_INDEPENDENT_ROOT_ACCEPTANCE_CHAIN')
    original=meta(m['source_producer_manifest']);need(original['schema']=='COMMON_POPULATION_PRODUCER_V1'
      and original['status']=='PENDING_ACTUAL_PARENT_C0_AND_INDEPENDENT_ROOT_REVIEW'
      and Path(m['source_producer_manifest']['path'])==Path(plan['output_directory'])/'common/manifest.json','ORIGINAL_CANDIDATE_NEVER_RELABELLED_IN_PLACE')
    for k,v in original.items():
        if k not in ('schema','status'):need(m[k]==v,'ROOT_ACCEPTED_COMMON_PRESERVES_PRODUCER_FIELD:'+k)
    need(len(m['membership_tables'])==16 and len(m['physical_geometry_tables'])==32,'FULL_COMMON16_MEMBERSHIP32_ORDINARY_PHYSICAL_MAPS')
    refs=[*chain.values(),raw,entry['startup_proof_reference'],entry['preflight_reference'],entry['plan_reference'],proof['request_reference'],
      m['root_component_review'],review['candidate_reference'],m['source_producer_manifest'],*(Q.pin(PRODUCER.HERE/n) for n in PRODUCER.FILES),*sources()]
    return m,unique(refs)
