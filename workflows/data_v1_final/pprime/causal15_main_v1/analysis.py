"""Existing vector tests on a fixed causal matrix; no automatic release or cause."""
from __future__ import annotations
from . import contract as C


def analyze(records,config,original_evidence):
    import numpy as np
    from evaluate_v1 import measurement
    from math_v1 import covariance
    by={(r['condition'],r['arm']):r for r in records};C.need(len(by)==len(records),'DUPLICATE_QA_MATRIX_CELL')
    comparisons=[]
    for condition in C.CASES:
        arms={arm:by.get((condition,arm)) for arm in C.ARMS}
        for left,right in (('B1','B2'),('B1','R1'),('B1','P1'),('P1','P2'),('B1','P2')):
            a,b=arms[left],arms[right];item={'condition':condition,'arms':[left,right],'checks':{},'status':'UNAVAILABLE_NO_CAUSE'}
            if a and b and a.get('independent_raw_readback') and b.get('independent_raw_readback'):
                ma,mb=measurement(a,config),measurement(b,config)
                rotation=np.eye(3).tolist() if (left,right) in {('B1','B2'),('P1','P2')} else b['rotation_matrix']
                for field in sorted(set(ma['vectors'])&set(mb['vectors'])):
                    x,y=ma['vectors'][field],mb['vectors'][field]
                    item['checks'][field]=covariance(x['values'],y['values'],x['rounding_halfwidth'],y['rounding_halfwidth'],config['vector_tolerances'][field],rotation)
                item['status']='ACTUAL_ORIGINAL_TOLERANCE_CHECKS_RECORDED' if item['checks'] else 'NATIVE_VECTORS_UNAVAILABLE'
            comparisons.append(item)
    historical=[]
    for record in records:
        old=original_evidence[record['qa_id']]
        origin={'case':record['origin_case'],'independent_raw_readback':old['old_vectors'],'parsed_wp5_result':old['old_result']}
        before,after=measurement(origin,config),measurement(record,config);checks={}
        rotation=record['rotation_matrix'] if record['arm'].startswith('P') else np.eye(3).tolist()
        for field in sorted(set(before['vectors'])&set(after['vectors'])):
            a,b=before['vectors'][field],after['vectors'][field]
            checks[field]=covariance(a['values'],b['values'],a['rounding_halfwidth'],b['rounding_halfwidth'],config['vector_tolerances'][field],rotation)
        historical.append({'qa_id':record['qa_id'],'source_case_id':record['origin_case_id'],'checks_against_original_native_values':checks,
            'source_result_reference':old['source_result_reference'],'native_SCF_cause_claimed':False})
    return {'schema':'PPRIME_CAUSAL15_ANALYSIS_V1','comparisons':comparisons,'historical_source_comparisons':historical,'actual_records':len(records),
        'cause':'UNKNOWN_REQUIRES_ROOT_REVIEW_OF_FIXED_CAUSAL_CONTROLS','original15FAIL_preserved':True,
        'new_numeric_tolerance':False,'scientific_PASS':False,'full_or2000_release':'HOLD'}
