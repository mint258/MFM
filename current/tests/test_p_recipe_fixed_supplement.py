import importlib.util
import json
from pathlib import Path

import pytest

from phychem_mfm.phase1.p_recipe_clip import GroupClipCalibration
from phychem_mfm.phase1.p_recipe_plan import configuration
from phychem_mfm.phase1.v2_s_training import sample_lr_ratio
from phychem_mfm.phase1.v3_training import SampleClock

POLICY=dict(calibration_samples=150000,window_start_samples=60000,initial_clip=281.7,quantile=.99)


def test_window_excludes_early_norms_preserves_full_batches_and_freezes():
    clip=GroupClipCalibration(POLICY,3000000)
    assert not clip.exact_boundary
    assert not clip.observe(1e9,60000,samples_before=59968)
    assert not clip.observe(10,60032,samples_before=60000)
    clock=SampleClock(3000000,milestones=(500000,1000000),samples_consumed=149984)
    assert clock.max_next_samples(32)==32
    clock.advance(32)
    assert clock.samples_consumed==150016
    assert clip.threshold==281.7
    assert clip.observe(20,150016,samples_before=149984)
    assert clip.threshold==pytest.approx(19.9)
    assert clip.fitted_summary()['observed_updates']==2
    assert clip.fitted_summary()['effective_freeze_samples']==150016
    assert not clip.observe(1e10,150048,samples_before=150016)
    assert clip.threshold==pytest.approx(19.9)


def test_fixed_window_and_partial_norm_history_resume_independent_of_budget():
    short=GroupClipCalibration(POLICY,3000000)
    long=GroupClipCalibration(POLICY,9000000)
    assert short.calibration_samples==long.calibration_samples==150000
    short.observe(40,90016,samples_before=89984)
    long.load_state_dict(short.state_dict())
    long.observe(80,150016,samples_before=149984)
    assert long.threshold==pytest.approx(79.6)
    final=GroupClipCalibration(POLICY,9000000)
    final.load_state_dict(long.state_dict())
    assert final.threshold==long.threshold and final.fitted


@pytest.mark.parametrize('budget',[3000000,9000000])
def test_each_budget_has_its_own_two_percent_warmup_and_zero_endpoint(budget):
    assert sample_lr_ratio(int(budget*.02),budget,'cosine')==1
    assert sample_lr_ratio(budget,budget,'cosine')==0


