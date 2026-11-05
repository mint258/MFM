"""Exact failed5429 closed tables, preserved failure, and original TRAIN science."""
import csv,io,types
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v5 import contract as OLD
P=OLD.P;need=OLD.need;meta=OLD.meta;RUN=OLD.RUN;REPO=OLD.REPO;PY=OLD.PY
KEY='existing_sprime_fast55k_resume_v6';MODULE='workflows.data_v1_final.labels.'+KEY+'.run';HERE=REPO/'workflows/data_v1_final/labels'/KEY
FILES=('__init__.py','contract.py','metadata.py','run.py','geometry.py','geometry_tables.py','io.py','README.md')
OLDROOT=OLD.OLDROOT;PHASE_ROOT=OLD.PHASE_ROOT
GEOMETRY_ROOT=RUN/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v5/day05_cpu2_v1_pilot_provisional'
PILOT_COUNTS=OLD.PILOT_COUNTS;GLOBAL_SOURCE_COUNTS=OLD.GLOBAL_SOURCE_COUNTS
unique=OLD.unique;reference=OLD.reference;logical=OLD.logical;resume_authority=OLD.resume_authority;phase_authority=OLD.phase_authority

def __getattr__(name):return getattr(OLD,name)

def geometry_authority(p):
    r=meta(p['completed_geometry_review_reference']);a=r['parent_registration']
    need(r['schema']=='ROOT_COMPLETED_GEOMETRY_TABLES_FAILED5429_READONLY_REVIEW_V1'
      and r['status']=='APPROVED_CLOSED_SIX_TABLES_ONLY_FAILED_PARENT_NOT_PROMOTED'and r['reviewer']=='root'
      and r['old_output_root']==str(GEOMETRY_ROOT),'EXACT_READONLY_CLOSED_GEOMETRY_COMPONENTS_NOT_WHOLE_FAILED_PARENT')
    req,sub,proof,receipt=[meta(a[k])for k in('request_reference','submission_reference','proof_reference','receipt_reference')]
    need(req==sub['request']==proof['request']and req['scope_key']==OLD.KEY and req['cpus']==16 and req['node']=='compute-0-2'
      and str(sub['job_id'])==str(proof['job_id'])==str(receipt['job_id'])=='4525429','ACTUAL_FAILED5429_REGISTRATION_CHAIN')
    account=meta(a['accounting_reference']);raw,ref=P.small(a['raw_reference']['path'])
    rows=[x for x in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|')if x['JobIDRaw']=='4525429']
    need(account['query_returncode']==0 and account['uid']==1278 and account['raw_sacct_reference']==a['raw_reference']==ref
      and len(rows)==1 and rows[0]['State']=='FAILED'and rows[0]['ExitCode']=='1:0'and rows[0]['UID']=='1278'
      and rows[0]['AllocCPUS']=='16'and rows[0]['NodeList']=='compute-0-2','REAL_FAILED_PARENT_NO_C0_ALIAS')
    need(receipt['held']is True and len(receipt['errors'])==1
      and receipt['errors'][0]['message']=='ACTUAL_SAME_STORAGE_NODE_AND_ORIGINAL_FOOTER_SOURCE_GUARD_NOT_HASH_STAGE_ALIAS'
      and receipt['geometry_reference']is None and receipt['numeric_repetitions']==[]
      and r['failure_before_metadata_DB_or_any_numeric_statistics']is True,'ONLY_COMPLETED_G_BUILD_BEFORE_METADATA_FRAME_FAILURE')
    for name in OLD.FILES:need(P.pin(OLD.HERE/name)in req['source_references'],'EXACT_OLD_FROZEN_GEOMETRY_PRODUCER_SOURCE')
    return r,receipt

def scope(p):
    s=OLD.scope(p);s.update(purpose='CLOSED_SIX_GEOMETRY_TABLE_REUSE_THEN_ORIGINAL_CHILDREN_AND_TWO_TRAIN_REPLAYS',
      completed_geometry_review_reference=p.get('completed_geometry_review_reference'),closed_packet_reader_workers=0,
      maximum_pending_packet_reads=0,original_decoder_in_workers=False,closed_geometry_tables_reused=True,
      geometry_table_recomputation=False,temporary_sqlite_blob_codec='DV1Z1_ZLIB_ORIGINAL_LOSSLESS',
      frame_review_node='compute-0-2',all_original_table_count_hash_and_F64_verifications_retained=True)
    return s

def plan(p):
    f=OLD.plan;g=dict(f.__globals__,KEY=KEY,scope=scope)
    value=types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(p)
    geometry_authority(p);r=meta(p['source_metadata_frame_review_reference'])
    need(r['schema']=='ROOT_PILOT_RAW_METADATA_SOURCE_FRAME_REVIEW_V1'and r['status']=='APPROVED_ORIGINAL_INHERITED_SHA_FOOTER_FD_GUARD'
      and r['reviewer']=='root'and r['node']==p['node']=='compute-0-2'
      and r['source_inventory_reference']==p['source_inventory_reference']and r['footer_manifest_reference']==p['footer_manifest_reference']
      and r['fresh_original_Parquet_whole_SHA_claimed']is False,'CORRECT_ACTUAL_CPU2_FRAME_AUTHORITY_NO_SCIENTIFIC_CHANGE')
    return value
