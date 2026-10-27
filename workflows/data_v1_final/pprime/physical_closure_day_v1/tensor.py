"""Retained NEW20 SP tensors with original reader, rotation and tolerances."""
import collections,concurrent.futures as cf
from workflows.data_v1_final.pprime.strict20_readback_v1 import replay as B,checks as K
from workflows.data_v1_final.pprime.strict_numerics20_qa_v1 import analysis as A
from . import contract as C,io as I

def state(value):
    if value.get('pass') is True:return 'PASS'
    if value.get('within_numeric_allowance') is False:return 'FAIL_NUMERIC_ALLOWANCE'
    if value.get('within_numeric_allowance') is True and value.get('sufficient_signal') is False:return 'UNDEFINED_INSUFFICIENT_SIGNAL'
    return 'UNKNOWN_UNAVAILABLE_OR_INVALID'

def run(plan,authority,ep,analysis,config,objects,store,out,check):
    import numpy as np
    from math_v1 import tensor_covariance,tensor_checks,output_frame
    old_own,_=K.index_analysis(analysis);old,new,_=C.P.E.P.S.protocol(ep);wire=objects[1]
    roots=[C.P.ACTUAL,C.P.BASE,C.ROOT/'artifacts',C.REPO/'configs/data_v1/pprime',C.P.E.LEDGER,authority['prepare_root']]
    def one_group(g):
        check();descriptor=I.value(g['descriptor_reference'],roots,plan['data_references'],8<<20)
        C.need(descriptor['schema']=='STRICT20_READBACK_GROUP_DESCRIPTOR_V1' and descriptor['group_index']==g['group_index']
            and len(descriptor['rows'])==60,'SAME_ORIGINAL_GROUP_DESCRIPTOR')
        entries=[e for e in descriptor['rows'] if K.qa_cell(e['qa_id'])[1] in ('xtb_singlepoint','xtb_perturbed_gradient')]
        C.need(len(entries)==10 and all({K.qa_cell(e['qa_id'])[2] for e in entries if K.qa_cell(e['qa_id'])[1]==name}==set(C.P.E.P.ARMS)
            for name in ('xtb_singlepoint','xtb_perturbed_gradient')),'FIVE_SP_AND_GRADIENT_ARMS_NOT_COMPLETION_ORDER')
        records={};evidence=[];gradient=[]
        for entry in sorted(entries,key=lambda x:x['qa_id']):
            check();r,proof=B.one(entry,{'actual_root_review_reference':authority['actual_root_review_reference']},ep,
                roots,plan['data_references'],old,new,objects,check)
            own,m=A.own(r,config);K.exact(own,old_own[r['qa_id']],wire)
            C.need(own['defined_QC_pass'] is True,'ORIGINAL_SP_OWN_GATE_STILL_PASS')
            compact={k:r[k] for k in ('qa_id','molecule_id','rotation_matrix','condition','arm')}
            compact['case']={k:r['case'][k] for k in ('symbols','actual_rendered_coordinates_A')}
            if r['condition']=='xtb_singlepoint':records[r['arm']]=(compact,m)
            else:
                task=I.value(entry['task_reference'],roots,plan['data_references'],8<<20)
                gradient.append({'qa_id':r['qa_id'],'arm':r['arm'],'readback':proof,'own':own,'seed':task['seed'],
                    'parent_original_record_id':task['case']['row']['record_id'],'task_reference':entry['task_reference'],
                    'actual_postcall_input_references':r['actual_postcall_input_references'],
                    'actual_child_coordinates_A':r['case']['actual_rendered_coordinates_A'],
                    'symbols':r['case']['symbols'],'original_force_relation':m.get('force_relation'),
                    'own_output_coordinates':m['coordinates'],'mechanical_diagnostics_not_finite_difference':m.get('mechanical_diagnostics'),
                    'original_renderer_and_intent_seed_exact':True,'finite_difference_validation':'NOT_MEASURED',
                    'final_export_geometry_id_or_child_H0_created':False})
            evidence.append({'qa_id':r['qa_id'],'readback':proof,'own':own,
                'quadrupole':m.get('quadrupole'),'original_tensor_trace_check':m.get('quadrupole_checks'),
                'SP_own_output_coordinates':m['coordinates'],'input_reference':entry['task_reference']})
        comparisons=[]
        for left,right in A.PAIRS:
            x,mx=records[left];y,my=records[right]
            r=np.eye(3).tolist() if (left,right) in (('B1','B2'),('P1','P2')) else y['rotation_matrix']
            C.need(x['case']['symbols']==y['case']['symbols'],'SAME_UNSHUFFLED_ATOM_ORDER')
            expected=np.asarray(x['case']['actual_rendered_coordinates_A'],dtype=np.float64)@np.asarray(r,dtype=np.float64).T
            orbit=output_frame(expected,y['case']['actual_rendered_coordinates_A'],config['rendered_coordinate_atol_A'])
            q0,q1=mx.get('quadrupole'),my.get('quadrupole')
            value=tensor_covariance(q0['six_components_au'],q1['six_components_au'],q0['rounding_halfwidth_au'],q1['rounding_halfwidth_au'],
                config['tensor_tolerance'],rotation=r) if q0 is not None and q1 is not None else {'pass':False,'reason':'ORIGINAL_RAW_SIX_COMPONENT_BLOCK_MISSING'}
            comparisons.append({'molecule_id':x['molecule_id'],'condition':'xtb_singlepoint','arms':[left,right],
                'qa_ids':[x['qa_id'],y['qa_id']],'state':state(value),'original_tensor_check':value,
                'actual_input_rotation_check':orbit,'input_orbit_is_not_SP_own_output_frame':True,
                'coordinate_control_state':'PASS' if orbit['supports_input_axes'] else 'FAIL_ORIGINAL_RENDERED_COORDINATE_GATE',
                'scientific_acceptance_or_new_tolerance':False})
        ref=store.json(out/('tensor_g%02d.DATA.json'%g['group_index']),{'schema':'PPRIME_PHYSICAL_DAY_RETAINED_TENSOR_GROUP_V1',
            'group_index':g['group_index'],'calls':evidence,'comparisons':comparisons,'perturbed_gradient':gradient,
            'original_tensor_tolerance':config['tensor_tolerance']})
        return {'group_index':g['group_index'],'DATA_reference':ref,'SP_calls':5,'gradient_calls':len(gradient),'comparisons':5,
            'gradient_force_relation_counts':dict(collections.Counter('PASS' if v['original_force_relation'] and v['original_force_relation']['pass'] is True else 'FAIL_OR_UNAVAILABLE' for v in gradient)),
            'counts':dict(collections.Counter(v['state'] for v in comparisons)),
            'input_orbit_failures':sum(v['coordinate_control_state']!='PASS' for v in comparisons)}
    reports=[]
    # Exactly20 bounded groups, at most16 active/20 pending; no population-sized object.
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        futures={pool.submit(one_group,g):g['group_index'] for g in authority['groups']}
        for future in cf.as_completed(futures):reports.append(future.result())
    C.need(len(reports)==20 and sum(v['SP_calls'] for v in reports)==sum(v['gradient_calls'] for v in reports)==sum(v['comparisons'] for v in reports)==100,'EXACT_RETAINED_SP_GRADIENT_AND_TENSOR_MASS')
    counts=collections.Counter()
    for v in reports:counts.update(v['counts'])
    forces=collections.Counter()
    for v in reports:forces.update(v['gradient_force_relation_counts'])
    return {'SP_calls_reread':100,'gradient_calls_reread':100,'tensor_comparisons':100,'counts':dict(counts),
        'gradient_force_relation_counts':dict(forces),
        'input_orbit_failures':sum(v['input_orbit_failures'] for v in reports),'groups':sorted(reports,key=lambda x:x['group_index']),
        'SP_own_output_frame_missing_not_backfilled':True,'original_tensor_function_and_tolerance_objects':True}

