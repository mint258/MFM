import numpy as np
import pytest
from phychem_mfm.phase1.p_recipe_seed_policy import second_seed_required,combined_seed_decision,fresh_seed1_configuration


def test_borderline_interval_and_seed_cap():
    # tau=.01: include0.5tau, exclude1.5tau; both directions matter.
    assert not second_seed_required(.004,0.)
    assert second_seed_required(.005,0.)
    assert second_seed_required(.014,0.)
    assert not second_seed_required(.015,0.)
    assert second_seed_required(0.,.005)
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
