"""Keep measured training cost when Slurm resets elapsed time on re-entry."""
import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('elapsed,floor,expected,closed',[(0,7488.645236756653,7488.645236756653,False),(100,0,90,False),(100,0,50,True)])
def test_accounting_retains_observed_cost_floor(monkeypatch,elapsed,floor,expected,closed):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root/'tools/p_recipe'))
    spec=importlib.util.spec_from_file_location('collector_cost_test',root/'tools/p_recipe/collect_execution.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**k:f'9|FAILED|{elapsed}|1:0\n')
    monkeypatch.setattr(module,'read',lambda p:{'study_revision':'test'})
    monkeypatch.setattr(module,'progress',lambda c:{})
    monkeypatch.setattr(module,'write',lambda *a:None)
    record=dict(backend='Slurm',job_id=9,stage=2,round=2,configuration='cfg',
                allocation_pretraining_seconds=10,elapsed_seconds_floor=floor,
                accounting_closed=closed,elapsed_seconds=50,state='FAILED')
    module.collect_locked({'runs':{'run':record}})
    assert record['elapsed_seconds']==pytest.approx(expected)
    if not closed:assert record['allocation_elapsed_seconds']==elapsed
    else:assert 'allocation_elapsed_seconds' not in record


def test_native_segment_closed_after_reboot_keeps_terminal_state_and_cost(monkeypatch):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root/'tools/p_recipe'))
    spec=importlib.util.spec_from_file_location('collector_native_reboot_test',root/'tools/p_recipe/collect_execution.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'observe_native',lambda record:pytest.fail('A verified lost native segment must not be reactivated'))
    monkeypatch.setattr(module,'read',lambda path:{'study_revision':'fixed_20261115'})
    monkeypatch.setattr(module,'progress',lambda configuration:{'samples':1014368})
    monkeypatch.setattr(module,'write',lambda *args:None)
    record=dict(backend='native_SSH',stage=2,round=3,configuration='original_cfg',
                study_revision='fixed_20261115',state='NODE_FAIL',exit_code=None,
                accounting_closed=True,elapsed_seconds=13079.,end_reason='verified_node_reboot')
    ledger=module.collect_locked({'runs':{'original':record}})
    assert record['state']=='NODE_FAIL' and record['exit_code'] is None
    assert record['elapsed_seconds']==13079.
    assert ledger['completed_screening_gpu_hours_by_revision']['fixed_20261115']['3']==pytest.approx(13079./3600)
