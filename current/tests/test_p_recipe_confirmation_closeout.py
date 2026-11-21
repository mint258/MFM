from pathlib import Path
import runpy
import pytest


def _module(monkeypatch):
    folder=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    monkeypatch.syspath_prepend(str(folder))
    return runpy.run_path(str(folder/'final_comparisons.py'))


def test_completed_four_arm_plan_has_no_cancelled_or_scaling_decision(monkeypatch):
    m=_module(monkeypatch);authority=m['CLOSEOUT']
    configs={arm:dict(arm=arm,run=arm,output='/synthetic/'+arm,samples=9000000,
                     study_revision='fixed_20261115') for arm in ('T1','T2','T5','T6')}
    ledger={'runs':{arm:{'state':'COMPLETED','exit_code':'0:0'} for arm in configs}}
    plan=dict(configurations=[arm+'.json' for arm in configs],selection_authority=authority,
              recipe_frozen=True,T7_required=False,T4_included=False,T4_user_decision='OMIT',
              T4_user_confirmation=authority,study_revision='fixed_20261115',samples_per_run=9000000,
              Pprime_comparator='T2')
    def read(path):
        name=Path(path).name
        if name=='study_execution.json':return ledger
        if name=='summary.json':return {'status':'COMPLETE','samples':9000000}
        if name.endswith('.json') and name[:-5] in configs:return configs[name[:-5]]
        raise AssertionError('Unexpected access: '+str(path))
    function=m['completed_configurations'];scope=function.__globals__
    monkeypatch.setitem(scope,'read',read)
    monkeypatch.setitem(scope,'summaries',lambda c:{r:{'complete':True,'bootstrap_samples':1000,'bootstrap_defined':1000} for r in ('R1','R3')})
    actual=function(plan)
    assert set(actual)=={'T1','T2','T5','T6'}
    deciding,descriptive=m['comparison_layout'](plan,actual)
    assert deciding==[('T2','T1','confirmation')]
    assert {a for pair in descriptive for a in pair[:2]}=={'T2','T5','T6'}
    configs['T3']=dict(configs['T2'],arm='T3',run='T3')
    plan['configurations'].append('T3.json')
    with pytest.raises(ValueError,match='arms differ'):function(plan)


def test_negative_confirmation_does_not_reopen_frozen_recipe(monkeypatch):
    m=_module(monkeypatch)
    plan={'selection_authority':m['CLOSEOUT']}
    configs={'T1':{'components':[]},'T2':{'components':['A1']}}
    rows=[{'purpose':'confirmation','readout':'R3','verdict':'loss'}]
    assert m['final_recipe_choice'](plan,configs,rows)==('T2',None)
