"""Only the new scientific TRAIN eligibility change."""
import importlib.util
from pathlib import Path

def test_exclusion_is_whole_molecule_and_preserves_original_owner():
    path=Path(__file__).resolve().parents[2]/'tools/p_recipe/refit_d4.py'
    spec=importlib.util.spec_from_file_location('p_recipe_refit',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source={'molecule_id':'excluded','record_id':'first','fit_eligible':True}
    other=dict(source,record_id='second')
    for owner in (source,other):
        result=module.fitted_owner(owner,{'excluded'})
        assert result['fit_eligible'] is False
        assert result['record_id']==owner['record_id']
        assert owner['fit_eligible'] is True
    retained=dict(source,molecule_id='retained')
    assert module.fitted_owner(retained,{'excluded'}) is retained
