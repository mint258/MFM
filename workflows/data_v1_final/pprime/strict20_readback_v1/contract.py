"""Actual C0 authority, two finite stages and disjoint SOURCE/DATA references."""
from __future__ import annotations
import json,pathlib,re
from workflows.data_v1_final.pprime.strict_numerics20_qa_v1 import contract as E
Q=E.Q;F=E.F;meta=E.meta;need=Q.need;ROOT=Q.ROOT;REPO=Q.REPO;PY=Q.PY
HERE=REPO/'workflows/data_v1_final/pprime/strict20_readback_v1'
FILES=('__init__.py','contract.py','io.py','checks.py','inventory.py','replay.py','run.py','metadata.py','test_v1.py','frozen_sources.json','README.md')
MODULE='workflows.data_v1_final.pprime.strict20_readback_v1.run'
BASE=ROOT/'artifacts/labels/source_status_v1/strict20_readback_v1'
ACTUAL=ROOT/'artifacts/pprime_strict20_all12_qa_v1/run_v1'
REVIEW=ROOT/'control/root_actual_new20_all12_1200_limited_diagnostic_review_v1.json'
JOB='4524436';WALL=7200;CAP=1<<30;RESERVE=128<<20
SHA=re.compile('[0-9a-f]{64}')

def triple(r,*,source=False):
    need(isinstance(r,dict) and all(k in r for k in ('path','bytes','sha256')),'ACTUAL_REFERENCE_REQUIRED')
    v={k:r[k] for k in ('path','bytes','sha256')};p=pathlib.Path(v['path'])
    need(p.is_absolute() and '..' not in p.parts and type(v['bytes']) is int and v['bytes']>=(0 if source else 1)
        and isinstance(v['sha256'],str) and SHA.fullmatch(v['sha256']) is not None,'POSITIVE_NONBOOL_LITERAL_DATA_OR_EXACT_SOURCE')
    if v['bytes']==0:need(source and v['sha256']=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855','EXACT_EMPTY_SOURCE_ONLY')
    return v

def unique(refs,*,source=False):
    out={}
    for r in refs:
        r=triple(r,source=source);need(r['path'] not in out or out[r['path']]==r,'SAME_PATH_DIFFERENT_PRODUCER_PIN');out[r['path']]=r
    return list(out.values())

def within(ref,roots):
    r=triple(ref);p=pathlib.Path(r['path'])
    need(any(p==pathlib.Path(root) or pathlib.Path(root) in p.parents for root in roots),'EXACT_ACTUAL_CLOSED_ROOT_ONLY')
    return r

def scope(mode):need(mode in ('inventory','audit'),'TWO_READONLY_STAGES_ONLY');return 'strict20_readback_'+mode+'_v1'

def cap(mode):scope(mode);return (256 if mode=='inventory' else 32)<<20
def reserve(mode):scope(mode);return (64 if mode=='inventory' else 10)<<20

def parameters(mode,group=None):
    scope(mode)
    if mode=='audit':need(type(group)is int and 0<=group<20,'EXACT_ONE_ORIGINAL_MOLECULE_INDEX')
    else:need(group is None,'INVENTORY_HAS_NO_GROUP')
    return {'mode':mode,'group_index':group,'original_job':JOB,'original_molecules':20,'conditions':12,'arms':5,
        'calls':1200 if mode=='inventory' else 60,'original_vector_comparisons':500 if mode=='inventory' else 25,
        'allocated_cpus':16,'readonly_worker_threads':1,'new_pure_boundary_methods':3,'all3_before_DATA':True,'native_initialize_or_invoke_calls':0,
        'new_QM_UFF_calls':0,'original_readers_and_defined_comparison_objects':True,'typed_float64_bit_parity':True,
        'inline_native_processing_independently_replayed':False,'original_masks_tolerances_and_evidence_unchanged':True,
        'automatic_retry':False,'scientific_PASS':False,'full_or2000_release':'HOLD','wall_seconds':WALL,'output_cap_bytes':cap(mode),
        'all21_stage_partition_caps_plus_technical_metadata_reserve_bytes':CAP}

def sources():
    frozen=json.loads((HERE/'frozen_sources.json').read_text())
    need(frozen['schema']=='STRICT20_READBACK_ORIGINAL_SOURCE_OBJECT_PINS_V1','ORIGINAL_SOURCE_OBJECT_AUTHORITY')
    paths=[*(HERE/n for n in FILES),*E.sources()]
    for directory in ('export/native_body_frame32_v1','export/native_availability_v1',
        'labels/source_status_cpu_auto_memory_v1','execution/cpu_auto_memory_queue_v2'):
        paths.extend((REPO/'workflows/data_v1_final'/directory).glob('*.py'))
    for r in frozen['references']:
        triple(r,source=True);need(Q.pin(r['path'])==r,'ORIGINAL_SOURCE_OBJECT_BYTES_CHANGED');paths.append(pathlib.Path(r['path']))
    return list(dict.fromkeys(paths))

def audit_ref():return triple(json.loads((HERE/'frozen_sources.json').read_text())['audit_configuration_DATA_reference'])

def parents(plan):
    rr=triple(plan['actual_root_review_reference']);need(rr['path']==str(REVIEW),'SPECIFIC_ACTUAL_ROOT_REVIEW')
    r=meta(rr);need(r['schema']=='ROOT_ACTUAL_NEW20_ALL12_STRICT_QA_LIMITED_TECHNICAL_REVIEW_V1'
        and r['status']=='ACTUAL_C0_ALL1200_DEFINED_DIAGNOSTIC_QA_CLOSED_NO_2000_FULL_RELEASE' and r['reviewer']=='root'
        and r['actual_returned_terminals']==1200 and r['original_vector_comparisons']==500
        and r['scientific_PASS'] is False and r['full_or2000_release']=='HOLD'
        and r['native_units_sign_origin_axes_accepted'] is False,'ACTUAL_LIMITED1200_NOT_PHYSICAL_RELEASE')
    ep=meta(r['plan_reference']);proof=meta(r['startup_proof_reference']);E.require_user(ep)
    need(ep['schema']=='PPRIME_NEW20_ALL12_USER_AUTHORIZED_QA_PLAN_V1' and ep['scope_parameters']==E.PARAMETERS
        and ep['output_directory']==str(ACTUAL) and ep['user_decision_reference']==r['user_decision_reference']
        and str(proof['job_id'])==JOB and proof['uid']==1278 and proof['request']['scope_key']==E.KEY
        and proof['request']['scope_parameters']==E.PARAMETERS and proof['request']['data_references']==ep['data_references']
        and proof['request']['cpus']==16 and proof['request']['node']=='compute-0-13','ACTUAL_EXECUTION_PLAN_PROOF_EXACT')
    _,raw=F.account(r['accounting_reference'],JOB,'compute-0-13');need(raw==r['raw_accounting_reference'],'ACTUAL_C0_RAW_ACCOUNT_PIN')
    need(r['receipt_reference']['path']==str(ACTUAL/'receipt.json')
        and r['analysis_DATA_locator_not_opened_or_hashed_on_login']['path']==str(ACTUAL/'defined_QA_checks.DATA.json'),'EXACT_CLOSED_OUTPUT_NAMES')
    prepare_root=pathlib.Path(ep['prepared20_reference']['path']).parent
    need(ROOT/'artifacts' in prepare_root.parents and prepare_root!=ACTUAL and not prepare_root.is_symlink(),'ACTUAL_PREPARED_ROOT_NOT_FUTURE')
    data=unique([r['receipt_reference'],r['analysis_DATA_locator_not_opened_or_hashed_on_login'],ep['prepared20_reference']])
    refs=unique([rr,r['plan_reference'],r['startup_proof_reference'],r['accounting_reference'],raw,r['user_decision_reference'],
        ep['original_protocol_reference'],ep['candidate_protocol_reference'],ep['prepare_accounting_reference']])
    if plan['mode']=='audit':
        c=meta(plan['inventory_closure_reference']);need(c['schema']=='STRICT20_READBACK_ACTUAL_STAGE_C0_V1'
            and c['mode']=='inventory' and c['status']=='ACTUAL_READONLY_STAGE_C0_NOT_PHYSICAL_ACCEPTANCE','ACTUAL_INVENTORY_C0_BEFORE_AUDIT')
        m,_,_=actual(c['closure_references']);need(c['manifest_reference']==c['closure_references']['manifest']
            and m['schema']=='STRICT20_READBACK_MANIFEST_V1' and m['mode']=='inventory'
            and m['status']=='COMPLETE_READONLY_EVIDENCE_PHYSICAL_UNKNOWN' and m['completed_calls']==1200 and m['held_calls']==0
            and m['actual_root_review_reference']==rr and len(m['groups'])==20,'ACTUAL_COMPLETE_INVENTORY_LOCATORS')
        g=meta(m['groups'][plan['group_index']]);need(g['schema']=='STRICT20_READBACK_GROUP_LOCATORS_V1'
            and g['group_index']==plan['group_index'] and g['calls']==60,'EXACT_ACTUAL_GROUP_LOCATORS')
        data=unique(g['data_references']);refs=unique([*refs,plan['inventory_closure_reference'],c['manifest_reference'],m['groups'][plan['group_index']]])
        plan_group=g
    else:plan_group=None
    return r,ep,data,refs,prepare_root,plan_group

def actual(refs):
    from workflows.data_v1_final.export.native_body_frame32_v1.contract import actual_closure
    m=meta(refs['manifest']);mode=m['mode'];params=parameters(mode,m.get('group_index'))
    m,p,extra=actual_closure(refs,mode,'STRICT20_READBACK_MANIFEST_V1','COMPLETE_READONLY_EVIDENCE_PHYSICAL_UNKNOWN',MODULE,scope(mode),params)
    need(p['scope_parameters']==params and p['wall_seconds']==WALL and p['output_cap_bytes']==cap(mode)
        and m['uid']==1278 and m['node']=='compute-0-13' and m['endpoint']=='202.38.247.57:22'
        and m['held_calls']==0 and m['new_QM_UFF_calls']==m['native_initialize_or_invoke_calls']==0
        and m['scientific_PASS'] is False and m['full_or2000_release']=='HOLD'
        and m['native_units_sign_basis_origin_axes_accepted'] is False,'ACTUAL_TECHNICAL_ONLY_STAGE_CLOSURE')
    gate=meta(m['source3_reference']);need(gate['tests_run']==3 and all(gate[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_NEW3_ALL_PASS')
    for r in p['source_references']:need(Q.pin(r['path'])==r,'ACTUAL_STAGE_SOURCE_AND_SMALL_PARENT_BYTES_STILL_EXACT')
    if mode=='inventory':need(m['completed_calls']==1200 and len(m['groups'])==20,'ACTUAL_INVENTORY1200_NOT_PARTIAL')
    else:need(m['completed_calls']==60 and m['original_own_exact_checks']==m['original_pair_exact_checks']==60
        and m['original_vector_exact_comparisons']==25 and m['all60_and25_exact'] is True and not m['errors'],'ACTUAL60_ALL25_ORIGINAL_VECTOR_COMPARISONS')
    return m,p,extra
