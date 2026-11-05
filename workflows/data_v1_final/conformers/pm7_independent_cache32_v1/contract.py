"""Pure cache identity/selection/software-bound contracts."""
from __future__ import annotations
import hashlib,json,pathlib
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=RUN/'repository';BASE=RUN/'artifacts/conformers/pm7_independent_cache32_v1'
PROFILE=REPO/'workflows/data_v1_final/conformers/statistics_v1'
FILES=('__init__.py','contract.py','inheritance.py','io.py','core.py','prepare32.py','run32.py','test_cache.py','schemas.json','README.md')
CPUS=16;CAP=8<<30;PACKET_CAP=128<<20;TASK_CAP=8<<20
MAX_RECORDS=300;MAX_ATOMS=10000;SHARD_MOLECULES=5000
SCIENCE_SOURCE={'path':'/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/scripts/sprime_v6.py','bytes':20644,'sha256':'d6f1d29a6de673a1faf186e095c4fef7534a81022a09a4840ec65e5d8fa424d3'}
SCIENCE_PREPARE={'path':'/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/scripts/prepare.py','bytes':6040,'sha256':'4b10dc5c0c2c1f3c42250ca1c8541c43661ada301484f92a6ce7bfce512f4a10'}


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(value):return hashlib.sha256(canonical(value)).hexdigest()
def q(value):return "'"+str(value).replace("'","''")+"'"
def stable(domain,mid):return hashlib.sha256(('pm7-independent-cache-v1:'+domain+':'+mid).encode()).hexdigest()


def software_bound(records,max_atoms):
    if not(type(records) is int and records>0 and type(max_atoms) is int and max_atoms>0):
        return {'status':'PENDING_SOURCE_DIMENSIONS_UNVERIFIED','records':records,'maximum_total_atoms':max_atoms,
            'packet_reserve_bytes':4*TASK_CAP,'scientific_N_truncated':False,'replacement_member_selected':False}
    bound=(2<<20)+128*records*max_atoms+128*records*records
    good=records<=MAX_RECORDS and max_atoms<=MAX_ATOMS and bound<=PACKET_CAP
    return {'status':'WITHIN_SOFTWARE_BOUND' if good else 'PENDING_SELECTED_SOURCE_EXCEEDS_SOFTWARE_BOUND',
        'records':records,'maximum_total_atoms':max_atoms,'packet_reserve_bytes':bound,
        'scientific_N_truncated':False,'replacement_member_selected':False}


def pick_golden(rows):
    need(len(rows)==len({r['molecule_id'] for r in rows})==256,'EXACT_ORIGINAL_CLOSED256_MANIFEST_REQUIRED')
    return sorted(rows,key=lambda r:(stable('golden',r['molecule_id']),r['molecule_id']))[:16]


def missing_hof(reason):
    return {'value_kcal_mol':None,'valid':False,'reason':reason,'converged':None,'convergence_null_review':False,
        'registry_id':60,'task':'pm7_B','source_status':None}


def validate_hof(value):
    import math
    need(value.get('registry_id')==60 and value.get('task')=='pm7_B','ONLY_CANONICAL_REGISTRY60_PM7_B_HOF')
    if value['valid']:
        need(value['reason'] is None and value['value_kcal_mol'] is not None and math.isfinite(float(value['value_kcal_mol'])),'VALID_HOF_MUST_BE_REAL_FINITE_VALUE')
    else:need(value['value_kcal_mol'] is None and bool(value['reason']),'MISSING_HOF_HAS_REASON_AND_NO_FAKE_ZERO')


def scope(stage):
    need(stage in {'prepare32','run32'},'EXACT_BOUNDED_CACHE_STAGE')
    return {'stage':'PM7_INDEPENDENT_CACHE32_'+stage.upper(),'pilot':False,'molecules':32,'golden':16,'independent':16,
        'maximum_workers':16,'new_UFF_calls':0,'new_QM_calls':0,'no_Sprime_SUCCESS_filter':True,'no_Sprime_anchor':True,
        'source_mother_molecules':1220466,'source_records':11231854,'record_ID_basis':'NATIVE_RECORD_ID',
        'rmsd_A':0.5,'order_seed':20261025,'whole_output_cap_bytes':CAP,'common':False,'full_cache_release':False,
        'future_shard_roster_preparation_only':True,'physical_int64_or_production_release':False,
        'input_authority':'PINNED_CANONICAL_POINTERS_PLUS_PER_RECORD_NATIVE_PAYLOAD_SHA_AND_EXACT_FROZEN_HOF_OWNER',
        'cost_policy':'REPORT_AND_CONTINUE'}
