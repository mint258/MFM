"""Protect the final suite from process reuse and unbudgeted output."""
import importlib
from pathlib import Path
import pytest


@pytest.fixture
def suite(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2]/'tools/model_v3'))
    return importlib.import_module('cpu_perf_regression')


def identity():
    return dict(status='ACTIVE',pid=12,uid=1,boot_id='boot',start_ticks=25,
        pgid=12,sid=12,argv_sha256='cmd',cgroup='job',slurm_job_id='1')


def test_live_identity_change_is_rejected_before_cleanup_authority_changes(suite):
    observed={}; original=identity()
    suite.bind(observed,original)
    with pytest.raises(RuntimeError,match='identity changed'):
        suite.bind(observed,dict(original,argv_sha256='other'))
    assert observed[(12,25)] is original


def test_exiting_or_unknown_process_does_not_acquire_signal_authority(suite):
    observed={}
    suite.bind(observed,dict(identity(),status='EXITING'))
    suite.bind(observed,dict(identity(),status='GONE'))
    with pytest.raises(RuntimeError,match='Cannot bind'):
        suite.bind(observed,dict(identity(),status='FOREIGN'))
    assert not observed


def test_suite_reserves_new_output_in_addition_to_concurrent_forecasts(suite,monkeypatch,tmp_path):
    monkeypatch.setattr(suite,'capacity',lambda:{'prior':'retained'})
    monkeypatch.setattr(suite,'filesystem_status',lambda p:{})
    monkeypatch.setattr(suite,'require_capacity',lambda *a:None)
    calls=[]
    def quota(*args):
        calls.append(args); return dict(available=160_000_000_000,required=140_000_000_000)
    monkeypatch.setattr(suite,'quota_headroom',quota)
    result=suite.storage(tmp_path)
    assert calls[0][2:]==(suite.OUTPUT_PEAK+64*1024**2,23_179_869_184)
    assert result['existing_forecasts']=={'prior':'retained'}


def test_unknown_account_capacity_prevents_suite_output(suite,monkeypatch,tmp_path):
    monkeypatch.setattr(suite,'capacity',lambda:(_ for _ in ()).throw(OSError('quota unknown')))
    with pytest.raises(OSError,match='quota unknown'):
        suite.storage(tmp_path/'new')
    assert not (tmp_path/'new').exists()
