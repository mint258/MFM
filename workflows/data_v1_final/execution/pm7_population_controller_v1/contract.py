"""Pure bounded slots, retirement and honest coverage; no scientific payloads."""
from __future__ import annotations
import hashlib,json,pathlib
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=pathlib.Path(__file__).absolute().parent;BASE=RUN/'control/pm7_population_controller_v1'
FILES=('__init__.py','contract.py','derive.py','controller.py','inventory_cpu.py','test_state.py','README.md')
CAP=64<<30;POOL=2*CAP;CONTROL_CAP=8<<30;INVENTORY_CAP=8<<20
SCHEMA='ROOT_RANGE_PM7_EXISTING247_REVIEW_V1';STATUS='APPROVED_FINITE_EXISTING247_FROZEN_TEMPLATE_DISPATCH'
TERMINAL={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED','SPECIAL_EXIT'}
POLICY='ROOT_DELEGATED_FROZEN_TEMPLATE_DERIVATION_NOT_NEW_PER_JOB_HUMAN_REVIEW'


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def key(row):return 'g%02d_s%05d'%(row['file_group'],row['shard_index'])


def descriptors(value):
    rows=value['descriptors'];need(value['schema']=='PM7_PRECOMMON_WHOLE_MOLECULE_SHARDS_PREPARED_V1'
        and len(rows)==247 and len({key(r) for r in rows})==247 and sum(r['molecules'] for r in rows)==1220466
        and sum(r['records'] for r in rows)==11231854 and all(0<r['molecules']<=5000 for r in rows),'EXACT_EXISTING247_WHOLE_MOLECULE_UNION')
    return {key(r):dict(r) for r in rows}


def retired(parent,closure,jid):
    if parent is None or parent['state']!='COMPLETED' or parent['exit_code']!='0:0':return False
    if not closure or closure.get('status')!='REGISTERED_PHASE_ALL_TERMINAL_NOT_GLOBAL_TASK_COMPLETE':return False
    rows=closure.get('states',[])
    return len(rows)==1 and str(rows[0].get('job_id'))==str(jid) and rows[0].get('state')=='COMPLETED' and rows[0].get('exit_code')=='0:0'


def receipt(receipt,row):
    need(receipt['schema']=='PM7_POPULATION_CACHE_BATCH_RECEIPT_V1' and receipt['status']=='SELECTION_DURABLY_CLOSED_ROOT_REVIEW_REQUIRED'
        and receipt['selection']==dict(file_group=row['file_group'],shard_index=row['shard_index'],offset=0,limit=row['molecules'])
        and receipt['selected_molecules']==receipt['durable_classified_molecules']==row['molecules']
        and receipt['selected_records']==row['records'] and receipt['unstarted_molecules']==receipt['consumed_without_validated_packet_molecules']==0
        and receipt['error_count']==0 and receipt['common'] is False and receipt['full_cache_release'] is False,'EXACT_DURABLE_WHOLE_SHARD_COVERAGE_NO_UNKNOWN')
    need(receipt.get('unknown_molecules',0)==0,'NO_CONSUMED_UNKNOWN_HIDDEN_BY_TECHNICAL_CLOSURE')
    # Known geometry/HOF/NULL QC states remain distinct from technical closure.
    need(receipt['geometry_complete_molecules']+receipt['geometry_pending_or_unresolved_molecules']==row['molecules']
        and receipt['selected_HOF_reader_records']==row['records'],'GEOMETRY_AND_HOF_COUNT_CONSERVATION')


def future_bytes(rows):return sum(CAP for row in rows.values() if row.get('job_id') and not row.get('retired'))
def capacity(rows):return sum(bool(r.get('job_id')) and not r.get('retired') for r in rows.values())<2


def next_action(rows,ordered):
    for name,row in rows.items():
        if row.get('ambiguous') or row.get('failed') or row.get('unknown'):return {'action':'HOLD','batch_id':name}
    if all(rows.get(k,{}).get('retired') for k in ordered):return {'action':'ALL_RETIRED_PENDING_CPU_INVENTORY'}
    if not capacity(rows):return {'action':'WAIT'}
    remaining=[k for k in ordered if not rows.get(k,{}).get('job_id')]
    return {'action':'DISPATCH','batch_id':remaining[0]} if remaining else {'action':'WAIT'}


def lease_allows(now,expires,wall):return now+wall+300<expires


def inventory_ready(state):
    return state.get('status')=='ALL247_RETIRED_PENDING_CPU_INVENTORY_AND_ROOT_REVIEW' and len(state.get('batches',{}))==247 and all(r.get('retired') for r in state['batches'].values())
