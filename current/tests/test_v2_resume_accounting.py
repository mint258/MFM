"""A resumed execution reports new work while its dev checkpoint keeps the full clock."""
import importlib.util
import json
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('resume_run_collector',
    Path(__file__).resolve().parents[2]/'tools/model_v3/v2_collect_runs.py')
collector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def write(root,name,value):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))


def collect(root):
    return collector.collect_run(root,name='P_resume',job='123',gpu='RTX5090',state='COMPLETED')


def test_resume_counts_only_new_work_and_keeps_the_full_checkpoint_dev_score(tmp_path):
    write(tmp_path,'execution.json',dict(initial_samples=96000,initial_updates=3000,elapsed_seconds_prior=4000.))
    write(tmp_path,'summary.json',dict(samples=6000000,updates=187500,seconds=84000.,
        actual_samples=5904000,actual_updates=184500,actual_seconds=80000.,status='TRAINING_COMPLETE_DEV_EVALUATION_PENDING'))
    write(tmp_path,'dev_eval/summary.json',dict(complete=True,consumed_samples=6000000,mean_normalized_improvement=.3))
    row=collect(tmp_path)
    assert row['samples']==5904000 and row['updates']==184500 and row['elapsed_seconds']==80000.
    assert row['dev_score']==.3 and row['throughput_molecules_s']==pytest.approx(5904000/80000.,abs=1e-10,rel=1e-10)


def test_running_resume_uses_the_observed_log_delta_instead_of_recounting_the_prefix(tmp_path):
    write(tmp_path,'execution.json',dict(initial_samples=96000,initial_updates=3000,elapsed_seconds_prior=4000.))
    (tmp_path/'losses.csv').write_text('samples,updates,seconds\n96032,3001,4002.5\n')
    row=collect(tmp_path)
    assert row['samples']==32 and row['updates']==1 and row['elapsed_seconds']==2.5


def test_resume_before_first_visible_update_reports_no_additional_work(tmp_path):
    write(tmp_path,'execution.json',dict(initial_samples=96000,initial_updates=3000,elapsed_seconds_prior=4000.))
    row=collect(tmp_path)
    assert row['samples']==0 and row['updates']==0 and row['elapsed_seconds']==''


def test_legacy_summary_with_explicit_actual_counts_remains_compatible(tmp_path):
    write(tmp_path,'summary.json',dict(actual_samples=160000,actual_updates=20000,seconds=1000.))
    row=collect(tmp_path)
    assert row['samples']==160000 and row['updates']==20000 and row['elapsed_seconds']==1000.


def test_stale_dev_checkpoint_is_not_attached_to_later_training_progress(tmp_path):
    write(tmp_path,'summary.json',dict(samples=6000000,updates=187500,seconds=1000.))
    write(tmp_path,'dev_eval/summary.json',dict(complete=True,consumed_samples=4000000,mean_normalized_improvement=.3))
    assert collect(tmp_path)['dev_score']==''


def test_log_from_before_the_declared_resume_is_not_silently_clipped_to_zero(tmp_path):
    write(tmp_path,'execution.json',dict(initial_samples=96000,initial_updates=3000,elapsed_seconds_prior=4000.))
    (tmp_path/'losses.csv').write_text('samples,updates,seconds\n64000,2000,3000.\n')
    with pytest.raises(ValueError,match='predates'):collect(tmp_path)


def test_native_s_stage_comes_from_actual_queue_without_changing_training_counts(tmp_path):
    write(tmp_path,'configuration.json',dict(views='three',seed=0,lr=1e-3,batch_size=32))
    write(tmp_path,'summary.json',dict(samples=6000000,updates=187500,seconds=1000.))
    original=collect(tmp_path)
    actual=collector.collect_run(tmp_path,name='P_resume',job='123',gpu='RTX5090',
                                 state='COMPLETED',stage=6)
    assert original['stage']==5
    assert actual=={**original,'stage':6}


def test_explicit_stage_cannot_relabel_a_configured_stage5_run_as_new_stage6(tmp_path):
    write(tmp_path,'configuration.json',dict(stage=5,condition='P'))
    with pytest.raises(ValueError,match='conflicts with the original'):
        collector.collect_run(tmp_path,name='P_reused',job='123',gpu='RTX5090',
                              state='COMPLETED',stage=6)
    assert collector.collect_run(tmp_path,name='P_reused',job='123',gpu='RTX5090',
                                 state='COMPLETED',stage=5)['stage']==5
