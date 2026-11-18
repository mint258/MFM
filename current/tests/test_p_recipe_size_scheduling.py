from pathlib import Path
import json,runpy
import pytest


def module(monkeypatch):
    folder=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    monkeypatch.syspath_prepend(str(folder))
    return runpy.run_path(str(folder/'launch_plan.py'))


def card(node,gpu,**changes):
    return dict(node=node,gpu_uuid=gpu,free_cpus=16,used_mib=5,total_mib=24576,
                gpu_name='RTX'+gpu,existing_compute_context=False,**changes)


@pytest.mark.parametrize('samples,low_changes,high_changes,pin,expected',[
    (3000000,{}, {},None,'3090'),(3000001,{}, {},None,'5090'),
    (3000000,{'free_cpus':15},{},None,'5090'),
    (3000000,{'existing_compute_context':True},{},None,'5090'),
    (9000000,{}, {'used_mib':20000},None,'3090'),
    (3000000,{'free_cpus':0},{'used_mib':20000},None,None),
    (3000000,{}, {},'5090','5090')])
def test_budget_preference_falls_back_only_to_admissible_card(monkeypatch,samples,low_changes,high_changes,pin,expected):
    m=module(monkeypatch)
    low=card('compute-0-5','3090');low.update(low_changes)
    high=card('compute-0-22','5090');high.update(high_changes)
    native=[high];small=[low]
    policy=dict(cpu_overhead=2,maximum_existing_gpu_memory_fraction=.30,minimum_free_gpu_mib=18432)
    actual=m['take_card'](native,small,pin,configuration={'samples':samples,'workers':14},policy=policy)
    assert (actual['gpu_uuid'] if actual else None)==expected
    assert len(native)+len(small)==(1 if expected else 2)


def test_actual_cpu_only_node_is_rejected_before_gpu_probe(monkeypatch):
    m=module(monkeypatch);calls=[]
    def query(argv,**kwargs):
        calls.append(argv);return 'State=IDLE CPUTot=48 CPUAlloc=0 Partitions=cpu'
    monkeypatch.setattr(m['subprocess'],'check_output',query)
    with pytest.raises(ValueError,match='actual gpu partition'):m['observe']('compute-0-2')
    assert calls==[['scontrol','show','node','compute-0-2','-o']]


def test_mixed_plan_uses_both_groups_without_old_inventory(tmp_path,monkeypatch):
    m=module(monkeypatch);scope=m['launch_locked'].__globals__
    monkeypatch.setitem(scope,'C',tmp_path);monkeypatch.setitem(scope,'REPO',tmp_path)
    root=tmp_path/'configs/p_recipe';root.mkdir(parents=True)
    policy=dict(nodes=['compute-0-5','compute-0-20','compute-0-22'],exclusive=False,partition='gpu',
        cpu_overhead=2,maximum_existing_gpu_memory_fraction=.30,minimum_free_gpu_mib=18432,
        gpu_preference=['5090','4090','3090'],small_task_maximum_samples=3000000)
    (root/'scheduling.json').write_text(json.dumps(policy))
    available={'compute-0-5':card('compute-0-5','3090'),'compute-0-20':card('compute-0-20','4090'),
               'compute-0-22':card('compute-0-22','5090')}
    monkeypatch.setitem(scope,'observe',lambda node:[available[node]])
    monkeypatch.setitem(scope,'own_gpu_busy',lambda *_:False)
    calls=[]
    def submit(argv,**kwargs):
        assert argv[0]=='sbatch';calls.append(argv);return str(100+len(calls))+'\n'
    monkeypatch.setattr(m['subprocess'],'check_output',submit)
    paths=[]
    for name,budget in [('small',3000000),('large',9000000),('overflow',3000000)]:
        path=tmp_path/(name+'.json');path.write_text(json.dumps(dict(run=name,samples=budget,workers=14,
            output=str(tmp_path/name),stage=2 if budget==3000000 else 3,round=4)))
        paths.append(str(path))
    ledger=m['launch_locked']({'configurations':paths},{'runs':{}})
    assert [ledger['runs'][name]['node'] for name in ('small','large','overflow')]==[
        'compute-0-5','compute-0-22','compute-0-20']
    assert len(calls)==3 and all('--cpus-per-task=16' in call and '--exclusive' not in call for call in calls)
    assert not (tmp_path/'batch_gpu_inventory.json').exists()
