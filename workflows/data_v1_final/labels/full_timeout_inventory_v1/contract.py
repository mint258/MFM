"""Pure evidence and cursor boundaries, independent of any scientific body."""
from __future__ import annotations
import csv,json,re
from pathlib import Path
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=RUN/'repository';PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
HERE=REPO/'workflows/data_v1_final/labels/full_timeout_inventory_v1'
KEY='labels_full_timeout_inventory_v1'
MODULE='workflows.data_v1_final.labels.full_timeout_inventory_v1.run'
STAGE='LABELS_FULL_TIMEOUT_COMMITTED_WINDOW_READONLY_INVENTORY'
SCHEMA='LABELS_FULL_TIMEOUT_INVENTORY_PLAN_V1'
STATUS='PARTIAL_TIMEOUT_EVIDENCE_NOT_OLD_C0'
OLD=RUN/'artifacts/labels/source_status_v1/full_projection_batch0000_v1'
BOOK=RUN/'control/labels_full_bounded32_dispatch_v1.sqlite'
PARAMETERS={'original_job_id':'4521904','original_state':'TIMEOUT','original_parent_c0':False,
 'workers':16,'fixture_count':3,'readonly_old_outputs':True,'release_dispatcher_lease':False,
 'whole_output_cap_bytes':2<<30,'new_UFF_QM_calls':0,'normalization':False,
 'candidate_masks_frozen':False,'full_population_completed':False,'automatic_retry':False}
FRAME=('device','inode','bytes','mtime_ns','ctime_ns','uid','mode','nlink')


def need(ok,code):
    if not ok:raise ValueError(code)


def triple(ref):
    need(isinstance(ref,dict) and set(('path','bytes','sha256'))<=set(ref),'EXACT_REFERENCE_REQUIRED')
    p=Path(ref['path']);need(p.is_absolute() and '..' not in p.parts and type(ref['bytes']) is int and ref['bytes']>=0
      and re.fullmatch('[0-9a-f]{64}',ref['sha256']) is not None,'LITERAL_REFERENCE_AND_REAL_SHA_REQUIRED')
    return {k:ref[k] for k in ('path','bytes','sha256')}


def option(argv,name):
    need(argv.count(name)==1 and argv.index(name)+1<len(argv),'EXACT_OPTION:'+name)
    return argv[argv.index(name)+1]


def parent_chain(account,raw,request,proof,submission,config,config_ref):
    need(account.get('schema')=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
      and account.get('status')=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and account.get('query_returncode')==0
      and account.get('endpoint')=='202.38.247.57:22' and account.get('uid')==1278,'ACTUAL_MAIN_ACCOUNT_REQUIRED')
    parents=account.get('parents',[]);need(len(parents)==1,'EXACT_ONE_ORIGINAL_PARENT')
    p=parents[0]
    need(str(p.get('job_id'))=='4521904' and p.get('state')=='TIMEOUT' and p.get('exit_code')=='0:0'
      and p.get('alloc_cpus')==16 and p.get('elapsed_raw_seconds')==14412
      and p.get('node')=='compute-0-17' and account.get('allocated_core_seconds')==230592,
      'TIMEOUT_ZERO_EXIT_IS_NOT_C0_AND_ALL_REAL_COST_RETAINED')
    rows=list(csv.DictReader(raw.splitlines(),delimiter='|'))
    row=[r for r in rows if r.get('JobIDRaw')=='4521904'];need(len(row)==1,'EXACT_RAW_PARENT')
    r=row[0]
    need([r.get(k) for k in ('State','ExitCode','ElapsedRaw','AllocCPUS','NodeList','UID')]
      ==['TIMEOUT','0:0','14412','16','compute-0-17','1278'],'RAW_PARENT_FIELDS_DIFFER')
    need(proof.get('schema')=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and proof.get('uid')==1278
      and proof.get('node')=='compute-0-17' and submission.get('schema')=='CPU_AUTO_MEMORY_SUBMISSION_V1'
      and submission.get('uid')==1278,'HISTORICAL_MAIN_UID_NODE_AND_SCHEMAS')
    need(submission.get('job_id')=='4521904' and submission.get('sbatch_returncode')==0
      and submission.get('request')==request and proof.get('request')==request
      and str(proof.get('job_id'))=='4521904','ACTUAL_SUBMISSION_REQUEST_PROOF_CHAIN')
    argv=request['execution_argv']
    need(argv[:4]==[PY,'-B','-m','workflows.data_v1_final.labels.full_projection_v1.run']
      and len(argv)==10 and option(argv,'--output')==str(OLD)
      and option(argv,'--config')==config_ref['path'] and config_ref in request['source_references']
      and option(argv,'--startup-proof')==request['startup_proof_path'],'EXACT_ORIGINAL_FULL_PRIMARY_OPTIONS')
    need(config.get('schema')=='FULL_LABEL_PROJECTION_BATCH_CONFIG_V1'
      and config.get('dispatch_book_path')==str(BOOK) and config.get('batch_name')=='full_batch0000',
      'EXACT_FROZEN_FULL_BATCH_CONFIG')
    return {'original_parent_state':'TIMEOUT','original_parent_exit_code':'0:0','original_parent_c0':False,
      'allocated_core_seconds':230592,'all_raw_parent_and_step_rows':rows}


