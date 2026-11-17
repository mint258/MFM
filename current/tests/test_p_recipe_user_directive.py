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


def confirmation_fixture(tmp_path,monkeypatch):
    import json
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe/prepare_confirmation.py'
    spec=importlib.util.spec_from_file_location('directive_confirmation',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'REPO',tmp_path)
    monkeypatch.setattr(module,'R',tmp_path)
    monkeypatch.setattr(module,'OUT',tmp_path/'weights')
    directory=tmp_path/'configs/p_recipe';directory.mkdir(parents=True)
    policy=dict(confirmation=dict(perf_gpu_delivery_received=True,switch_proposal='configs/p_recipe/switches.json'))
    (directory/'user_directive_20261117.json').write_text(json.dumps(policy))
    base=dict(study_revision='fixed_20261115',batch_size=32,workers=14,
              activation_checkpointing=False,gradient_accumulation_steps=1,
              lr=3e-4,output=str(tmp_path/'weights/base'),samples=3000000,
              screening_samples=3000000,confirmation_checkpoint_interval=1000000,
              checkpoint_policy='screen_final_confirmation_milestones')
    proposal=dict(status='USER_CONFIRMED',user_confirmation=dict(message='Synthetic explicit approval'),
                  gpu_delivery='synthetic GPU delivery',recommendation=dict(
                      batch_size=32,workers=14,activation_checkpointing=False,
                      gradient_accumulation_steps=1,precision='FP32',TF32=False,
                      new_perf_switches=dict(S1=False,S2=False),S8_composed_new_switches=[]))
    proposal_path=directory/'switches.json';proposal_path.write_text(json.dumps(proposal))
    state=dict(round=3,study_revision='fixed_20261115',merged_components=[],adopted_winners=[],
               merge_base_components=[],component_evidence={},merge_rollback=False)
    return module,base,state,proposal,proposal_path


def test_confirmation_requires_user_choice_before_creating_configs(tmp_path,monkeypatch):
    import json
    import pytest
    module,base,state,proposal,path=confirmation_fixture(tmp_path,monkeypatch)
    proposal['status']='PENDING_USER_CONFIRMATION';path.write_text(json.dumps(proposal))
    base_path=tmp_path/'base.json';base_path.write_text(json.dumps(base))
    with pytest.raises(ValueError,match='explicit user switch confirmation'):
        module.prepare(state,base_configuration=base_path,study_directory=tmp_path/'study')
    assert not (tmp_path/'study').exists()


def test_confirmation_requires_round3_and_gpu_delivery(tmp_path,monkeypatch):
    import json
    import pytest
    module,base,state,proposal,path=confirmation_fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='round3'):
        module.approved_switch_snapshot(dict(state,round=2),base)
    policy=tmp_path/'configs/p_recipe/user_directive_20261117.json'
    value=json.loads(policy.read_text());value['confirmation']['perf_gpu_delivery_received']=False
    policy.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='perf GPU delivery'):
        module.approved_switch_snapshot(state,base)


def test_confirmation_freezes_approved_choice_in_all_six_configs(tmp_path,monkeypatch):
    import json
    module,base,state,proposal,path=confirmation_fixture(tmp_path,monkeypatch)
    control=tmp_path/'runs/p_recipe_20261113';control.mkdir(parents=True)
    (control/'D6_metadata.json').write_text(json.dumps(dict(P_enabled=['p'],Pprime_enabled=['p'])))
    base_path=tmp_path/'base.json';base_path.write_text(json.dumps(base))
    plan=module.prepare(state,base_configuration=base_path,study_directory=tmp_path/'study')
    assert len(plan['configurations'])==6 and plan['samples_per_run']==9000000
    proposal['recommendation']['workers']=20;path.write_text(json.dumps(proposal))
    for config in plan['configurations']:
        value=json.loads(Path(config).read_text())
        assert value['confirmation_switch_snapshot']==plan['confirmation_switch_snapshot']
        assert value['confirmation_switch_snapshot']['recommendation']['workers']==value['workers']==14
        assert value['confirmation_switch_snapshot']['frozen_for_entire_run'] is True


def test_confirmation_does_not_silently_adopt_unimplemented_switches(tmp_path,monkeypatch):
    import json
    import pytest
    module,base,state,proposal,path=confirmation_fixture(tmp_path,monkeypatch)
    proposal['recommendation']['new_perf_switches']['S1']=True;path.write_text(json.dumps(proposal))
    with pytest.raises(ValueError,match='not adopted'):
        module.approved_switch_snapshot(state,base)