def old_controls(report):
    C.need(isinstance(report,dict) and isinstance(report.get('contradictions'),list),'ORIGINAL72_EVALUATION_SCHEMA')
    origins=report.get('quadrupole_origin_controls',[]);companions=report.get('same_geometry_SP_gradient_controls',[])
    tensors=[v['quadrupole_covariance'] for v in report.get('rotation_comparisons',[]) if v.get('quadrupole_covariance') is not None]
    def counts(rows):
        return dict(collections.Counter('PASS' if x.get('pass') is True else 'FAIL' if x.get('pass') is False else 'UNKNOWN_NOT_A_PASS_FIELD' for x in rows))
    companion_states=[]
    for row in companions:
        values=[row.get('exact_same_input_geometry'),row.get('gradient_output_coordinates',{}).get('supports_input_axes'),
            row.get('SP_gradient_raw_dipole_agreement',{}).get('pass')]
        companion_states.append('PASS' if all(x is True for x in values) else 'FAIL' if any(x is False for x in values) else 'UNKNOWN')
    return {'original_status':report.get('status'),'old_contradictions':report['contradictions'],'old_incomplete':report.get('incomplete'),
        'origin_controls':origins,'origin_counts':counts(origins),'tensor_checks':tensors,'tensor_counts':counts(tensors),
        'same_geometry_companions':companions,'companion_original_gate_counts':dict(collections.Counter(companion_states)),
        'no_translation_in_NEW20':True,'finite_difference_energy_gradient_control':'NOT_MEASURED',
        'missing_origin_controls':'UNKNOWN_NO_RETAINED_CONTROL' if not origins else None,
        'old_failed_job_preserved':'4521124 FAILED 3:0;2160 allocated core seconds;not a new C0'}
