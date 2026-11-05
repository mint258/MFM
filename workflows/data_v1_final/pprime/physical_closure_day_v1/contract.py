"""Exact closed parents and DATA locators; metadata never opens scientific DATA."""
from __future__ import annotations
import pathlib,re
from workflows.data_v1_final.pprime.strict20_readback_v1 import contract as P,checks as K
from workflows.data_v1_final.export.native_frame_summary32_v1 import contract as N
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import contract as Day
Q=P.Q;F=P.F;ROOT=P.ROOT;REPO=P.REPO;PY=P.PY;need=P.need;meta=P.meta;unique=P.unique
HERE=REPO/'workflows/data_v1_final/pprime/physical_closure_day_v1'
FILES=('__init__.py','contract.py','io.py','reduce.py','tensor.py','native.py','run.py','metadata.py','test_v1.py','README.md')
KEY='pprime_physical_closure_day_v1';MODULE='workflows.data_v1_final.pprime.physical_closure_day_v1.run'
BASE=ROOT/'artifacts/labels/source_status_v1/physical_closure_day_v1';WALL=86400;DEFAULT_CAP=2<<30
MASTER=ROOT/'control/strict20_readback_all1200_actual_technical_closure_v1.json'
NREVIEW=ROOT/'control/root_actual_native_summary32_384_technical_review_v1.json'
OLD=ROOT/'artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/stage_receipt.json'
OLD_ACCOUNT=ROOT/'control/accounting/pprime_original72_4521124_actual_terminal_for_physical_closure_v1.json'
QA=re.compile(r'qa20-\d{2}-\d{2}')

def parameters(cap=DEFAULT_CAP):
    need(type(cap)is int and (512<<20)<=cap<=(8<<30),'EXPLICIT_BOUNDED_WHOLE_CAP')
    return {'scope_key':KEY,'original_QM_job':'4524436','molecules':20,'conditions':12,'arms':5,'original_calls':1200,
        'original_vector_comparisons':500,'empty_vector_pair_rows':900,'retained_SP_calls':100,'retained_gradient_calls':100,
        'retained_raw_calls':200,'tensor_pair_checks':100,
        'retained_native_keys':384,'retained_original_B_metadata_evidence':384,'old72_job':'4521124','old72_FAILED_preserved':True,'cpus':16,'wall_seconds':WALL,
        'output_cap_bytes':cap,'resource_evidence_cap_bytes':128<<20,'workers':16,'maximum_pending_groups':32,'producer_pure_methods':3,'resource_pure_methods':3,
        'all_pure_before_DATA_and_monitor':True,'native_initialize_or_invoke_calls':0,'new_QM_UFF_calls':0,'once_writes':0,
        'original_functions_tolerances_masks_and_return_states_preserved':True,'no_new_precision_permission':True,
        'scientific_PASS':False,'full_or2000_release':'HOLD','D1_jointly_frozen':False}

def is_detail_reference(ref):
    p=pathlib.PurePosixPath(ref['path']);found=[part for part in p.parts if QA.fullmatch(part)]
    leaf=re.fullmatch(r'(qa20-\d{2}-\d{2})\.DATA\.json',p.name)
    if leaf is not None and p.parent.name=='tasks':found.append(leaf[1])
    if not found:return False
    need(len(found)==1,'ONE_CALL_IN_LITERAL_PATH')
    return K.qa_cell(found[0])[1] in ('xtb_singlepoint','xtb_perturbed_gradient')

def select_detail_references(refs,index,prepare_root,ep):
    """Metadata-only closure, including exact original hash-named once claims."""
    need(type(index)is int and 0<=index<20,'SPECIFIC_ORIGINAL_GROUP')
    qas={'qa20-%02d-%02d'%(index,j) for j in range(60)
        if K.qa_cell('qa20-%02d-%02d'%(index,j))[1] in ('xtb_singlepoint','xtb_perturbed_gradient')}
    tasks={str(pathlib.Path(prepare_root)/'tasks'/(qa+'.DATA.json')) for qa in qas}
    claims={str(P.E.LEDGER/(P.E.once_key(ep,qa)+'.json')) for qa in qas}
    need(len(qas)==len(tasks)==len(claims)==10,'TEN_ORIGINAL_DETAIL_TASKS_AND_CLAIMS')
    selected=unique([r for r in refs if is_detail_reference(r) or r['path'] in claims])
    paths={r['path'] for r in selected}
    need(tasks<=paths and claims<=paths,'ORIGINAL_PRODUCER_TASK_AND_ONCE_CLAIM_TRIPLES_ALL_DECLARED')
    return selected,{'detail_calls':10,'exact_prepared_task_files':10,'exact_original_hash_named_once_claims':10,
        'task_claim_triples_in_original_group_inventory':True,'original_once_key_function_reused_readonly':True}

