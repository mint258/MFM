"""Only terminal4525232's frozen55k cache; no new cohort, math or old writes."""
import csv,io
from pathlib import Path
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import contract as OLD
P=OLD.P;need=OLD.need;meta=OLD.meta;RUN=OLD.RUN;REPO=OLD.REPO;PY=OLD.PY
KEY='existing_sprime_fast55k_resume_v1';MODULE='workflows.data_v1_final.labels.'+KEY+'.run';HERE=REPO/'workflows/data_v1_final/labels'/KEY
FILES=('__init__.py','contract.py','metadata.py','run.py','geometry.py','cache.py','README.md')
OLDROOT=RUN/'artifacts/labels/source_status_v1/existing_sprime_fast55k_pilot_day_v1/day01_cpu17_v1_pilot_provisional'
PILOT_COUNTS=OLD.PILOT_COUNTS;GLOBAL_SOURCE_COUNTS=OLD.GLOBAL_SOURCE_COUNTS
unique=OLD.unique;reference=OLD.reference;logical=OLD.logical
def __getattr__(name):return getattr(OLD,name)
def resume_authority(p):
    r=meta(p['resume_origin_review_reference']);a=r['parent_registration']
    need(r['schema']=='ROOT_FAST55K_C0_PARTIAL_CACHE_READONLY_RESUME_REVIEW_V1'
      and r['status']=='APPROVED_EXACT4525232_CACHE_READONLY_AND_MISSING_ONLY' and r['reviewer']=='root'
      and r['old_output_root']==str(OLDROOT) and r['no_old_output_writes'] is True,'ROOT_EXACT_CACHE_ADOPTION')
    req,sub,proof,old=[meta(a[k]) for k in ('request_reference','submission_reference','proof_reference','plan_reference')]
    need(req==sub['request']==proof['request'] and sub['request_reference']==proof['request_reference']==a['request_reference']
      and str(sub['job_id'])==str(proof['job_id'])=='4525232' and sub['sbatch_returncode']==0
      and req['scope_key']==OLD.KEY and req['cpus']==16 and req['node']=='compute-0-17'
      and req['execution_argv']==[PY,'-B','-m',OLD.MODULE,'--plan',a['plan_reference']['path'],'--startup-proof',a['proof_reference']['path']]
      and old['output_directory']==str(OLDROOT),'REAL_REGISTERED_OLD_FAST55K_ONLY')
    account=meta(a['accounting_reference']);raw,ref=P.small(a['raw_reference']['path'])
    rows=[x for x in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|')if x['JobIDRaw']=='4525232']
    need(account['query_returncode']==0 and account['uid']==1278 and account['raw_sacct_reference']==a['raw_reference']==ref
      and len(rows)==1 and rows[0]['UID']=='1278' and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
      and int(rows[0]['AllocCPUS'])==16 and rows[0]['NodeList']=='compute-0-17','ACTUAL_OLD_C0_NOT_COMPLETE_D4')
    for name in OLD.FILES:need(P.pin(REPO/'workflows/data_v1_final/labels'/OLD.KEY/name)in req['source_references'],'FROZEN_FAST_SOURCE_NO_HOTSWAP')
    return r,old,proof
def scope(p):
    return {'purpose':'READONLY_C0_PARTIAL_FAST55K_CACHE_MISSING_ONLY_THEN_ORIGINAL_D4',
      'resume_origin_review_reference':p['resume_origin_review_reference'],'node':p['node'],'requested_cpus':16,
      'wall_seconds':86400,'output_directory':p['output_directory'],'whole_output_cap_bytes':p['whole_output_cap_bytes'],
      'pilot_counts':PILOT_COUNTS,'original_population_counts':GLOBAL_SOURCE_COUNTS,'old_cache_root':str(OLDROOT/'typed_coverage'),
      'original_tasks_and_sequence':True,'same_geometry_171groups_math_two_TRAIN_replays':True,'new_QM_UFF_calls':0,
      'old_parts_readonly_no_full55k_cache_rebuild':True,'full_Common_D4_D5_D3_D6_release':False}
def plan(p):
    need(p['schema']=='EXISTING_SPRIME_FAST55K_RESUME_PLAN_V1' and p['status']=='ROOT_REVIEWED_EXECUTABLE_BOUNDED_PILOT'
      and p['reviewer']=='root' and p['cpus']==p['requested_cpus']==p['workers']==16 and p['wall_seconds']==86400
      and 32<<30<=p['whole_output_cap_bytes']<=512<<30 and p['scope_parameters']==scope(p)
      and Path(p['output_directory']).parent==RUN/'artifacts/labels/source_status_v1'/KEY,'EXACT_NEW16CPU_DAY_RESUME')
    _,old,_=resume_authority(p)
    for k in ('canonical_index','field_map_reference','logical_group_plan_reference','source_inventory_reference','formal_record_index_reference',
      'footer_manifest_reference','pilot_input_review_reference','projection_origin_review_reference','base_cache_plan_reference',
      'hof_closed_prefix_reuse_review_reference','pilot_priority_review_reference','element_basis','field_scope'):
        need(p[k]==old[k],'NO_SCIENTIFIC_AUTHORITY_OR_COHORT_CHANGE:'+k)
    need(p['TSQR_chunk']==256 and p['quality_new_mask_fraction']==.01 and p['independent_numeric_replay_required']is True
      and p['full_Common_D4_D5_D3_D6_release']is False,'SAME_ORIGINAL_MATH_AND_QUALITY')
    for r in p['source_references']:need(P.pin(r['path'])==r,'EXACT_RESUME_SOURCE')
    for r in p['data_references']:reference(r)
    return p