def test_confirmation_producer_uses_three_times_screening_budget(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('p_fixed_confirmation_test',root/'tools/p_recipe/prepare_confirmation.py')
    tool=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    monkeypatch.setattr(tool,'R',tmp_path)
    monkeypatch.setattr(tool,'REPO',tmp_path)
    control=tmp_path/'runs/p_recipe_20261113'
    control.mkdir(parents=True)
    (control/'D6_metadata.json').write_text(json.dumps(dict(P_enabled=['p'],Pprime_enabled=['p'])))
    base=dict(output=str(tmp_path/'outputs/base'),lr=3e-4,batch_size=32,samples=3000000,
              screening_samples=3000000,activation_checkpointing=False,study_revision='fixed',
              normalizations='original20261107',clip_calibration=POLICY,
              checkpoint_policy='screen_final_confirmation_milestones',confirmation_checkpoint_interval=1000000)
    base_path=tmp_path/'base.json'
    base_path.write_text(json.dumps(base))
    state=dict(round=2,merged_components=[],adopted_winners=[],merge_base_components=[],
               component_evidence={},study_revision='fixed')
    plan=tool.prepare(state,base_configuration=base_path,study_directory=tmp_path/'study')
    assert plan['samples_per_run']==9000000 and len(plan['configurations'])==6
    for path in plan['configurations']:
        cfg=json.loads(Path(path).read_text())
        assert cfg['samples']==9000000
        assert cfg['checkpoint_samples']==list(range(1000000,9000001,1000000))
        assert cfg['batch_size']==cfg['microbatch_size']==32
        assert cfg['activation_checkpointing'] is False
        assert cfg['normalizations']=='original20261107'
        assert cfg['clip_calibration']==POLICY


def load_tool(name):
    root=Path(__file__).resolve().parents[2]
    import sys
    sys.path.insert(0,str(root/'tools/p_recipe'))
    spec=importlib.util.spec_from_file_location('fixed_'+name,root/'tools/p_recipe'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reused_baseline_keeps_actual_run_output_and_original_clip(tmp_path):
    tool=load_tool('reuse_baseline')
    source=dict(run='actual_G1',output=str(tmp_path/'actual'),samples=3000000,batch_size=32,
                lr=3e-4,activation_checkpointing=False,study_revision='legacy',
                clip_calibration=dict(fraction=.05,initial_clip=281.7,quantile=.99))
    path=tmp_path/'source.json';path.write_text(json.dumps(source))
    base=dict(reuse_baseline_configuration=str(path),screening_samples=3000000,
              study_revision='new',baseline_clip_exception='User-approved original G1 window')
    alias=tool.baseline_configuration(base)
    assert alias['run']==source['run'] and alias['output']==source['output']
    assert alias['clip_calibration']==source['clip_calibration']
    assert alias['study_revision']=='new' and alias['baseline_source_study_revision']=='legacy'
    assert json.loads(path.read_text())==source
    source['batch_size']=128;path.write_text(json.dumps(source))
    with pytest.raises(ValueError,match='user-approved'):
        tool.baseline_configuration(base)


def test_reused_baseline_cost_counts_once_in_current_screening_budget():
    tool=load_tool('collect_execution')
    reuse=dict(study_revision='new',round=1)
    records=[dict(stage='calibration',round=0,state='FAILED',elapsed_seconds=3600,screening_reuse_attribution=reuse),
             dict(stage='calibration',round=0,state='COMPLETED',elapsed_seconds=1800,screening_reuse_attribution=reuse),
             dict(stage='calibration',round=0,state='RUNNING',elapsed_seconds=100,screening_reuse_attribution=reuse)]
    hours,revisions=tool.completed_screening_hours(records)
    assert hours=={'1':1.5}
    assert revisions=={'new':{'1':1.5}}


def test_round2_dispatch_starts_B1_before_other_runs(tmp_path,monkeypatch):
    tool=load_tool('prepare_round')
    monkeypatch.setattr(tool,'R',tmp_path)
    monkeypatch.setattr(tool,'REPO',tmp_path)
    control=tmp_path/'runs/p_recipe_20261113';control.mkdir(parents=True)
    (control/'D4_gamma.json').write_text('{"gamma":0.1597693323500406}')
    base=dict(output=str(tmp_path/'out/base'),lr=3e-4,batch_size=32,samples=3000000,
              screening_samples=3000000,study_revision='new',
              checkpoint_policy='screen_final_confirmation_milestones',
              screening_checkpoint_interval=1000000,initial_checkpoint_samples=32)
    path=tmp_path/'base.json';path.write_text(json.dumps(base))
    plan=tool.prepare(2,dict(merged_components=[],study_revision='new'),
                      base_configuration=path,study_directory=tmp_path/'study')
    assert json.loads(Path(plan['configurations'][0]).read_text())['arm']=='B1'
    for config_path in plan['configurations']:
        cfg=json.loads(Path(config_path).read_text())
        assert cfg['checkpoint_samples']==[32,1000000,2000000,3000000]
        assert cfg['batch_size']==cfg['microbatch_size']==32


@pytest.mark.parametrize('winner,lr',[('C1',6e-4),('C2',1.5e-4)])
def test_adopted_lr_reaches_M3_confirmations_and_T3_remains_M2(tmp_path,monkeypatch,winner,lr):
    tool=load_tool('prepare_confirmation')
    monkeypatch.setattr(tool,'R',tmp_path);monkeypatch.setattr(tool,'REPO',tmp_path)
    control=tmp_path/'runs/p_recipe_20261113';control.mkdir(parents=True)
    (control/'D6_metadata.json').write_text(json.dumps(dict(P_enabled=['p'],Pprime_enabled=['p'])))
    base=dict(output=str(tmp_path/'out/base'),lr=3e-4,batch_size=32,samples=3000000,
              screening_samples=3000000,study_revision='new')
    path=tmp_path/'base.json';path.write_text(json.dumps(base))
    state=dict(round=3,merged_components=['B1',winner],adopted_winners=[winner],
               merge_base_components=['B1'],component_evidence={},study_revision='new',merge_rollback=False)
    plan=tool.prepare(state,base_configuration=path,study_directory=tmp_path/'study')
    configs={json.loads(Path(p).read_text())['arm']:json.loads(Path(p).read_text()) for p in plan['configurations']}
    assert configs['T3']['components']==['B1']
    for arm in ('T2','T4','T5','T6'):assert configs[arm]['lr']==lr
    for arm in ('T1','T3'):assert configs[arm]['lr']==3e-4
