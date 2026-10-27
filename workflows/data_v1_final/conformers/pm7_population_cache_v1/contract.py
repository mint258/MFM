"""Bounded whole-molecule membership, identities and conservation; no science."""
from __future__ import annotations
import hashlib,json,pathlib
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=RUN/'repository';HERE=pathlib.Path(__file__).absolute().parent
BASE=RUN/'artifacts/conformers/pm7_population_cache_v1';LEDGER=BASE/'claims'
FILES=('__init__.py','contract.py','io.py','worker.py','run.py','metadata.py','test_boundaries.py','README.md')
CAP=64<<30;RESERVE=64<<20;MAX_MOLECULES=5000;MAX_RECORDS=100000
POPULATION_MOLECULES=1220466;POPULATION_RECORDS=11231854;CPUS=16
SCHEMA='ROOT_PM7_POPULATION_CACHE_BATCH_PLAN_V1';STATUS='APPROVED_EXACT_WHOLE_MOLECULE_CACHE_BATCH'
SCOPE='pm7_population_cache_v1_batch';OPTIONS=('plan','root-preflight','quota-reuse-review','output')


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def q(v):return "'"+str(v).replace("'","''")+"'"
def reference(r):
    p=pathlib.Path(r['path']);need(p.is_absolute() and '..' not in p.parts and type(r['bytes']) is int and r['bytes']>0
        and len(r['sha256'])==64 and all(c in '0123456789abcdef' for c in r['sha256']),'ACTUAL_LITERAL_PIN_REQUIRED')
    return {k:r[k] for k in ('path','bytes','sha256')}


def selection(value):
    need(set(value)=={'file_group','shard_index','offset','limit'},'EXACT_SELECTION_FIELDS')
    need(all(type(value[k]) is int for k in value),'INTEGER_SELECTION_NOT_BOOL')
    need(value['file_group']>=0 and value['shard_index']>=0 and 0<=value['offset']<MAX_MOLECULES
         and 1<=value['limit']<=MAX_MOLECULES-value['offset'],'FINITE_CONTIGUOUS_WHOLE_MOLECULE_SELECTION')
    return dict(value)


def scope(selected):
    return {'stage':'PM7_PRECOMMON_POPULATION_CACHE_BATCH','selection':selection(selected),'pilot':False,
        'source_molecules':POPULATION_MOLECULES,'source_records':POPULATION_RECORDS,'maximum_workers':CPUS,
        'maximum_batch_molecules':MAX_MOLECULES,'maximum_batch_records':MAX_RECORDS,'whole_output_cap_bytes':CAP,
        'legacy_budget_owned_disk_soft_stop_bytes':8<<30,'effective_disk_soft_stop_bytes':min(8<<30,CAP),
        'record_ID_basis':'NATIVE_RECORD_ID','rmsd_A':0.5,'order_seed':20261025,'canonical_HOF_registry':60,
        'canonical_HOF_unit':'kcal/mol','native_energy_fallback':False,'no_Sprime_filter_or_anchor':True,
        'new_QM_calls':0,'new_UFF_calls':0,'geometry_generation_calls':0,'common':False,'full_cache_release':False,
        'physical_int64_or_D7_order_release':False,'cost_policy':'REPORT_AND_CONTINUE',
        'existing_claim_authority':'FIXED_NAMESPACE_CLAIM_AND_DETERMINISTIC_TASK_START_PACKET_FINISHED_LOCATORS_WITH_REAL_PARENT_ACCOUNTING'}


def task_key(formal,hof,records):
    need(records and len(records)==len({r['record_id'] for r in records}),'WHOLE_DISTINCT_RECORD_SET')
    mids={r['molecule_id'] for r in records};need(len(mids)==1,'NO_MOLECULE_MIX')
    return digest(['PM7_POPULATION_CACHE_NATIVE_V1',reference(formal),reference(hof),
                   [(r['record_id'],r['record_payload_sha256']) for r in sorted(records,key=lambda x:x['record_id'])]])


def classify_claim(claim,terminal,finished_valid=False,evidence_exists=False):
    if claim is None:return 'UNKNOWN_ORPHAN_EVIDENCE' if evidence_exists else 'PROVEN_UNSTARTED'
    if terminal is None:return 'UNKNOWN_PARENT_ACCOUNTING_REQUIRED'
    return 'DURABLE_PACKET_RECOVERED' if finished_valid else 'UNKNOWN_CONSUMED_NO_COMPLETE_PACKET'


def conservation(expected,rows):
    mids=[r['molecule_id'] for r in rows];need(len(mids)==len(set(mids)),'DUPLICATE_CLOSED_MOLECULE')
    need(set(mids)<=set(expected),'CACHE_OUTSIDE_FROZEN_SELECTION')
    done=set(mids);unstarted=[mid for mid in expected if mid not in done]
    need(len(done)+len(unstarted)==len(expected),'MOLECULE_CONSERVATION')
    return unstarted


def reserve(meta):
    n=meta['records'];atoms=meta['maximum_total_atoms']
    # The inherited kernel's actual software dimensions, plus two bounded
    # 16KiB diagnostic event prefixes per record, task and provenance overhead.
    return (2<<20)+128*n*atoms+128*n*n+32768*n+(2<<20)


def error_reason(text):
    # Exact frozen source error tokens, otherwise the exception class. Full
    # messages remain per record; this is reporting, not a new QC predicate.
    codes=('ACTUAL_RECORD_MANIFEST_MISMATCH','SOURCE_GRAPH_MISSING','SOURCE_GRAPH_SHAPE',
        'SOURCE_BOND_TYPE_UNRESOLVED','SOURCE_GEOMETRY_INVALID','FIXED_SOURCE_ATOM_SEQUENCE_OR_GRAPH_MISMATCH',
        'SOURCE_ATOM_COUNT_CHANGED','ONLY_CANONICAL_REGISTRY60_PM7_B_HOF','VALID_HOF_MUST_BE_REAL_FINITE_VALUE',
        'MISSING_HOF_HAS_REASON_AND_NO_FAKE_ZERO','FINITE_ORIGINAL_RMSD_CACHE_REQUIRED')
    return next((code for code in codes if code in str(text)),str(text).split('(',1)[0][:80])
