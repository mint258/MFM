"""Regression for an actual disk STOP hidden by delayed sacct RUNNING state."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('v2_runtime_state',
    Path(__file__).absolute().parents[2] / 'tools/model_v3/v2_runtime_state.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_controller_stop_overrides_observed_stale_accounting_running():
    record = 'JobId=4529108 UserId=zixiao(1278) JobState=STOPPED Restarts=0 NodeList=compute-0-21'
    assert m.observed_job_state(4529108, {'4529108': 'RUNNING'}, record) == (
        'STOPPED', 'slurm_controller')


def test_resumed_controller_overrides_stale_accounting_stop():
    record = 'JobId=4529108 UserId=zixiao(1278) JobState=RUNNING Restarts=0'
    assert m.observed_job_state(4529108, {'4529108': 'STOPPED'}, record) == (
        'RUNNING', 'slurm_controller')


def test_unavailable_controller_fallback_is_explicit_and_unknown_stays_unknown():
    assert m.observed_job_state(2, {'2': 'COMPLETED'}, '') == ('COMPLETED', 'accounting_fallback')
    assert m.observed_job_state(3, {}, 'JobId=2 UserId=zixiao(1278) JobState=RUNNING') == (
        'UNKNOWN', 'accounting_fallback')


def test_other_owner_cannot_be_associated_with_model_run():
    with pytest.raises(ValueError, match='ownership'):
        m.observed_job_state(2, {'2': 'RUNNING'}, 'JobId=2 UserId=other(999) JobState=RUNNING')


def test_missing_current_state_is_an_observation_error():
    with pytest.raises(ValueError, match='lacks'):
        m.observed_job_state(2, {'2': 'RUNNING'}, 'JobId=2 UserId=zixiao(1278)')
