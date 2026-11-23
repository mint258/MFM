"""I1 deletion policy and exact own-budget source contracts, no real data."""
from copy import deepcopy
import pytest
from i1_decision_entry import recommendation,validate_native_sources

def primary(verdict,low,high,count=1,required=False):
 return dict(decision=dict(verdict=verdict,ci_lower=low,ci_upper=high),seed_count=count,seed1_required=required)

def test_WIN_only_requests_registered_confirmation_before_drop():
 assert recommendation(primary('win',.01,.05,required=True))==('WAITING_CONDITIONAL_SEED1',None)
 assert recommendation(primary('win',.01,.05,count=2))==('COMPLETE','DROP')
 with pytest.raises(ValueError):recommendation(primary('win',.01,.05))

def test_deletion_TIE_and_LOSS_are_not_addition_arm_rules():
 assert recommendation(primary('tie',-.01,.01))==('COMPLETE','DROP')
 assert recommendation(primary('tie',-.02,-.001))==('COMPLETE','RETAIN')
 assert recommendation(primary('loss',-.08,-.04))==('COMPLETE','RETAIN')
 assert recommendation(primary('tie',.001,.009))==('COMPLETE','RETAIN')

def test_sources_preserve_own_budget_and_only_B4_changes():
 norm='window2_TRAIN_normalization_parameters_20261107_v1'
 baseline=dict(arm='F2',samples=3000000,seed=0,p_recipe=dict(anti_collapse=True,element_residual=True,pma_pooling=True,gamma=.159769),normalizations=norm)
 candidate=deepcopy(baseline);candidate['arm']='I1';candidate['p_recipe']['anti_collapse']=False
 validate_native_sources(candidate,baseline,0)
 midpoint=deepcopy(baseline);midpoint['source_training_budget']=9000000
 with pytest.raises(ValueError):validate_native_sources(candidate,midpoint,0)
 changed=deepcopy(candidate);changed['p_recipe']['gamma']=.2
 with pytest.raises(ValueError):validate_native_sources(changed,baseline,0)
 changed=deepcopy(candidate);changed['normalizations']='new normalization'
 with pytest.raises(ValueError):validate_native_sources(changed,baseline,0)
