"""Check guide AND-criterion semantics and frozen auxiliary-family exclusion."""
import os
from report_s_experiment_current_v6 import joint_judgment
from prepare import ROOT,save,sha

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    cases=[('all required criteria pass',[True]*3,[True]*32,'ONE_EPOCH_SUFFICIENT_UNDER_PREDECLARED_RULE'),
        ('known S failure with unavailable probe',[False,True,True],[None]+[True]*31,'ONE_EPOCH_INSUFFICIENT_UNDER_PREDECLARED_RULE'),
        ('known probe failure with another unavailable probe',[True]*3,[False,None]+[True]*30,'ONE_EPOCH_INSUFFICIENT_UNDER_PREDECLARED_RULE'),
        ('unknown probe with all other required criteria passing',[True]*3,[None]+[True]*31,'NOT_ESTABLISHED_DUE_TO_UNAVAILABLE_PROBE_CELLS')]
    for name,loss,probe,expected in cases:
        actual=joint_judgment([{'both_below_2_percent':v} for v in loss],
            [{'included_in_primary_judgment':True,'criterion_met':v} for v in probe]+[{'included_in_primary_judgment':False,'criterion_met':False}]*3)
        assert actual==expected,(name,actual,expected)
    save(ROOT/'reports/s_report_judgment_rule_validation_v1.json',{'status':'GUIDE_CONJUNCTIVE_JUDGMENT_AND_AUXILIARY_EXCLUSION_PASS',
        'job_id':os.environ['SLURM_JOB_ID'],'cases':len(cases),'formal_scores_used':False,'report_source_sha256':sha(ROOT/'scripts/report_s_experiment_current_v6.py')})
    print('GUIDE_CONJUNCTIVE_JUDGMENT_AND_AUXILIARY_EXCLUSION_PASS',flush=True)

if __name__=='__main__':main()
