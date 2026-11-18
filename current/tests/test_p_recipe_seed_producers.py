from pathlib import Path
import json,runpy
import pytest


def module(monkeypatch,name):
    folder=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    monkeypatch.syspath_prepend(str(folder))
    return runpy.run_path(str(folder/name))


def publish(c,score,ledger):
    output=Path(c['output']);(output/'readout').mkdir(parents=True,exist_ok=True)
    (output/'summary.json').write_text(json.dumps(dict(status='COMPLETE',samples=c['samples'],updates=93750)))
    result={r:dict(complete=True,bootstrap_samples=1000,bootstrap_defined=1000,
        mean_normalized_improvement=score,paired_bootstrap={'values':[score]*1000}) for r in ('R3','R1')}
    (output/'readout/scores.json').write_text(json.dumps(result))
    ledger['runs'][c['run']]={'state':'COMPLETED','exit_code':'0:0'}


def configuration(tmp,arm,*,components=None,samples=3000000):
    c=dict(run=arm,arm=arm,seed=0,output=str(tmp/arm),samples=samples,lr=.0003,
        batch_size=32,components=components or [],p_recipe={},label_parameters='/synthetic/parameters.json')
    path=tmp/(arm+'.json');path.write_text(json.dumps(c));return path,c


def factory(monkeypatch,tmp,ledger,baseline=None):
    m=module(monkeypatch,'seed_comparisons.py')
    references={}
    if baseline:
        child=dict(baseline,seed=1,run=baseline['run']+'_existing1',output=str(tmp/'existing1'))
        publish(child,.402,ledger);path=tmp/'existing1.json';path.write_text(json.dumps(child))
        references[baseline['run']]=str(path)
    return lambda:m['SeedComparisons'](tmp/'comparisons',registry=tmp/'registry.json',
        configuration_directory=tmp/'children',ledger=ledger,reference=tmp/'none.json',
        reference_configurations=references)


def finish_children(tmp,ledger,scores):
    for path in (tmp/'children').glob('*.json'):
        c=json.loads(path.read_text());publish(c,scores[c['seed0_run']],ledger)


def test_round3_waits_without_final_deltas_then_uses_two_seed_verdict(tmp_path,monkeypatch):
    m=module(monkeypatch,'decide_round.py');ledger={'runs':{}}
    bp,b=configuration(tmp_path,'M2',components=['A1','B3','B4'])
    ap,a=configuration(tmp_path,'C3',components=b['components']+['C3'])
    publish(b,.4,ledger);publish(a,.424,ledger);make=factory(monkeypatch,tmp_path,ledger,b)
    plan=dict(round=3,baseline='M2',baseline_components=b['components'],configurations=[str(bp),str(ap)],
        study_revision='fixed_20261115',control_directory=str(tmp_path))
    written=[];monkeypatch.setitem(m['close'].__globals__,'write_deltas',lambda rows,*_:written.extend(rows))
    pending=m['close'](plan,None,1.,seed_session=make())
    assert not pending['conditional_seed_decisions_complete'] and written==[]
    comparison=next(iter(pending['seed_comparisons']['comparisons'].values()))
    assert comparison['seed0_rows'][0]['verdict']=='win'
    finish_children(tmp_path,ledger,{'C3':.38})
    final=m['close'](plan,None,1.,seed_session=make())
    assert final['conditional_seed_decisions_complete'] and final['decisions']['C3']['verdict']=='tie'
    assert final['adopted_winners']==[] and not final['screening_finished']
    assert written[0]['delta']==pytest.approx(.001)


