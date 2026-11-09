"""Top-two preparation uses joint actual conditions, never one-condition wins."""
import importlib.util
import json
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('c1_repeat_preparer',
    Path(__file__).resolve().parents[2]/'tools/model_v3/v2_prepare_c1_repeats.py')
preparer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)


def rows():
    scores={'C1-0':(.4,.2),'C1-a':(.3,.5),'C1-b':(.9,-.6)}
    return [dict(candidate=c,condition=condition,seed=0,score=score)
        for c,pair in scores.items() for condition,score in zip(('S','P'),pair)]


def test_joint_top_two_does_not_promote_the_best_s_only_candidate_or_claim_a_final_winner():
    result=preparer.rank_initial(rows())
    assert result['selected_top_two']==['C1-a','C1-0']
    assert result['joint_seed0_scores']['C1-a']==pytest.approx(.4,abs=1e-12,rel=1e-12)
    assert result['selected_architecture'] is None and result['seed_standard_deviation'] is None


@pytest.mark.parametrize('change',['missing','duplicate','wrong_seed','nonfinite'])
def test_partial_duplicate_or_wrong_seed_results_cannot_select_repeats(change):
    data=rows()
    if change=='missing':data.pop()
    elif change=='duplicate':data[-1]=data[0]
    elif change=='wrong_seed':data[-1]['seed']=1
    else:data[-1]['score']=float('nan')
    with pytest.raises(ValueError):preparer.rank_initial(data)


def test_exact_initial_ties_use_the_predeclared_candidate_order():
    data=rows()
    for row in data:row['score']=.2
    assert preparer.rank_initial(data)['selected_top_two']==['C1-0','C1-a']


def test_p_repeat_changes_only_seed_and_output():
    original=dict(root='/published/D6',condition='P',seed=0,output='/old',candidate='C1-a',
        head_form='H1',views='three',normalizations='/D4',subset_path='/original240k',
        samples=6000000,lr=.0003,clip=1.,extra_scientific_option={'fixed':True})
    mode,result=preparer.repeat_configuration('P','C1-a',original)
    assert mode=='v31' and result['seed']==1 and result['output']!=original['output']
    assert {k:v for k,v in result.items() if k not in ('seed','output')}=={
        k:v for k,v in original.items() if k not in ('seed','output')}
    assert original['seed']==0


def test_s_repeat_preserves_original_index_and_every_supported_scientific_argument():
    original=dict(distance_bias='C1-a',views='three',samples=6000000,batch_size=32,
        lr=.0003,schedule='cosine',clip=1.,D5_index='/original/S240k.parquet',betas=[.9,.95])
    mode,result=preparer.repeat_configuration('S','C1-a',original)
    assert mode=='native_s' and result['index_path']==original['D5_index'] and result['seed']==1
    for key in ('distance_bias','views','samples','batch_size','lr','schedule','clip'):
        assert result[key]==original[key]


def closed_result(tmp_path):
    configuration=dict(condition='P',distance_bias='C1-a',seed=0,views='three',samples=6000000,
        batch_size=32,lr=.0003,schedule='cosine',clip=1,expected_molecules=240000)
    summary=dict(complete=True,consumed_samples=6000000,tasks={'task/ridge':dict(normalized_improvement=.2)},
        source_roles=['train','train_inner_validation'],downstream_TEST_read=False,
        checkpoint=str(tmp_path/'samples_6000000.pt'),mean_normalized_improvement=.2)
    return configuration,summary


@pytest.mark.parametrize('change',[None,'incomplete','early_checkpoint','different_cells','test_role','wrong_candidate'])
def test_only_complete_original_development_results_are_read_for_ranking(tmp_path,change):
    configuration,summary=closed_result(tmp_path)
    if change=='incomplete':summary['complete']=False
    elif change=='early_checkpoint':summary['consumed_samples']=1000000
    elif change=='different_cells':summary['tasks']={}
    elif change=='test_role':summary['source_roles'].append('test')
    elif change=='wrong_candidate':configuration['distance_bias']='C1-b'
    (tmp_path/'configuration.json').write_text(json.dumps(configuration))
    (tmp_path/'dev_eval').mkdir()
    (tmp_path/'dev_eval/summary.json').write_text(json.dumps(summary))
    entry=dict(directory=str(tmp_path),condition='P',candidate='C1-a')
    if change is None:
        row,original=preparer.initial_result(entry,{'task/ridge'})
        assert row['score']==.2 and original==configuration
        assert not (tmp_path/'samples_6000000.pt').exists() # No checkpoint/label reread required.
    else:
        with pytest.raises(ValueError):preparer.initial_result(entry,{'task/ridge'})


def test_prepare_writes_only_four_selected_repeats_and_preserves_them_on_identical_retry(tmp_path):
    panel=json.loads((preparer.REPO/'configs/dev_panel_v1.json').read_text())
    cells={t['task_id']+'/'+r for t in panel['tasks'] for r in ('ridge','linear64_relu')}
    inputs=dict(runs=[])
    for row in rows():
        directory=tmp_path/(row['condition']+'_'+row['candidate'])
        directory.mkdir();(directory/'dev_eval').mkdir()
        configuration,summary=closed_result(directory)
        configuration.update(condition=row['condition'],distance_bias=row['candidate'],
            root='/published/D6',D5_index='/original/S240k.parquet',betas=[.9,.95])
        summary.update(mean_normalized_improvement=row['score'],tasks={
            cell:dict(normalized_improvement=row['score']) for cell in cells})
        (directory/'configuration.json').write_text(json.dumps(configuration))
        (directory/'dev_eval/summary.json').write_text(json.dumps(summary))
        inputs['runs'].append(dict(directory=str(directory),condition=row['condition'],candidate=row['candidate']))
    output=tmp_path/'prepared'
    result=preparer.prepare(inputs,output)
    assert result['selected_top_two']==['C1-a','C1-0'] and len(result['prepared_repeats'])==4
    assert {p.name for p in output.iterdir()}=={
        'S_C1-a_seed1.json','P_C1-a_seed1.json','S_C1-0_seed1.json','P_C1-0_seed1.json','selection.json'}
    before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in output.iterdir()}
    assert preparer.prepare(inputs,output)==result
    assert before=={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in output.iterdir()}
