"""Explicit model-side grid TRAIN consumer; supplies no data-release schema."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

from .v3_contract import canonical_hash, require
from .v3_sampling import ConformationSelection
from .v3_sample_budget_events import binding, read_bound, write_once

MODE = 'authoritative_grid_train'
SCOPE = 'grid_cell'
SCHEMA = 'model_v3_grid_TRAIN_consumption_v1'


def validate_grid_contract(configuration, *, verify_release=True):
    """A pinned final-data hook verifies subset/source authority, never a FULL word.

    This is a MODEL consumption projection, not an invented D6 physical format.
    The original scientific proxy and full-TRAIN contracts are unchanged.
    """
    require(configuration.get('engineering_only') is False
        and configuration.get('experiment_scope') == 'GRID_CELL_TRAIN_PROPOSAL',
        'Grid TRAIN is an explicit scientific scope, never engineering acceptance')
    value = configuration.get('grid_train_contract')
    require(type(value) is dict and set(value) == {'schema', 'role', 'population_scope',
        'molecule_count', 'membership_sha256', 'base_TRAIN_membership_sha256',
        'release_evidence', 'geometry_source', 'selection', 'sample_budget', 'purpose'},
        'Complete versioned grid TRAIN consumer projection required')
    require(value['schema'] == SCHEMA and value['role'] == 'TRAIN'
        and value['population_scope'] == 'selected_frozen_TRAIN_subset'
        and value['purpose'] in ('grid_cell', 'handoff_smoke')
        and type(value['molecule_count']) is int and value['molecule_count'] > 0
        and type(value['sample_budget']) is int and value['sample_budget'] > 0,
        'Grid membership/count/purpose must be explicit TRAIN')
    import re
    for name in ('membership_sha256', 'base_TRAIN_membership_sha256'):
        require(type(value[name]) is str and re.fullmatch('[a-f0-9]{64}', value[name]),
            'Bound grid/base TRAIN membership SHA required')
    release = value['release_evidence']
    require(type(release) is dict and set(release) == {'path', 'bytes', 'sha256'},
        'Actual frozen base TRAIN release rawref required')
    if verify_release:
        require(binding(release['path']) == release, 'Grid base release raw bytes differ')
    require(value['geometry_source'] in ('PM7', 'Sprime_UFF'), 'Explicit supported grid geometry source required')
    selection = ConformationSelection(**value['selection'])
    require(asdict(selection) == value['selection'], 'Canonical existing conformation selection required')
    c = configuration['proxy_contract']
    require(c['sample_budget'] == value['sample_budget']
        and c['sampler'] == {'selection': value['selection'], 'geometry_source': value['geometry_source']},
        'Grid sampler/budget differs from its actual registered cell')
    if value['purpose'] == 'handoff_smoke':
        require(value['molecule_count'] == 120000 and value['sample_budget'] == 1000000
            and selection.mode in ('first_k', 'diversity_first_k') and selection.k == 2,
            'Guide handoff smoke requires actual120000 TRAIN molecules/k2/1000000 base draws')
    return value


def verify_grid_inputs(inputs, configuration):
    value = validate_grid_contract(configuration)
    require(inputs.index.role == 'TRAIN' and len(inputs.index) == value['molecule_count']
        and inputs.index.content_sha256 == value['membership_sha256'],
        'Actual grid TRAIN membership/count differs')
    require(inputs.grid_train_contract == value
        and inputs.authority_receipt.get('grid_TRAIN_consumption_contract_sha256') == canonical_hash(value)
        and inputs.authority_receipt.get('grid_subset_verified_against_base_TRAIN') is True,
        'Pinned final authority hook did not verify this exact base-TRAIN subset/grid contract')
    return value


def prepare_grid(base_request, grid_contract, *, adapter, input_projection, training_plan, output, base_request_ref):
    """Prepare metadata for later Root registration/admission; never bless a release.

    Numeric policies/model/recipe remain the explicitly supplied base. The final
    grid policy must additionally bind frozen_model/frozen_recipe rawrefs in its
    Git-registered policy; this preparer cannot freeze either artifact.
    """
    from .v3_proxy_run import identity, validate_sources
    from .v3_sample_budget_experiment import SampleBudgetPlan
    require(read_bound(base_request_ref) == base_request, 'Grid base request raw binding differs')
    validate_sources(base_request)
    root = __import__('pathlib').Path(output)
    require(not root.exists(), 'Fresh grid preparation directory required')
    configuration = deepcopy(read_bound(base_request['configuration']))
    require(configuration.get('engineering_only') is False, 'Scientific grid template required')
    configuration.update(experiment_scope='GRID_CELL_TRAIN_PROPOSAL', grid_train_contract=deepcopy(grid_contract))
    c = configuration['proxy_contract']
    c['sample_budget'] = grid_contract['sample_budget']
    c['sampler'] = {'selection': deepcopy(grid_contract['selection']), 'geometry_source': grid_contract['geometry_source']}
    require(type(training_plan) is dict and set(training_plan) == {'sample_plan', 'milestones', 'schedule'},
        'Explicit complete grid sample/validation/checkpoint/schedule plan required')
    plan_data = deepcopy(training_plan['sample_plan'])
    plan = SampleBudgetPlan(**{**plan_data, **{key: tuple(plan_data[key])
        for key in ('panel_samples', 'validation_samples', 'validation_roles')}})
    require(plan.sample_budget == c['sample_budget'], 'Grid plan differs from declared cell budget')
    c.update(sample_plan=plan_data, milestones=deepcopy(training_plan['milestones']),
        schedule=deepcopy(training_plan['schedule']))
    configuration['input_projection_sha256'] = canonical_hash(input_projection)
    validate_grid_contract(configuration)
    require(binding(adapter['path']) == adapter, 'Pinned grid final-data adapter source differs')
    root.mkdir(parents=True)
    cfg = write_once(root/'configuration.json', configuration)
    request = deepcopy(base_request)
    request.update(mode=MODE, scope=SCOPE, configuration=cfg, adapter=adapter,
        input_projection=deepcopy(input_projection), registrations={})
    request.pop('Root_admission', None)
    require('long_run_policy' not in configuration or type(request.get('long_run')) is dict,
        'Grid long run must retain a finite explicit storage admission')
    request_ref = write_once(root/'request.UNADMITTED.json', request)
    candidate = {'schema': 'model_v3_grid_preparation_v1', 'status': 'AWAITING_GRID_REGISTRATION_AND_ROOT_ADMISSION',
        'request': request_ref, 'configuration_identity_sha256': identity(configuration),
        'base_request': base_request_ref, 'data_authority_granted_by_preparer': False,
        'scientific_acceptance': False}
    return write_once(root/'GRID_PREPARATION.json', candidate)