def metadata_refs(value):
    """Already pinned references only; no recursive body discovery or first SHA."""
    out=[]
    def visit(v):
        if isinstance(v,dict):
            if all(k in v for k in ('path','bytes','sha256')):out.append(P.triple(v,source=True));return
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value);return unique(out,source=True)

def old_account(ref):
    need(P.triple(ref)['path']==str(OLD_ACCOUNT),'SPECIFIC_ORIGINAL72_TERMINAL_ACCOUNT')
    a=meta(ref)
    # The original queue's terminal parser handles the complete raw sacct text.
    raw=a.get('raw_reference',a.get('raw_sacct_reference',a.get('raw_accounting_reference')))
    if raw is None:
        candidates=[r for r in metadata_refs(a) if r['path'].endswith('.sacct.txt')]
        need(len(candidates)==1,'ORIGINAL72_ONE_ACTUAL_RAW_ACCOUNT_REF');raw=candidates[0]
    raw=P.triple(raw);need(raw['bytes']<=2<<20,'SMALL_ACTUAL_ACCOUNT_TEXT_ONLY');text=pathlib.Path(raw['path']).read_text()
    need(Q.pin(raw['path'])==raw,'ORIGINAL72_CURRENT_RAW_ACCOUNT_SHA')
    rows=[line.split('|') for line in text.splitlines() if line.startswith('4521124|')]
    need(len(rows)==1 and rows[0]==['4521124','FAILED','3:0','135','16','compute-0-14','1278']
        and a['allocated_core_seconds']==2160,'TRUE_FAILED72_PARENT_NOT_BATCH_OR_EXTERN_C0')
    return a,raw

