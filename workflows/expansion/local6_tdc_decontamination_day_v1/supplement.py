"""One original whole-SOURCE check and bounded existing-C0 physical facts."""
import collections
from pathlib import Path
from workflows.data_v1_final.labels.normalization_compact_day_v1.run import repository_check
from workflows.data_v1_final.pprime.common import read_staging
from . import contract as C,io as I

def check_repository(plan,out,budget):
    out.mkdir(parents=True,mode=0o700);budget.check()
    try:return repository_check(plan,out)
    finally:
        files=[p for p in out.iterdir() if p.is_file()];n=sum(p.stat().st_size for p in files)
        C.need(n<=64<<20,'FINITE_ORIGINAL_SOURCE_CHECK_OUTPUT');budget.charge(n)

def physical(plan,authority,out,budget):
    manifest_ref=authority['physical_manifest_reference'];root=Path(manifest_ref['path']).parent
    def load(ref,declared,cap):
        r=C.triple(ref);C.need(r['bytes']<=cap,'BOUNDED_CLOSED_PHYSICAL_DATA')
        with I.held(r,[root],declared) as (f,_):return read_staging(f.read(cap+1))
    m=load(manifest_ref,plan['data_references'],4<<20)
    C.need(m['schema']=='PPRIME_PHYSICAL_CLOSURE_DAY_MANIFEST_V1' and m['job_id']=='4524581' and m['uid']==1278
        and m['node']=='compute-0-18' and m['status']=='COMPLETE_RETAINED_PHYSICAL_EVIDENCE_REQUIRES_ROOT_D1_REVIEW'
        and not m['errors'] and m['native_initialize_or_invoke_calls']==m['new_QM_UFF_calls']==m['once_writes']==0
        and m['scientific_PASS'] is False and m['full_or2000_release']=='HOLD','ACTUAL_RETAINED_R2_C0_NOT_PRODUCTION_PERMISSION')
    s=m['sections'];native=s['native384']['per_key_DATA_references'];groups=s['retained_tensors_and_gradient']['groups']
    C.need(len(native)==384 and [v['position'] for v in native]==list(range(384)) and len(groups)==20
        and [v['group_index'] for v in groups]==list(range(20)),'EXACT_C0_NATIVE_AND_TENSOR_POPULATION')
    selected=[]
    for row in native:
        r=C.triple(row['DATA_reference']);C.need(r['path']==str(root/('native_%04d.DATA.json'%row['position'])),'ONLY_FIXED_C0_NATIVE_PRODUCER_PATH');selected.append(r)
    for row in groups:
        r=C.triple(row['DATA_reference']);C.need(r['path']==str(root/('tensor_g%02d.DATA.json'%row['group_index'])),'ONLY_FIXED_C0_TENSOR_PRODUCER_PATH');selected.append(r)
    extras={'old72':s['old72']['DATA_reference'],'defined':s['defined']['summary_DATA_reference'],'official':s['official_source']['reference']}
    expected={'old72':'old72_controls.DATA.json','defined':'defined_QC_summary.DATA.json','official':'official_source_facts.json'}
    for name,r in extras.items():C.need(C.triple(r)['path']==str(root/expected[name]),'EXACT_C0_PHYSICAL_SUPPLEMENT_PATH');selected.append(C.triple(r))
    declared=C.unique(selected);C.need(len(declared)==407,'EXACT_C0_EMBEDDED_AUTHORITY_NO_OPEN_ENDED_ROOT_READ')
    headers={};versions={};keywords={};coords={};trace=collections.Counter();n=0
    for row in native:
        budget.check();v=load(row['DATA_reference'],declared,32<<20);condition=row['condition']
        C.need(v['schema']=='PPRIME_PHYSICAL_RETAINED_NATIVE_KEY_V1' and v['position']==row['position'] and v['key']['calc_type']==condition,'EXACT_R2_NATIVE_RECORD')
        headers.setdefault(condition,collections.Counter()).update(v['native_explicit_unit_header_labels_observed'])
        versions.setdefault(condition,collections.Counter())[I.canonical(v['actual_original_software']).decode()]+=1
        keywords.setdefault(condition,collections.Counter())[I.canonical(v['actual_original_keywords']).decode()]+=1
        coords.setdefault(condition,collections.Counter())[v['own_coordinate_gate']['state']]+=1
        q=v.get('r674_original_trace_gate');trace['PASS' if q and q.get('trace_within_rounding') is True else 'FAIL' if q and q.get('trace_within_rounding') is False else 'NA_OR_UNKNOWN']+=1;n+=1
    tensors=collections.Counter();forces=collections.Counter();calls=0
    for row in groups:
        budget.check();v=load(row['DATA_reference'],declared,32<<20)
        C.need(v['schema']=='PPRIME_PHYSICAL_DAY_RETAINED_TENSOR_GROUP_V1' and v['group_index']==row['group_index'] and len(v['comparisons'])==5
            and len(v['perturbed_gradient'])==5,'EXACT_RETAINED_COMPARISON_AND_CHILD_COUNTS')
        tensors.update(x['state'] for x in v['comparisons'])
        forces.update('PASS' if x['original_force_relation'] and x['original_force_relation']['pass'] is True else 'FAIL_OR_UNKNOWN' for x in v['perturbed_gradient']);calls+=5
    old=load(extras['old72'],declared,8<<20);defined=load(extras['defined'],declared,8<<20);official=load(extras['official'],declared,8<<20)
    C.need(defined['own_rows']==defined['pair_rows']==1200 and defined['vector_checks']==500 and defined['empty_vector_pair_rows']==900
        and len(defined['own_matrix'])==60 and sum(tensors.values())==sum(forces.values())==100 and len(official['source_facts'])==15,
        'C0_DEFINITION_VECTOR_TENSOR_GRADIENT_AND_SOURCE_CONTEXT_MASS')
    result={'schema':'LOCAL7_PARENT_RETAINED_PHYSICAL_D1_FACTS_V1','actual_C0_manifest_reference':manifest_ref,
        'actual_accounting_reference':plan['physical_accounting_reference'],'native_records':n,'tensor_comparison_counts':dict(tensors),
        'gradient_calls':calls,'gradient_force_relation_counts':dict(forces),'native_explicit_unit_headers_by_condition':headers,
        'actual_software_variants_by_condition':versions,'actual_keyword_variants_by_condition':keywords,'native_own_coordinate_states_by_condition':coords,
        'original_trace_gate_counts':dict(trace),'old72_origin_counts':old['origin_counts'],'old72_tensor_counts':old['tensor_counts'],
        'old72_companion_counts':old['companion_original_gate_counts'],'SCF_original_tri_state_by_task_and_arm':[
            {'condition':r['condition'],'arm':r['arm'],'SCF':r['SCF']} for r in defined['own_matrix']],
        'original500_vector_matrix':defined['vector_matrix'],'official_source15_context':official,
        'all407_embedded_refs_whole_SHA_sameFD_verified':True,'SP_own_coords_UNKNOWN_not_backfilled':True,
        'new_engine_RDKIT_QM_UFF_or_numeric_recomputation':0,'mask_or_tolerance_or_precision_permission_changed':False,
        'Root_physical_PASS_2000_full_or_D1_signed':False}
    return I.write(out/'physical_D1_review_facts.json',result,budget)
