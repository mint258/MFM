"""User cap removal keeps registered round and empty-round rules."""
import importlib.util
from pathlib import Path
def tool():
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe/decide_round.py'
    spec=importlib.util.spec_from_file_location('directive_decide_round',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def test_cancelled_gpu_cap():
    assert tool().screening_stop_reasons(dict(round=2,screening_gpu_hour_limit=None),0,350)==[]
def test_legacy_cap():
    assert tool().screening_stop_reasons(dict(round=2),0,200)==['Screening reached200GPUh; current round completed']
def test_other_registered_limits_remain():
    assert tool().screening_stop_reasons(dict(round=3,screening_gpu_hour_limit=None),2,350)==['Three registered rounds completed','Two consecutive rounds without winning components']

def test_nfs_default_reserve():
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe/native_run.py'
    spec=importlib.util.spec_from_file_location('directive_native',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.nfs_growth({})==67108864
    assert module.nfs_growth({'nfs_future_bytes':2147483648})==2147483648

def test_nfs_reserve_cannot_shrink_below_existing_floor():
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe/native_run.py'
    spec=importlib.util.spec_from_file_location('directive_native_floor',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.nfs_growth({'nfs_future_bytes':1})==67108864