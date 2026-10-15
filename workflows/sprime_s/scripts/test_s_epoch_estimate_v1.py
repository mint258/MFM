"""Check S-curve inference boundaries; synthetic losses are never formal results."""
import ast,json,os
from prepare import ROOT,save,sha
from s_epoch_estimate_v1 import TASKS,estimate_epochs
assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
cases=[]
def values(a,b,c):return {e:{task:v for task in TASKS} for e,v in enumerate((a,b,c),1)}
r=estimate_epochs({});assert r['estimated_epochs'] is None and r['lower_bound_epochs'] is None;cases.append('missing_full_endpoints_are_not_estimated')
r=estimate_epochs(values(.11,.101,.1001));assert r['estimated_epochs']==2 and r['status'].startswith('OBSERVED_');cases.append('observed_next_epoch_gain_is_distinct_from_joint_convergence')
r=estimate_epochs(values(.2,.15,.125));assert r['estimated_epochs']==6 and not r['extrapolation_verified'];cases.append('conditional_positive_floor_exponential_forecast_is_six_not_verified')
r=estimate_epochs(values(.4,.2,.1));assert r['estimated_epochs'] is None and r['lower_bound_epochs']==3;cases.append('zero_asymptote_cannot_support_finite_relative_gain_threshold')
r=estimate_epochs(values(.4,.2,.05));assert r['estimated_epochs'] is None;cases.append('negative_fitted_floor_is_not_reported_as_real')
r=estimate_epochs(values(.2,.21,.15));assert r['estimated_epochs'] is None;cases.append('nonmonotonic_curve_has_no_unfounded_epoch_number')
x=values(.2,.15,.125);x[2]['distance']=.21;x[3]['distance']=.15;r=estimate_epochs(x);assert r['estimated_epochs'] is None;cases.append('one_unidentified_head_prevents_joint_S_forecast')
old=ast.parse((ROOT/'scripts/report_s_experiment_current_v8.py').read_text());new=ast.parse((ROOT/'scripts/report_s_experiment_current_v9.py').read_text())
for name in ['joint_judgment','wait_for_actual_publication']:
    assert ast.dump(next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name))==ast.dump(next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name))
save(ROOT/'reports/s_epoch_estimate_validation_v1.json',{'status':'S_CURVE_ESTIMATE_BOUNDARIES_AND_UNCHANGED_SCIENTIFIC_JUDGMENT_PASS','job_id':os.environ['SLURM_JOB_ID'],'synthetic_non_scientific_validation':True,'cases':cases,'source_sha256':sha(ROOT/'scripts/s_epoch_estimate_v1.py'),'report_source_sha256':sha(ROOT/'scripts/report_s_experiment_current_v9.py')})
print('S_CURVE_ESTIMATE_BOUNDARIES_PASS',len(cases))
