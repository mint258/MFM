import numpy as np
import pytest
from phychem_mfm.phase1.p_recipe_seed_policy import second_seed_required,combined_seed_decision,fresh_seed1_configuration


def test_seed0_win_only_and_confirmation_never_adds_seeds():
    assert not second_seed_required(.005,0.,.001)
    assert not second_seed_required(.04,0.,-.001)
    assert second_seed_required(.04,0.,.001)
    assert not second_seed_required(0.,.04,.001)
    assert second_seed_required(0.,.04,-.05,training_failure=True)
    assert not second_seed_required(.04,0.,.001,confirmation=True)
    assert not second_seed_required(.04,0.,.001,confirmation=True,training_failure=True)
    with pytest.raises(ValueError,match='no third seed'):
        combined_seed_decision({0:None,1:None,2:None})


def test_two_seed_ci_keeps_opposing_training_seed_effects():
    # The pooled CI retains the disagreement between training seeds.
    b=np.full(1000,.4)
    result=combined_seed_decision({0:(.44,.4,b+.04,b),1:(.38,.4,b-.02,b)})
    assert result['decision']['delta']==pytest.approx(.01)
    assert result['decision']['ci_lower']<0<result['decision']['ci_upper']
    assert result['decision']['verdict']=='tie'
    assert result['combined_bootstrap_draws']==2000
    assert result['seed1_required'] is False


def test_single_seed_point_and_original_paired_ci_are_preserved():
    b=np.linspace(.38,.42,1000)
    result=combined_seed_decision({0:(.43,.4,b+.03,b)})
    assert result['decision']['delta']==pytest.approx(.03)
    assert result['decision']['ci_lower']==pytest.approx(.03)
    assert result['decision']['verdict']=='win'
    # A seed0 win near the threshold still needs the registered second seed.
    assert result['seed1_required'] is True


def test_seed1_starts_fresh_and_keeps_parent_science():
    parent=dict(seed=0,run='C3_resumed',output='/outputs/C3_resumed',
                resume='/old/samples.pt',resume_samples=2000000,attempt=2,
                handoff_request='/control/old_request',source='PM7',samples=3000000,
                lr=.0003,batch_size=32,p_recipe={'element_residual':True},
                checkpoint_samples=[1000000,2000000,3000000])
    child=fresh_seed1_configuration(parent,output_root='/admitted/seed1')
    assert child['seed']==1 and child['output']=='/admitted/seed1/C3_resumed_seed1'
    assert not {'resume','resume_samples','attempt','handoff_request'}&child.keys()
    for key in ('source','samples','lr','batch_size','p_recipe','checkpoint_samples'):
        assert child[key]==parent[key]
    child['p_recipe']['element_residual']=False
    assert parent['p_recipe']['element_residual'] is True
    with pytest.raises(ValueError):fresh_seed1_configuration(child)


def test_frozen_confirmation_keeps_side_line_settings_and_own_budget():
    from pathlib import Path
    import runpy
    module=runpy.run_path(str(Path(__file__).resolve().parents[2]/'tools/p_recipe/prepare_confirmation.py'))
    build=module['confirmation_configuration']
    base=dict(output='/outputs/base',lr=.0003,batch_size=32,
              checkpoint_policy='screen_final_confirmation_milestones',confirmation_checkpoint_interval=1000000)
    frozen=dict(components=['A1','HEADS_T1'],p_recipe={'element_residual':True,'atom_attention_decoder':True},
                private_head_configuration={'selected_fields':['r68']},lr=.00015,head_form='H1',
                resume='/old/checkpoint.pt',samples=3000000,output='/old/frozen')
    c=build(base,set(frozen['components']),run='confirmation_T2',arm='T2',samples=9000000,frozen=frozen)
    assert c['p_recipe']==frozen['p_recipe'] and c['private_head_configuration']==frozen['private_head_configuration']
    assert c['lr']==.00015 and c['samples']==9000000 and c['seed']==0
    assert c['checkpoint_samples']==list(range(1000000,9000001,1000000))
    assert 'resume' not in c
    baseline=build(base,set(),run='confirmation_T1',arm='T1',samples=9000000,frozen=frozen)
    assert baseline['p_recipe']=={} and baseline['lr']==.0003
