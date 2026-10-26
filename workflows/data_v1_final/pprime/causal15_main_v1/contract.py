"""Fixed six original calls and fifteen new QA executions, never a release."""
from __future__ import annotations
import hashlib,json,pathlib,re
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
HERE=pathlib.Path(__file__).absolute().parent;PPRIME=REPO/'workflows/data_v1_final/pprime'
BASE=RUN/'artifacts/pprime_causal15_main_v1';OLD=RUN/'artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';UID=1278;MID='molecule_01200493';CAP=2<<30
RAW_CAP=16<<20;RESULT_CAP=8<<20;INPUT_CAP=65536;TIMEOUT=900;WORKERS=15
FILES=('__init__.py','contract.py','io.py','render.py','prepare.py','execute.py','analysis.py','test_cases.py','metadata.py','README.md')
CASES={'pm7_B':('case-054','case-055'),'xtb_perturbed_gradient':('case-058','case-059'),
       'xtb_singlepoint_noisy_companion':('case-060','case-061')}
P90=[[0,-1,0],[1,0,0],[0,0,1]];ARMS=('B1','B2','R1','P1','P2')
INVENTORY={'path':str(PPRIME/'frame_native_precision_alpha_v2/origin_inventory.json'),'bytes':546050,'sha256':'83e58412628c6c0048f39b9cdc8f8ddda2bfe181eca8f9d7d74b40f9d99022cf'}
ENGINE_SHA='53c09b68938ead8449f0da2ec7a03337df3125826080ece58fabe107cdd9f26b'
NATIVE_SHA='6943612b2fd6c3c7a492c08183f2328230469dea5113aadc613c32378cc79b59'
AUDIT=PPRIME.parents[2]/'configs/data_v1/pprime/vector_frame_audit_root_v1.json'


def need(ok,message):
    if not ok:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def triple(value):
    result={k:value[k] for k in ('path','bytes','sha256')};p=pathlib.Path(result['path'])
    need(p.is_absolute() and '..' not in p.parts and type(result['bytes']) is int and result['bytes']>0
        and re.fullmatch('[0-9a-f]{64}',result['sha256']),'POSITIVE_ACTUAL_LITERAL_REFERENCE_REQUIRED');return result


def parameters(stage):
    need(stage in {'prepare','execute'},'FIXED_TWO_STAGE_ONLY')
    return {'stage':'PPRIME_CAUSAL15_'+stage.upper(),'pilot':False,'molecule_id':MID,'geometry_source':'pm7',
        'source_cases':[c for pair in CASES.values() for c in pair],'QA_calls':15,'maximum_workers':15,
        'new_QM_calls':0 if stage=='prepare' else 15,'new_UFF_calls':0,'task_timeout_seconds':TIMEOUT,
        'timeout_basis':'ACTUAL_FROZEN_PROTOCOL900_NO_TASK_OVERRIDE','same_original_record_id_and_seed':True,
        'source_input_authority':'EXACT_SIX_PINNED_RESULTS_TO_ORIGINAL_PER_CALL_SHA_AND_FIXED_INVENTORY_LOCATORS',
        'P90_arithmetic':'EXACT_DECIMAL_TOKEN_SIGNED_PERMUTATION_BEFORE_FLOAT64_BRIDGE',
        'resource_monitor_signals':False,'native_original_timeout_semantics_preserved':True,
        'whole_output_cap_bytes':CAP,'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'}


def source_identity(case_id,case):
    hits=[(condition,pair.index(case_id)) for condition,pair in CASES.items() if case_id in pair]
    need(len(hits)==1,'ONLY_FIXED_SIX_SOURCE_CASES');condition,index=hits[0]
    calc='xtb_singlepoint' if condition.endswith('companion') else condition
    need(case['case_id']==case_id and case['molecule_id']==MID and case['geometry_source']=='pm7'
        and case['condition']==condition and case['calc_type']==calc and case['arm']==('base','rotated')[index],
        'EXACT_ORIGINAL_SIX_CASE_IDENTITY_REQUIRED')
    rid='vector-audit:'+MID+':pm7'+(':noisy-companion' if condition.endswith('companion') else '')
    need(case['row']['record_id']==rid and case['row']['molecule_id']==MID,'ORIGINAL_RECORD_ID_SEED_MUST_NOT_CHANGE')
    return condition


def key(prepared,qa_id):return sha(canonical(['independent-pprime-causal15-QA-once-v1',triple(prepared),qa_id]))
