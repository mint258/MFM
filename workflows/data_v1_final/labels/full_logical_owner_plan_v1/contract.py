"""Pure exact full-source population/order and explicit new authority boundary."""
import collections,re
from pathlib import Path
from workflows.data_v1_final.labels.normalization_typed_cache_v1.contract import need,reference
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=REPO/'workflows/data_v1_final/labels/full_logical_owner_plan_v1'
FILES=('__init__.py','contract.py','io.py','worker.py','build.py','metadata.py','source_inverse.py','test_boundaries.py','README.md')
KEY='labels_full_original_logical_owner_plan_build_v1';MODULE='workflows.data_v1_final.labels.full_logical_owner_plan_v1.build'
SCHEMA='FULL_LOGICAL_OWNER_PLAN_BUILD_CONFIG_V1';CAP=1<<30
PARAMETERS={'canonical_records':11231854,'canonical_molecules':1220466,'base_files':184,'label_files':2024,'task_slots':14,'workers':16,
 'original_order':'SOURCE_JOB_ASC_THEN_ORIGINAL_VERIFIED_FILE_LIST_THEN_PHYSICAL_ROW','TSQR_chunk':256,'QR_reduction':'ORIGINAL_ORDERED_LEFT_FOLD',
 'new_logical_plan_not_old_full_null':True,'labels_or_numeric_calibration_read':False,'new_UFF_QM_calls':0,'final_Common_D4':False}

def config(cfg):
    need(cfg['schema']==SCHEMA and cfg['scope_key']==KEY and cfg['scope_parameters']==PARAMETERS,'EXACT_NEW_LOGICAL_PLAN_SCOPE')
    need(cfg['workers']==16 and cfg['output_cap_bytes']==CAP and type(cfg['wall_seconds']) is int and 600<=cfg['wall_seconds']<=7200,'FINITE16CPU_MAX2H_1GIB')
    need(type(cfg['other_output_cap_bytes']) is int and cfg['other_output_cap_bytes']>=0,'ALL_OTHER_FUTURE_STORAGE_CAPS_REQUIRED')
    for r in cfg['data_references']:reference(r)
    for r in cfg['small_references']:reference(r,source=True)
    return cfg

def review(cfg,r):
    need(r['schema']=='ROOT_FULL_LOGICAL_OWNER_PLAN_BUILD_REVIEW_V1' and r['status']=='ROOT_APPROVED_NEW_FULL_LOGICAL_PLAN_BUILD'
      and r['reviewer']=='root' and r['reason'].strip(),'SEPARATE_ROOT_TECHNICAL_APPROVAL_REQUIRED')
    need(r['baseline512_config_reference']==cfg['baseline512_config_reference'] and r['footer_manifest_reference']==cfg['footer_parent']['manifest']
      and r['canonical_preparation_reference']==cfg['canonical_preparation_reference'] and r['formal_record_index_reference']==cfg['formal_record_index_reference'], 'EXACT_ROOT_INPUT_AUTHORITY')
    need(r['old_full_logical_plan_was_null'] is True and r['old1904_remains_TIMEOUT'] is True and r['old_books_or_HOLD_modified'] is False
      and r['current_CPU_full_SHA_current_frame_binding_approved'] is True and r['freeze_requires_actual_C0'] is True,'NO_OLD_AUTHORITY_OR_PHYSICAL_IDENTITY_FICTION')
    need(type(r['other_output_cap_bytes']) is int and type(r['quota_headroom_bytes']) is int and r['source_mapping_evidence_references']==cfg['source_mapping_evidence_references'] and r['all_other_future_caps_reviewed'] is True
      and r['other_output_cap_bytes']==cfg['other_output_cap_bytes'] and r['new_output_cap_bytes']==CAP and r['quota_headroom_bytes']==200000000000,'EXACT_STORAGE_AND_MAPPING_REVIEW')
    return r

def ranges(n,workers=16):
    need(type(n) is int and n>=workers and workers==16,'SIXTEEN_NONEMPTY_PHYSICAL_ORDINAL_PARTITIONS')
    return [(i*n//workers,(i+1)*n//workers) for i in range(workers)]

def groups(labels,base,counts,role_authority):
    """Same full jobs expression as streaming.prepare; file lists stay in input order."""
    all_jobs=sorted((int(job),sum(v['records'] for v in values.values())) for job,values in counts.items())
    jobs=[int(job) for job,_ in all_jobs]
    need(len(jobs)>=16 and len(set(jobs))==len(jobs),'ACTUAL_FULL_SOURCE_JOB_GROUPS_NOT_PILOT16')
    need(set(jobs)=={int(r['source_job_id']) for r in labels}==set(base),'EXACT_CANONICAL_AND_SOURCE_JOB_SET')
    result=[];totals=collections.Counter();molecules=collections.Counter()
    for i,job in enumerate(jobs):
        rc=counts[str(job)];need(set(rc)<=set(('TRAIN','VAL','FULL')),'ONLY_FROZEN_SOURCE_ROLES')
        source_files=[x for x in labels if int(x['source_job_id'])==job]
        need(source_files and base[job],'OWNER_JOB_MISSING_BASE_OR_LABEL')
        for role,row in rc.items():totals[role]+=row['records'];molecules[role]+=row['molecules']
        result.append({'group_index':i,'source_job_id':job,'owner_index':None,'owner_index_reason':'FULL_READER_USES_SHA_BOUND_CANONICAL_SQLITE_NO_SYNTHETIC_OWNER_PARQUET',
          'expected_records':sum(r['records'] for r in rc.values()),'expected_molecules':sum(r['molecules'] for r in rc.values()),
          'expected_TRAIN_records':rc.get('TRAIN',{}).get('records',0),'role_counts':rc,'label_files':source_files,'base_files':base[job]})
    need(sum(totals.values())==11231854 and sum(molecules.values())==1220466,'EXACT_ALL_RECORD_AND_MOLECULE_POPULATION')
    need({r:{'records':totals[r],'molecules':molecules[r]} for r in role_authority}==role_authority,'ACTUAL_ROLE_RECORD_AND_WHOLE_MOLECULE_CONSERVATION')
    return result,dict(totals),dict(molecules)
