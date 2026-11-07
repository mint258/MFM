"""Closed5337 geometry packets and typed cache; unchanged frozen55k science."""
import csv,io,types
from pathlib import Path
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3 import contract as OLD
P=OLD.P;need=OLD.need;meta=OLD.meta;RUN=OLD.RUN;REPO=OLD.REPO;PY=OLD.PY
KEY='existing_sprime_fast55k_resume_v4';MODULE='workflows.data_v1_final.labels.'+KEY+'.run';HERE=REPO/'workflows/data_v1_final/labels'/KEY
FILES=('__init__.py','contract.py','metadata.py','run.py','geometry.py','resource_census.py','README.md')
OLDROOT=OLD.OLDROOT
PHASE_ROOT=RUN/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v3/day03_cpu2_v1_pilot_provisional'
PILOT_COUNTS=OLD.PILOT_COUNTS;GLOBAL_SOURCE_COUNTS=OLD.GLOBAL_SOURCE_COUNTS
unique=OLD.unique;reference=OLD.reference;logical=OLD.logical;resume_authority=OLD.resume_authority

def __getattr__(name):return getattr(OLD,name)

def phase_authority(p):
    r=meta(p['closed_phase_review_reference']);a=r['parent_registration']
    need(r['schema']=='ROOT_CLOSED55K_GEOMETRY_RESOURCE_CONTINUATION_V1' and r['status']=='APPROVED_READONLY_CLOSED5337_CACHE_AND_GEOMETRY_PACKETS'
      and r['reviewer']=='root' and r['old_output_root']==str(PHASE_ROOT) and r['old_writes_or_QM_or_reselection']is False,'EXPLICIT_CLOSED_PHASE_REUSE')
    req,sub,proof,old,receipt=[meta(a[k])for k in ('request_reference','submission_reference','proof_reference','plan_reference','receipt_reference')]
    need(req==sub['request']==proof['request'] and sub['request_reference']==proof['request_reference']==a['request_reference']
      and str(sub['job_id'])==str(proof['job_id'])==str(receipt['job_id'])=='4525337' and sub['sbatch_returncode']==0
      and req['scope_key']==OLD.KEY and req['cpus']==16 and req['node']=='compute-0-2' and old['output_directory']==str(PHASE_ROOT), 'ACTUAL_CLOSED_PHASE_PARENT_CHAIN')
    account=meta(a['accounting_reference']);raw,ref=P.small(a['raw_reference']['path'])
    rows=[x for x in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|')if x['JobIDRaw']=='4525337']
    need(account['query_returncode']==0 and account['uid']==1278 and account['raw_sacct_reference']==a['raw_reference']==ref
      and len(rows)==1 and rows[0]['UID']=='1278' and rows[0]['State']=='COMPLETED' and rows[0]['ExitCode']=='0:0'
      and int(rows[0]['AllocCPUS'])==16 and rows[0]['NodeList']=='compute-0-2','ACTUAL5337_C0_NOT_COMPLETED_D4')
    need(receipt['status']=='DAY_DURABLE_PARTIAL_PENDING_EXPLICIT_ROOT_CONTINUATION' and not receipt['held'] and not receipt['errors']
      and receipt['coverage_reference']['path']==str(PHASE_ROOT/'typed_coverage/manifest.json') and receipt['geometry_reference']is None
      and receipt['numeric_repetitions']==[],'CLOSED_COVERAGE_AND_PACKETS_ONLY_NOT_FINAL_D4')
    for name in OLD.FILES:need(P.pin(OLD.HERE/name)in req['source_references'],'CLOSED_PHASE_SOURCE_IMMUTABLE')
    return r,old,proof,receipt

def scope(p):
    v=OLD.scope(p)
    v.update(purpose='READONLY_COMPLETE55K_PACKETS_AND_CLOSED_TYPED_CACHE_THEN_ORIGINAL_TABLES_D4',
      closed_phase_review_reference=p['closed_phase_review_reference'],resource_census='FULL_AT_WRITES_FORCE_OBSERVER_FINAL_AND_AT_MOST_ONE_SECOND_BETWEEN_TABLE_ROW_CHECKS',
      geometry_packet_recomputation=False,original_geometry_table_projection_AST_tail=True)
    return v

def plan(p):
    f=OLD.plan;g=dict(f.__globals__,KEY=KEY,scope=scope)
    x=types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(p)
    phase_authority(p);need(p['node']=='compute-0-2','REUSE_EXISTING_SAME_STORAGE_CPU2_METADATA_AUTHORITY');return x