def derive(plan):
    need(P.triple(plan['aggregate_reference'])['path']==str(MASTER),'SPECIFIC_ALL1200_CLOSURE')
    master=meta(plan['aggregate_reference'])
    need(master['schema']=='STRICT20_READBACK_ALL1200_ACTUAL_TECHNICAL_CLOSURE_V1'
        and master['actual_readonly_calls']==1200 and master['original_vector_exact_comparisons']==500
        and len(master['actual_closure_references'])==21 and master['scientific_PASS'] is False
        and master['full_or2000_release']=='HOLD','ACTUAL_ALL20_NOT_PHYSICAL_RELEASE')
    rr=master['original_actual_root_review_reference'];r,ep,_,rp,prepare_root,_=P.parents({'actual_root_review_reference':rr,'mode':'inventory'})
    analysis=P.triple(r['analysis_DATA_locator_not_opened_or_hashed_on_login']);groups=[];seen=set();inventory=None
    parents=[plan['aggregate_reference'],*rp];data=[analysis,P.audit_ref()]
    for ref in master['actual_closure_references']:
        c=meta(ref);m,p,extra=P.actual(c['closure_references']);need(c['manifest_reference']==c['closure_references']['manifest'],'SAME_ACTUAL_READBACK_MANIFEST')
        parents.extend([ref,*c['closure_references'].values(),*extra])
        if m['mode']=='inventory':need(inventory is None,'ONE_ACTUAL_INVENTORY');inventory=(ref,m)
        else:
            i=m['group_index'];need(type(i)is int and i not in seen and 0<=i<20,'EXACT_DISTINCT20');seen.add(i)
            groups.append({'group_index':i,'evidence_reference':P.triple(m['evidence_DATA_reference']),
                'inventory_closure_reference':p['inventory_closure_reference']});data.append(m['evidence_DATA_reference'])
    need(inventory is not None and seen==set(range(20)),'ALL21_CLOSED_PARENTS')
    for row in groups:
        need(row['inventory_closure_reference']==inventory[0],'SAME_ORIGINAL_INVENTORY')
        locator_ref=inventory[1]['groups'][row['group_index']];g=meta(locator_ref)
        need(g['schema']=='STRICT20_READBACK_GROUP_LOCATORS_V1' and g['group_index']==row['group_index'] and g['calls']==60,'ACTUAL_GROUP_LOCATOR_ONLY')
        descriptor=P.triple(g['descriptor_reference']);selected,declaration=select_detail_references(g['data_references'],row['group_index'],prepare_root,ep)
        need(len({part for x in selected for part in pathlib.PurePosixPath(x['path']).parts if QA.fullmatch(part)})==10,'ONLY_FIVE_SP_AND_FIVE_GRADIENT_CALLS_PER_GROUP')
        row.update(locator_reference=locator_ref,descriptor_reference=descriptor,detail_input_declaration_closure=declaration)
        parents.append(locator_ref);data.extend([descriptor,*selected])
    need(P.triple(plan['native_summary_review_reference'])['path']==str(NREVIEW),'SPECIFIC_ACTUAL3953_REVIEW')
    nr=meta(plan['native_summary_review_reference']);need(nr['schema']=='ROOT_ACTUAL_NATIVE_SUMMARY32_TECHNICAL_REVIEW_V1'
        and str(nr['actual_job_id'])=='4523953','ACTUAL_NATIVE384_REVIEW')
    nm=meta(nr['manifest_reference']);np=meta(nm['plan_reference'])
    _,nraw=F.account(nr['actual_accounting_reference'],'4523953','compute-0-15')
    need(nraw==nr['raw_accounting_reference'] and nm['schema']=='NATIVE_FRAME_SUMMARY32_OBSERVATIONS_V1' and nm['job_id']=='4523953'
        and np['scope_parameters']==N.parameters('summary')
        and nm['completed_key_observations']==384 and nm['held_keys']==0 and nm['new_QM_UFF_calls']==0,'ACTUAL384_C0_NOT_UNITS_ACCEPTANCE')
    native=[{k:x[k] for k in ('position','calc_type','scientific_DATA_reference')} for x in nm['per_key_scientific_DATA_references']]
    need(len(native)==384 and [x['position'] for x in native]==list(range(384)),'FIXED384_ORDER')
    bm=meta(nm['body_closure_references']['manifest']);brows=bm['record_evidence_references']
    need(bm['job_id']=='4523708' and bm['completed_key_observations']==384 and bm['held_keys']==0 and len(brows)==384,'ACTUAL_B384_NATIVE_METADATA_PARENT')
    for row in native:
        b=brows[row['position']];need(b['position']==row['position'],'EXACT_B_POSITION_JOIN_NOT_GUESSED_SOURCE')
        row['B_evidence_reference']=P.triple(b['evidence_reference'])
        data.extend([P.triple(row['scientific_DATA_reference']),row['B_evidence_reference']])
    parents.extend([plan['native_summary_review_reference'],nr['manifest_reference'],nm['plan_reference'],nr['actual_accounting_reference'],nraw,
        *nm['body_closure_references'].values(),*nm['official_context_source_references']])
    need(P.triple(plan['old72_stage_receipt_reference'])['path']==str(OLD),'ORIGINAL72_RECEIPT_ONLY')
    old=meta(plan['old72_stage_receipt_reference']);need(old['schema']=='PPRIME_CPU_AUTO_MEMORY_ACTUAL_STAGE_V1'
        and str(old['job_id'])=='4521124' and old['production_membership'] is False
        and old['details']['actual_cases_closed']==72,'ORIGINAL_FAILED72_NOT_REPLACED')
    old_report=P.triple(old['details']['evaluation']);data.append(old_report)
    _,oraw=old_account(plan['old72_accounting_reference']);parents.extend([plan['old72_stage_receipt_reference'],plan['old72_accounting_reference'],oraw,old['plan'],old['startup_proof']])
    official=meta(plan['official_source_catalog_reference']);need(official['schema']=='PPRIME_PHYSICAL_CLOSURE_OFFICIAL_SOURCE_CATALOG_V1'
        and official['xtb_observed_prefix_resolved_commit']=='edcfbbe39d411edc225e27315fbda3a204ddb023'
        and official['mopac_release_commit']=='490725eac356e0e75037f37bdd2db343d6bc9e09','PINNED_OFFICIAL_SOURCE_IDENTITIES')
    parents.append(plan['official_source_catalog_reference'])
    for row in official['files']:
        ref=P.triple(row['reference']);need(ref['bytes']<=2<<20 and Q.pin(ref['path'])==ref,'OFFICIAL_FULL_SOURCE_BYTES_NOT_DATA');parents.append(ref)
    authority={'actual_root_review_reference':rr,'execution_plan_reference':r['plan_reference'],'prepare_root':str(prepare_root),
        'analysis_reference':analysis,'audit_configuration_reference':P.audit_ref(),'groups':sorted(groups,key=lambda x:x['group_index']),
        'native_manifest_reference':nr['manifest_reference'],'native_keys':native,'old72_evaluation_reference':old_report,
        'official_source_catalog_reference':plan['official_source_catalog_reference']}
    return authority,unique(data),unique(parents,source=True),ep,official

def sources():
    paths=[*(HERE/n for n in FILES),*P.sources(),*N.source_paths(),*Day.sources()]
    return list(dict.fromkeys(paths))
