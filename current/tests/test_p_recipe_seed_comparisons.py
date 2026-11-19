from pathlib import Path
import json,runpy
import pytest


def module(monkeypatch):
    folder=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    monkeypatch.syspath_prepend(str(folder))
    return runpy.run_path(str(folder/'seed_comparisons.py'))


def publish(c,score,ledger):
    output=Path(c['output']);(output/'readout').mkdir(parents=True,exist_ok=True)
    (output/'summary.json').write_text(json.dumps({'status':'COMPLETE','samples':c['samples']}))
    values={r:dict(complete=True,bootstrap_samples=1000,bootstrap_defined=1000,
                  mean_normalized_improvement=score,paired_bootstrap={'values':[score]*1000}) for r in ('R1','R3')}
    (output/'readout/scores.json').write_text(json.dumps(values))
    ledger['runs'][c['run']]={'state':'COMPLETED','exit_code':'0:0'}


def config(tmp,run,seed=0):
    return dict(run=run,seed=seed,output=str(tmp/run),samples=3000000,batch_size=32,lr=.0003,p_recipe={})


@pytest.mark.parametrize('score,descriptive',[(.404,False),(.42,True)])
def test_clear_or_descriptive_comparison_creates_no_seed1(tmp_path,monkeypatch,score,descriptive):
    m=module(monkeypatch);ledger={'runs':{}}
    a=config(tmp_path,'candidate');b=config(tmp_path,'baseline')
    publish(a,score,ledger);publish(b,.4,ledger)
    session=m['SeedComparisons'](tmp_path/'comparison',registry=tmp_path/'registry.json',
        configuration_directory=tmp_path/'children',ledger=ledger,reference=tmp_path/'no_reference.json')
    result=session.assess(a,b,'scaling' if descriptive else 'screening',4,descriptive=descriptive)
    assert result['ready'] and result['seed_count']==1 and not result['seed1_required']
    assert not (tmp_path/'children').exists() and not (tmp_path/'registry.json').exists()
    state=session.save()
    assert json.loads(Path(state['seed1_plan']).read_text())['configurations']==[]


def test_borderline_reuses_reference_and_waits_for_only_one_fresh_child(tmp_path,monkeypatch):
    m=module(monkeypatch);ledger={'runs':{}}
    a=config(tmp_path,'candidate');a['resume']='/old/seed0_checkpoint'
    b=config(tmp_path,'baseline');b1=config(tmp_path,'shared_baseline_seed1',1)
    publish(a,.42,ledger);publish(b,.4,ledger);publish(b1,.402,ledger)
    b1path=tmp_path/'shared.json';b1path.write_text(json.dumps(b1))
    reference=tmp_path/'reference.json';reference.write_text(json.dumps(dict(ready_for_reuse=True,samples=3000000,
        observed_seed_noise={'seed0_run':'baseline'},configuration=str(b1path))))
    kwargs=dict(registry=tmp_path/'registry.json',configuration_directory=tmp_path/'children',ledger=ledger,reference=reference)
    session=m['SeedComparisons'](tmp_path/'comparison',**kwargs)
    first=session.assess(a,b,'screening',4)
    assert not first['ready'] and first['status']=='WAITING_FOR_REGISTERED_SEED1'
    state=session.save();plan=json.loads(Path(state['seed1_plan']).read_text())
    assert len(plan['configurations'])==1
    child_path=Path(plan['configurations'][0]);child=json.loads(child_path.read_text())
    assert child['seed']==1 and child['seed0_run']=='candidate' and 'resume' not in child
    assert list((tmp_path/'children').iterdir())==[child_path]
    publish(child,.438,ledger)
    combined=m['combined_seed_decision'];calls=[]
    def only_new_combination(pairs):
        calls.append(set(pairs));assert set(pairs)=={0,1}
        return combined(pairs)
    monkeypatch.setitem(session.assess.__func__.__globals__,'combined_seed_decision',only_new_combination)
    final=m['SeedComparisons'](tmp_path/'comparison',**kwargs)
    result=final.assess(a,b,'screening',4)
    assert result['ready'] and result['seed_count']==2
    assert result['rows'][0]['delta']==pytest.approx(.028)
    assert calls==[{0,1},{0,1}]
    state=final.save()
    assert json.loads(Path(state['seed1_plan']).read_text())['configurations']==[]


@pytest.mark.parametrize('context',['R1_only','descriptive_scaling'])
def test_report_only_metadata_cannot_request_seed1_or_decide_scaling(tmp_path,monkeypatch,context):
    m=module(monkeypatch);ledger={'runs':{}}
    a=config(tmp_path,'candidate');b=config(tmp_path,'baseline')
    descriptive=context=='descriptive_scaling'
    publish(a,.424 if descriptive else .404,ledger);publish(b,.4,ledger)
    if not descriptive:
        path=Path(a['output'])/'readout/scores.json';scores=json.loads(path.read_text())
        scores['R1'].update(mean_normalized_improvement=.424,paired_bootstrap={'values':[.424]*1000})
        path.write_text(json.dumps(scores))
    session=m['SeedComparisons'](tmp_path/'comparison',registry=tmp_path/'registry.json',
        configuration_directory=tmp_path/'children',ledger=ledger,reference=tmp_path/'no_reference.json')
    result=session.assess(a,b,'molecule_scaling' if descriptive else 'screening',0 if descriptive else 4,
                          descriptive=descriptive)
    assert result['ready'] and result['seed_count']==1 and not result['seed1_required']
    assert not (tmp_path/'registry.json').exists() and not (tmp_path/'children').exists()
    assert not result['evidence']['R1']['may_trigger_seed1']
    assert not result['evidence']['R1']['seed1_required']
    if descriptive:
        assert result['seed_trigger_readout'] is None
        assert all(item['decision']['verdict']=='descriptive' and not item['seed1_required']
                   and not item['may_trigger_seed1'] for item in result['evidence'].values())
    else:
        assert result['evidence']['R1']['seed0_borderline']
        assert result['rows'][1]['verdict']=='win'
