"""Verify the actual failed journal tail is preserved but not double-counted."""
import json,os
from prepare import ROOT,save,sha

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    summary=json.loads((ROOT/'reports/current_experiment/summary.json').read_text())
    assert summary['report_source_sha256']==sha(ROOT/'scripts/report_s_experiment_current_v8.py')
    tails=summary['abandoned_failed_tail_metrics_excluded_from_committed_training_curves']
    actual=next(row for row in tails if row['segment']=='segment_4515155')
    assert actual['cutoff']==4194304 and actual['last_abandoned_logged_records']==5057536
    assert actual['excluded_logged_rows']>0 and summary['failed_attempt_compute_cost_retained']
    rows=[json.loads(line) for line in open(actual['original_journal_path'])]
    assert max(row['consumed_records'] for row in rows)==5057536
    assert sha(actual['original_journal_path'])==actual['original_journal_sha256']
    save(ROOT/'reports/s_failed_tail_report_validation_v2.json',{'status':'ACTUAL_FAILED_TAIL_RETAINED_AND_COMMITTED_CURVE_EXCLUSION_PASS',
        'job_id':os.environ['SLURM_JOB_ID'],'failed_job':'4515155','safe_records':4194304,
        'abandoned_last_logged_records':5057536,'abandoned_rows':actual['excluded_logged_rows'],'report_source_sha256':sha(ROOT/'scripts/report_s_experiment_current_v8.py')})
    print('ACTUAL_FAILED_TAIL_RETAINED_AND_COMMITTED_CURVE_EXCLUSION_PASS',flush=True)

if __name__=='__main__':main()