def cursor_chain(ranges,tickets,windows,expected):
    """Metadata conservation, NOT scientific acceptance of referenced parts."""
    want={r['range_id']:r for r in expected};need(len(want)==len(expected),'UNIQUE_EXPECTED_RANGES')
    got={r['range_id']:r for r in ranges};need(len(got)==len(ranges) and set(got)==set(want),'EXACT_RANGE_SET')
    ts={t['ticket']:t for t in tickets};need(len(ts)==len(tickets),'UNIQUE_TICKETS')
    ws={};closed=set()
    for w in windows:
        need(w['range_id'] in want and (w['range_id'],w['lo']) not in ws,'UNIQUE_KNOWN_WINDOW')
        ws[w['range_id'],w['lo']]=w
        candidates=[t for t in tickets if t['range_id']==w['range_id'] and t['lo']==w['lo'] and t['status']=='CLOSED'
          and t['receipt']==w['receipt']]
        need(len(candidates)==1,'ONE_MATCHING_CLOSED_TICKET_RECEIPT');closed.add(candidates[0]['ticket'])
    need({t['ticket'] for t in tickets if t['status']=='CLOSED'}==closed,'NO_CLOSED_TICKET_WITHOUT_WINDOW')
    for key,e in want.items():
        r=got[key];need(r['stop']==e['physical_row_hi'] and e['physical_row_lo']<=r['cursor']<=r['stop'],'CURSOR_INSIDE_ORIGINAL_TILE')
        pos=e['physical_row_lo']
        for w in sorted((w for w in windows if w['range_id']==key),key=lambda x:x['lo']):
            need(w['lo']==pos<w['hi']<=r['cursor'],'CONTIGUOUS_NONOVERLAPPING_COMMITTED_PREFIX');pos=w['hi']
        need(pos==r['cursor'],'CURSOR_EQUALS_EXACT_COMMITTED_WINDOW_PREFIX')
    for key in got:
        need(sum(t['range_id']==key and t['status']!='CLOSED' for t in tickets)<=1,'ONE_UNPUBLISHED_TICKET_PER_RANGE')
    for t in tickets:
        need(t['range_id'] in want and t['status'] in ('CLOSED','RESERVED','UNKNOWN_UNPUBLISHED')
          and type(t['amount']) is int and t['amount']>0 and t['inodes']>0,'KNOWN_POSITIVE_TICKET')
        if t['status']!='CLOSED':need(t['lo']==got[t['range_id']]['cursor'],'UNPUBLISHED_TICKET_AT_UNCLOSED_CURSOR')
    return {'ranges':len(ranges),'committed_windows':len(windows),'unpublished_tickets':sum(t['status']!='CLOSED' for t in tickets)}


def completed_window(body,window,parts):
    need(body.get('schema')=='BOUNDED_TYPED_PHYSICAL_WINDOW_V1'
      and body.get('range_id')==window['range_id'] and body.get('physical_row_lo')==window['lo']
      and body.get('physical_row_hi')==window['hi'] and body.get('all_part_reopen_bits_verified') is True,
      'COMMITTED_RECEIPT_IDENTITY')
    classifications=body['physical_classifications']
    need(all(type(v) is int and v>=0 for v in classifications.values())
      and sum(classifications.values())==window['hi']-window['lo'],'WINDOW_PHYSICAL_MASS')
    need(len(parts)==len(body['parts']) and all(p['status']=='VERIFIED_TYPED_PART' for p in parts),
      'MISSING_UNVERIFIED_OR_CONFLICTING_PART_NOT_COMPLETE')
    need(sum(p['rows'] for p in parts)==classifications.get('CANONICAL',0),'CANONICAL_ROW_PART_MASS')
    return True


def file_class(relative,committed):
    if relative in committed:return 'COMMITTED_REFERENCE_REQUIRES_CPU_VERIFICATION'
    if relative.endswith('.partial'):return 'UNCOMMITTED_PARTIAL_NEVER_COMPLETED'
    if relative.startswith('parts/'):return 'UNCOMMITTED_ORPHAN_NEVER_COMPLETED'
    return 'AUXILIARY_OR_UNKNOWN_NEVER_IMPLICIT_COMPLETED'