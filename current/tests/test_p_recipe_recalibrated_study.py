"""Recalibration must not mix old decisions, budgets or archived outputs."""
import csv
import importlib.util
import json
import sys
from pathlib import Path
import pytest
from phychem_mfm.phase1.p_recipe_plan import configuration


def tool(name):
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe'
    sys.path.insert(0,str(path))
    spec=importlib.util.spec_from_file_location('test_recalibrated_'+name,path/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def base_file(tmp_path):
    base=dict(batch_size=32,lr=6e-4,output=str(tmp_path/'weights'/'base'),
        samples=3000000,screening_samples=2000000,study_revision='recalibrated',
        run_prefix='new_',results_directory='results/p_recipe/recalibrated_20261114',
        checkpoint_policy='screen_final_confirmation_milestones',normalizations='frozen11-07',
        clip_calibration=dict(fraction=.05,initial_clip=281.7,quantile=.99))
    path=tmp_path/'selected_base.json';path.write_text(json.dumps(base));return path,base


def test_new_budget_and_run_names_leave_archived_round_untouched(tmp_path,monkeypatch):
    module=tool('prepare_round');base_path,base=base_file(tmp_path)
    monkeypatch.setattr(module,'REPO',tmp_path/'repository')
    monkeypatch.setattr(module,'R',tmp_path/'server');monkeypatch.setattr(module,'OUT',tmp_path/'fits')
    decision=module.R/'runs/p_recipe_20261113/D2_decision.json'
    decision.parent.mkdir(parents=True);decision.write_text('{"A5":true}')
    archived=module.REPO/'configs/p_recipe/round1/B0.json'
    archived.parent.mkdir(parents=True);archived.write_text('archived original configuration')
    plan=module.prepare(1,base_configuration=base_path,study_directory='configs/p_recipe/new_study')
    assert len(plan['configurations'])==6 and plan['study_revision']=='recalibrated'
    assert plan['results_directory']==base['results_directory']
    for path in plan['configurations']:
        c=json.loads(Path(path).read_text())
        assert c['run'].startswith('new_round1_') and c['samples']==2000000
        assert c['batch_size']==c['microbatch_size']==32
        assert c['checkpoint_samples']==[2000000]
        assert c['normalizations']=='frozen11-07' and c['clip_calibration']==base['clip_calibration']
    assert archived.read_text()=='archived original configuration'


def test_invalidated_previous_decision_cannot_generate_the_next_round(tmp_path):
    path,_=base_file(tmp_path)
    with pytest.raises(ValueError,match='invalidated'):
        tool('prepare_round').prepare(2,dict(merged_components=[],selection_valid=False),base_configuration=path,study_directory=tmp_path/'new')
    assert not (tmp_path/'new').exists()


def test_new_decision_cannot_fall_back_to_an_unrevised_base(tmp_path):
    path,base=base_file(tmp_path);base.pop('study_revision');path.write_text(json.dumps(base))
    with pytest.raises(ValueError,match='different study revision'):
        tool('prepare_round').prepare(2,dict(merged_components=[],selection_valid=True,study_revision='recalibrated'),base_configuration=path,study_directory=tmp_path/'new')
    assert not (tmp_path/'new').exists()


def test_confirmation_keeps_its_full_budget_and_milestone_checkpoints(tmp_path):
    _,base=base_file(tmp_path)
    base.update(speed_calibration=True,calibration_training=True,evaluation_samples=[1500000,3000000],required_gpu_uuid='old-speed-card',resume='old-checkpoint')
    c=configuration(base,{'C1'},run='new_confirmation_T2',round_number=0,arm='T2',samples=4500000,stage=3)
    assert c['samples']==4500000 and c['checkpoint_samples']==list(range(500000,4500001,500000))
    assert c['batch_size']==32 and c['lr']==pytest.approx(.0012)
    assert not {'speed_calibration','calibration_training','evaluation_samples','required_gpu_uuid','resume'}&c.keys()


def test_old_gpu_cost_does_not_consume_the_new_screening_budget():
    records=[dict(stage=2,round=1,state='COMPLETED',elapsed_seconds=67*3600),
             dict(stage=2,round=2,state='CANCELLED',elapsed_seconds=2*3600),
             dict(stage=2,round=1,state='COMPLETED',elapsed_seconds=3*3600,study_revision='new'),
             dict(stage=2,round=1,state='FAILED',elapsed_seconds=360,study_revision='new'),
             dict(stage=2,round=2,state='RUNNING',elapsed_seconds=100*3600,study_revision='new'),
             dict(stage='calibration',round=0,state='COMPLETED',elapsed_seconds=40*3600,study_revision='new')]
    all_rounds,revisions=tool('collect_execution').completed_screening_hours(records)
    assert all_rounds['1']==pytest.approx(70.1)
    assert revisions['new']=={'1':pytest.approx(3.1)}
    assert revisions['original_20261113']=={'1':67.,'2':2.}


def test_new_deltas_upsert_without_overwriting_the_old_archive(tmp_path):
    module=tool('decide_round');old=tmp_path/'old/deltas.csv';old.parent.mkdir();old.write_text('archived original deltas')
    target=tmp_path/'new/deltas.csv'
    row=dict(purpose='screening',round=1,readout='R3',task='MEAN',A='new_A1',B='new_B0',delta=.02,ci_lower=.01,ci_upper=.03,verdict='win')
    module.write_deltas([row],target)
    module.write_deltas([dict(row,delta=.04)],target)
    with target.open() as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==1 and float(rows[0]['delta'])==.04
    assert old.read_text()=='archived original deltas'


def test_comparison_refuses_a_previous_state_from_another_revision():
    with pytest.raises(ValueError,match='different study revisions'):
        tool('decide_round').close(dict(study_revision='new'),dict(study_revision='old',selection_valid=True),0.)
