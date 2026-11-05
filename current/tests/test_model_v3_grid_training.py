"""Model-side grid consumer metadata tests; supplies no frozen data authority."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from phychem_mfm.phase1.v3_contract import canonical_hash
from phychem_mfm.phase1.v3_grid_training import validate_grid_contract, verify_grid_inputs
from phychem_mfm.phase1.v3_sample_budget_events import write_once


@pytest.fixture
def grid_case(tmp_path):
    release = write_once(tmp_path/'synthetic_release_fixture.json', {'synthetic_metadata_only':True})
    value = {'schema':'model_v3_grid_TRAIN_consumption_v1','role':'TRAIN',
        'population_scope':'selected_frozen_TRAIN_subset','molecule_count':120000,
        'membership_sha256':'a'*64,'base_TRAIN_membership_sha256':'b'*64,'release_evidence':release,
        'geometry_source':'PM7','selection':{'mode':'first_k','k':2},'sample_budget':1000000,'purpose':'handoff_smoke'}
    cfg = {'engineering_only':False,'experiment_scope':'GRID_CELL_TRAIN_PROPOSAL','grid_train_contract':value,
        'proxy_contract':{'sample_budget':value['sample_budget'],'sampler':{'selection':value['selection'],'geometry_source':'PM7'}}}
    class Index:
        role = 'TRAIN'
        content_sha256 = 'a'*64
        def __len__(self): return 120000
    inputs = SimpleNamespace(index=Index(), grid_train_contract=deepcopy(value),
        authority_receipt={'grid_TRAIN_consumption_contract_sha256':canonical_hash(value),
            'grid_subset_verified_against_base_TRAIN':True})
    return cfg, inputs


def test_grid_consumes_exact_declared_subset_and_geometry(grid_case):
    cfg, inputs = grid_case
    assert validate_grid_contract(cfg) == cfg['grid_train_contract']
    assert verify_grid_inputs(inputs, cfg) == cfg['grid_train_contract']


@pytest.mark.parametrize('field,value', (('role','FULL'),('population_scope','entire_frozen_TRAIN'),
    ('molecule_count',True),('sample_budget',True),('membership_sha256','bad'),
    ('base_TRAIN_membership_sha256',None),('geometry_source','recomputed'),
    ('selection',{'mode':'first_k','k':1}),('purpose','final_training')))
def test_grid_never_turns_other_population_or_unregistered_policy_into_handoff(grid_case, field, value):
    cfg, _ = grid_case
    cfg['grid_train_contract'][field] = value
    with pytest.raises(ValueError):
        validate_grid_contract(cfg)


@pytest.mark.parametrize('field', ('grid_TRAIN_consumption_contract_sha256','grid_subset_verified_against_base_TRAIN'))
def test_grid_requires_actual_authority_hook_projection(grid_case, field):
    cfg, inputs = grid_case
    del inputs.authority_receipt[field]
    with pytest.raises(ValueError):
        verify_grid_inputs(inputs, cfg)


def test_grid_data_release_hash_drift_fails(grid_case):
    cfg, _ = grid_case
    cfg['grid_train_contract']['release_evidence']['sha256'] = 'f'*64
    with pytest.raises(ValueError):
        validate_grid_contract(cfg)


def test_grid_proxy_or_full_scope_cannot_alias_explicit_grid(grid_case):
    cfg, _ = grid_case
    cfg['experiment_scope'] = 'FULL_TRAIN_CONVERGENCE_PROPOSAL'
    with pytest.raises(ValueError):
        validate_grid_contract(cfg)
