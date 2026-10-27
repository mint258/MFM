"""Aggregate existing booleans/metrics only;no new covariance or physics gate."""
import math
from collections import Counter
from workflows.data_v1_final.pprime.strict_numerics20_qa_v1 import analysis as A
from workflows.data_v1_final.pprime.strict20_readback_v1 import checks as K
from . import contract as C

def vector_state(value):
    if value.get('pass') is True:return 'PASS'
    if value.get('within_numeric_allowance') is False:return 'FAIL_NUMERIC_ALLOWANCE'
    if value.get('within_numeric_allowance') is True and value.get('sufficient_signal') is False:return 'UNDEFINED_INSUFFICIENT_SIGNAL_ORIGINAL_PASS_FALSE'
    return 'UNDEFINED_UNAVAILABLE_OR_INVALID_ORIGINAL_PASS_FALSE'
def scf_state(value):
    if value is True:return 'TRUE'
    if value is False:return 'FALSE'
    C.need(value is None,'SCF_TRI_STATE_NOT_TRUTHINESS');return 'NULL_UNKNOWN'
def collect(analysis,groups,config,exact):
    old_own,old_pairs=K.index_analysis(analysis)
    exact(analysis['original_predeclared_tolerances'],{k:config[k] for k in ('coordinate_atol_A','vector_tolerances','rendered_coordinate_atol_A','same_geometry_dipole_atol_au')})
    seen=set();mids=set();own_seen=set();pair_seen=set();own_counts={};pair_counts={};vector_counts={};worst=[];unknown=Counter();scf=Counter();detail=[]
    for group in groups:
        i=group['group_index'];C.need(i not in seen and type(i)is int and 0<=i<20,'ONE_EVIDENCE_PER_ORIGINAL_GROUP');seen.add(i)
        C.need(group['schema']=='STRICT20_READBACK_EXACT_GROUP_EVIDENCE_V1' and len(group['original_own_call_checks'])==len(group['original_pair_checks'])==60,'EXACT60_AND60_PER_GROUP')
        group_mids={r['molecule_id'] for r in group['original_own_call_checks']};C.need(len(group_mids)==1 and not group_mids&mids,'ONE_UNIQUE_MID_PER_ORIGINAL_GROUP');mids.update(group_mids)
        for row in group['original_own_call_checks']:
            qa=row['qa_id'];idx,condition,arm=K.qa_cell(qa);C.need(idx==i and row['condition']==condition and row['arm']==arm and qa not in own_seen,'EXACT_UNIQUE_OWN_MATRIX');own_seen.add(qa)
            exact(row,old_own[qa]);C.need(type(row['defined_QC_pass'])is bool and all(type(v)is bool for v in row['checks'].values()),'ORIGINAL_BOOLEAN_FLAGS_NOT_COERCED')
            key=(condition,arm);cell=own_counts.setdefault(key,{'PASS':0,'FAIL':0,'SCF':Counter(),'check_flags':{}});cell['PASS' if row['defined_QC_pass'] else 'FAIL']+=1
            state=scf_state(row['SCF_converged_original_metadata']);cell['SCF'][state]+=1;scf[state]+=1
            for name,value in row['checks'].items():cell['check_flags'].setdefault(name,Counter())[str(value)]+=1
            unknown.update(row['interpretation_UNKNOWN'])
        for row in group['original_pair_checks']:
            key=K.expected_key(row);C.need(row['molecule_id'] in group_mids and type(row['defined_QC_pass'])is bool and key not in pair_seen and tuple(row['arms']) in A.PAIRS,'EXACT_UNIQUE_DECLARED_PAIR');pair_seen.add(key);exact(row,old_pairs[key])
            fields=A.FIELDS.get(row['condition'],set());checks=row['defined_vector_checks'];C.need(set(checks)==fields,'EXACT_DEFINED_FIELD_SET_NOT_EMPTY_PASS_PROMOTION')
            cell=pair_counts.setdefault((row['condition'],tuple(row['arms'])),Counter());cell['original_defined_QC_PASS' if row['defined_QC_pass'] else 'original_defined_QC_FAIL']+=1
            if not fields:cell['vector_NOT_DEFINED_FOR_TASK']+=1
            for field,value in checks.items():
                state=vector_state(value);vector_counts.setdefault((row['condition'],tuple(row['arms']),field),Counter())[state]+=1
                metric=value.get('max_abs_residual');C.need(metric is None or type(metric)in (float,int) and math.isfinite(metric),'FINITE_EXISTING_REPORTED_RESIDUAL')
                if metric is not None:worst.append({'molecule_id':row['molecule_id'],'condition':row['condition'],'arms':row['arms'],'field':field,**value})
            detail.append(row)
    C.need(seen==set(range(20)) and own_seen==set(old_own) and pair_seen==set(old_pairs) and len(own_seen)==len(pair_seen)==1200,'ALL20_1200_MASS_NO_DUPLICATE_OR_MISSING')
    C.need(sum(sum(v.values()) for v in vector_counts.values())==500,'EXACT500_ORIGINAL_VECTOR_CHECKS')
    own_rows=[{'condition':k[0],'arm':k[1],**v} for k,v in sorted(own_counts.items())]
    pair_rows=[{'condition':k[0],'arms':list(k[1]),**dict(v)} for k,v in sorted(pair_counts.items())]
    vectors=[{'condition':k[0],'arms':list(k[1]),'field':k[2],**dict(v)} for k,v in sorted(vector_counts.items())]
    worst.sort(key=lambda r:(r['condition'],tuple(r['arms']),r['field'],-r['max_abs_residual'],r['molecule_id']))
    per_channel={}
    for row in worst:per_channel.setdefault((row['condition'],tuple(row['arms']),row['field']),row)
    return {'own_matrix':own_rows,'pair_matrix':pair_rows,'vector_matrix':vectors,'SCF_original_converged_counts':dict(scf),'interpretation_UNKNOWN_counts':dict(unknown),
      'worst_existing_max_abs_residual_per_condition_pair_field':list(per_channel.values()),'worst_metric_note':'rank absolute residual only inside the same condition/pair/field channel;max_allowance is an independent maximum,not a componentwise ratio or new pass rule',
      'own_rows':1200,'pair_rows':1200,'vector_checks':500,'empty_vector_pair_rows':sum(r.get('vector_NOT_DEFINED_FOR_TASK',0) for r in pair_rows),
      'scientific_PASS':False,'full_or2000_release':'HOLD','new_QM_UFF_calls':0},detail