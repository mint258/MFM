"""A per-card calibration must not silently run on a different available card."""
import importlib.util
import sys
from pathlib import Path


def launcher():
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    sys.path.insert(0,str(path))
    spec=importlib.util.spec_from_file_location('calibration_launcher',path/'launch_plan.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_pin_uses_matching_card_and_leaves_higher_ranked_card_available():
    cards=[dict(gpu_uuid='5090'),dict(gpu_uuid='4090')]
    selected=launcher().take_card(cards,[],required_gpu_uuid='4090')
    assert selected['gpu_uuid']=='4090'
    assert cards==[dict(gpu_uuid='5090')]


def test_missing_pin_waits_without_consuming_another_card():
    cards=[dict(gpu_uuid='5090')];fallback=[dict(gpu_uuid='3090')]
    assert launcher().take_card(cards,fallback,required_gpu_uuid='absent') is None
    assert len(cards)==len(fallback)==1


def test_pin_can_select_the_previously_used_fallback_gpu():
    cards=[dict(gpu_uuid='5090')];fallback=[dict(gpu_uuid='3090')]
    assert launcher().take_card(cards,fallback,required_gpu_uuid='3090')['gpu_uuid']=='3090'
    assert len(cards)==1 and not fallback


def test_occupied_fallback_is_skipped_before_submission(tmp_path,monkeypatch):
    import json
    module=launcher()
    monkeypatch.setattr(module,'C',tmp_path)
    inventory=[dict(node='compute-0-5',gpus=[['busy']]),dict(node='compute-0-6',gpus=[['free']])]
    (tmp_path/'batch_gpu_inventory.json').write_text(json.dumps(inventory))
    configuration=tmp_path/'A.json'
    configuration.write_text(json.dumps(dict(run='A',workers=4,output=str(tmp_path/'out'),stage=2,round=2)))
    def observe(node):
        if node not in ('compute-0-5','compute-0-6'):return []
        busy=node=='compute-0-5'
        return [dict(node=node,gpu_uuid='busy' if busy else 'free',used_mib=100,total_mib=24576,
                     gpu_name='RTX3090',free_cpus=64,existing_compute_context=busy)]
    monkeypatch.setattr(module,'observe',observe)
    monkeypatch.setattr(module,'own_gpu_busy',lambda gpu,node=None:False)
    calls=[]
    def submit(command,**kwargs):
        calls.append(command)
        return '12345\n'
    monkeypatch.setattr(module.subprocess,'check_output',submit)
    ledger=module.launch_locked(dict(configurations=[str(configuration)]),dict(runs={}))
    assert ledger['runs']['A']['gpu_uuid']=='free'
    assert len(calls)==1 and '--nodelist=compute-0-6' in calls[0]


def test_lock_admission_checks_actual_compute_node(tmp_path,monkeypatch):
    from types import SimpleNamespace
    module=launcher();monkeypatch.setattr(module,'R',tmp_path)
    calls=[]
    def query(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0,stdout='BUSY\n')
    monkeypatch.setattr(module.subprocess,'run',query)
    assert module.own_gpu_busy('GPU-fixture','compute-0-20')
    assert calls[0][0]=='ssh' and 'compute-0-20' in calls[0]