def test_round4_uses_conditional_results_and_keeps_simpler_ties(tmp_path,monkeypatch):
    m=module(monkeypatch,'decide_round4.py');ledger={'runs':{}};configs={};paths={}
    base=['A1','B3','B4']
    for arm,score,components in [('M2',.4,base),('PP',.395,base),('X1',.405,base+['X1']),
                                 ('X2',.424,base+['X2']),('F2',.4,base+['F2']),('F1',None,base+['F1'])]:
        paths[arm],configs[arm]=configuration(tmp_path,arm,components=components)
        if score is not None:publish(configs[arm],score,ledger)
    original=m['read']
    monkeypatch.setitem(m['close'].__globals__,'read',lambda p:ledger if Path(p).name=='study_execution.json' else original(p))
    make=factory(monkeypatch,tmp_path,ledger,configs['M2'])
    plan=dict(study_revision='fixed_20261115',baseline_configuration=str(paths['M2']),
        registered_configurations=[str(p) for p in paths.values()],unresolved_arms={'F1':'registered development timebox'},
        M2C_required=False,control_directory=str(tmp_path),fidelity_pairs=str(tmp_path/'recipe/fidelity_pairs.json'))
    round3=dict(round=3,study_revision='fixed_20261115',merged_components=base,component_evidence={},screening_gpu_hours=1.)
    written=[];monkeypatch.setitem(m['close'].__globals__,'write_deltas',lambda rows,*_:written.extend(rows))
    pending=m['close'](plan,round3,str(paths['M2']),1.,seed_session=make())
    assert not pending['conditional_seed_decisions_complete'] and written==[]
    finish_children(tmp_path,ledger,{'X2':.425})
    final=m['close'](plan,round3,str(paths['M2']),1.,seed_session=make())
    assert final['merge_validation_complete'] and not final['merge_required']
    assert final['adopted_winners']==['F2','X2']
    assert final['decisions']['F2']['verdict']=='tie' and final['decisions']['X2']['verdict']=='win'
    assert final['T4_user_decision']=='KEEP' and final['T4_user_confirmation']==m['CLOSEOUT']


@pytest.mark.parametrize('delta,lower,upper,expected',[(.04,.03,.05,'OMIT'),(-.04,-.05,-.03,'OMIT'),
                                                    (.01,.005,.015,'KEEP'),(.04,-.01,.08,'KEEP')])
def test_pp_t4_automatic_seed0_rule_does_not_wait_for_other_results(monkeypatch,delta,lower,upper,expected):
    m=module(monkeypatch,'decide_round4.py')
    row=dict(delta=delta,ci_lower=lower,ci_upper=upper,verdict='tie')
    result=dict(ready=False,seed0_rows=[row],seed0_evidence={'R3':{'mean_score_A':.4+delta,'mean_score_B':.4}})
    noise={'ready_for_reuse':True,'observed_seed_noise':{'seed1_minus_seed0':{'R3':.00205}}}
    state=m['pp_disposition']({'run':'PP'},{'run':'M2'},result,noise)
    assert state['T4_user_decision']==expected and state['omission_automatic']
    assert not state['PP_conditional_seed_decision_complete']


def test_final_preflight_reuses_children_and_reports_two_seed_scores(tmp_path,monkeypatch):
    m=module(monkeypatch,'final_comparisons.py');ledger={'runs':{}};configs={}
    for arm,score in [('T1',.4),('T2',.424),('T5',.39),('T6',.4)]:
        _,configs[arm]=configuration(tmp_path,arm,samples=9000000);publish(configs[arm],score,ledger)
    make=factory(monkeypatch,tmp_path,ledger)
    plan={'selection_authority':m['CLOSEOUT']}
    state,rows=m['confirmation_seed_results'](plan,configs,make())
    assert rows is None and len(json.loads(Path(state['seed1_plan']).read_text())['configurations'])==2
    assert {json.loads(p.read_text())['seed0_run'] for p in (tmp_path/'children').glob('*.json')}=={'T1','T2'}
    finish_children(tmp_path,ledger,{'T1':.4,'T2':.44})
    state,rows=m['confirmation_seed_results'](plan,configs,make())
    assert rows[0]['delta']==pytest.approx(.032) and rows[0]['verdict']=='win'
    assert all(row['verdict']=='descriptive' for row in rows if row['purpose']=='molecule_scaling')
    render=module(monkeypatch,'render_report.py')
    text='\n'.join(render['seed_sections']([],{'seed_comparisons':state}))
    assert '0.424' in text and '0.44' in text and '0.032' in text
