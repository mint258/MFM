"""Keep measured training cost when Slurm resets elapsed time on re-entry."""
import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize('elapsed,floor,expected',[(0,7488.645236756653,7488.645236756653),(100,0,90)])
def test_accounting_retains_observed_cost_floor(monkeypatch,elapsed,floor,expected):
    root=Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root/'tools/p_recipe'))
    spec=importlib.util.spec_from_file_location('collector_cost_test',root/'tools/p_recipe/collect_execution.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**k:f'9|FAILED|{elapsed}|1:0\n')
    monkeypatch.setattr(module,'read',lambda p:{'study_revision':'test'})
    monkeypatch.setattr(module,'progress',lambda c:{})
    monkeypatch.setattr(module,'write',lambda *a:None)
    record=dict(backend='Slurm',job_id=9,stage=2,round=2,configuration='cfg',
                allocation_pretraining_seconds=10,elapsed_seconds_floor=floor)
    module.collect_locked({'runs':{'run':record}})
    assert record['elapsed_seconds']==pytest.approx(expected)
    assert record['allocation_elapsed_seconds']==elapsed
