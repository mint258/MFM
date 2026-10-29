"""Thin second-seed preparation; no ranking rule, training or data authority."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from .v3_architecture_readiness import compile_trial, resolve_inputs, _policy
from .v3_decision_evidence import bound_json, canonical, digest, inspect_run, require
from .v3_decision_rules import registered_policy
from .v3_proxy_plan import Evidence, PlannedTrial, second_seed
from .v3_recipe_readiness import _concrete
from .v3_sample_budget_events import write_once

SELECTION_SCHEMA = 'model_v3_architecture_second_seed_selection_v1'
SELECTION_STATUS = 'ROOT_CONFIRMED_CLOSED_TOP_TWO'
SELECTION_AUTHORITY = 'root_verified_stage5_closed_selection'


def _trial(value):
    if isinstance(value, PlannedTrial):
        return value
    require(type(value) is dict and set(value) == {'name', 'stage', 'condition',
        'pretraining_seed', 'sample_budget', 'parameters', 'requires'}
        and type(value['parameters']) is list and all(type(p) is list and len(p) == 2
            and type(p[0]) is str for p in value['parameters'])
        and type(value['requires']) is list and all(type(x) is str for x in value['requires']),
        'Original complete PlannedTrial transport required')
    return PlannedTrial(**{**value, 'parameters': tuple(tuple(p) for p in value['parameters']),
                           'requires': tuple(value['requires'])})


def selection_document(reference, policy):
    """A bound operator selection input, NOT an invented score/ranking certificate.

    Root supplies the original process's already CLOSED explicit two names and
    original run entries. This module neither ranks them nor invents a score/SD.
    Root's authorship/ranking correctness remains the original operator review;
    downstream data/registration/Root admission is never granted by this header.
    """
    value = bound_json(reference)
    require(type(value) is dict and set(value) == {'schema', 'status', 'authority',
        'policy_sha256', 'selected_names', 'first_seed_runs', 'panel',
        'panel_preregistration_commit'}, 'Complete bound second-seed selection input required')
    require(value['schema'] == SELECTION_SCHEMA and value['status'] == SELECTION_STATUS
        and value['authority'] == SELECTION_AUTHORITY and value['policy_sha256'] == policy.sha256,
        'Actual closed explicit top-two selection required; missing/pending ranking cannot prepare repeats')
    names = value['selected_names']
    require(type(names) is list and len(names) == 2 and all(type(n) is str and n for n in names)
        and len(set(names)) == 2 and type(value['first_seed_runs']) is dict
        and set(value['first_seed_runs']) == set(names), 'Exactly two distinct selected first-seed names/runs required')
    digest(value['panel_preregistration_commit'], 40)
    require(type(value['panel']) is dict and {'path', 'sha256'} <= set(value['panel']),
        'Original complete panel reference required')
    digest(value['panel']['sha256'])
    return value


def inspect_first_seeds(selection, policy):
    """Reuse the existing full panel/CP/C0/source inspector on actual CPU only."""
    p = _policy(policy)
    runs = {name: inspect_run(selection['first_seed_runs'][name],
        panel_reference=selection['panel'],
        preregistration_commit=selection['panel_preregistration_commit'])
        for name in selection['selected_names']}
    require(all(run.seed == 0 and run.checkpoint_samples == p['sample_budget']
        and run.training_start_epoch > policy.commit_epoch for run in runs.values()),
        'Closed actual seed0 at the original registered budget and policy time required')
    require(len({r.training_run_id for r in runs.values()}) == 2
        and len({r.checkpoint_sha256 for r in runs.values()}) == 2
        and len({r.panel_identity_sha256 for r in runs.values()}) == 1,
        'Distinct completed first-seed runs/checkpoints on one complete frozen panel required')
    configurations = {}
    for name, run in runs.items():
        evaluation_request = bound_json(run.sources['request'])
        configurations[name] = bound_json(evaluation_request['model_configuration'])
    return configurations


def compile_repeat(first_seed_trials, selected_name, template, resolutions, policy, *,
                   registry, selection_reference, selected_names, first_seed_configurations):
    """Pure configuration compiler; a UNIT invocation grants NO actual run authority.

    Production prepare_repeat always obtains configurations through inspect_run;
    it never accepts caller-supplied RunEvidence or a skip-validation switch.
    """
    require(type(first_seed_trials) in (list, tuple) and len(first_seed_trials) == 2,
        'Exactly the selected two original first-seed trials required')
    trials = tuple(_trial(t) for t in first_seed_trials)
    require(type(selected_names) is list and len(selected_names) == len(set(selected_names)) == 2
        and {t.name for t in trials} == set(selected_names)
        and len({t.name for t in trials}) == 2 and selected_name in selected_names,
        'Selected name must belong to the two closed original trials')
    require(type(first_seed_configurations) is dict and set(first_seed_configurations) == set(selected_names),
        'Complete inspected first-seed configurations required')
    for trial in trials:
        require(trial.stage == 5 and type(trial.pretraining_seed) is int and trial.pretraining_seed == 0,
            'A repeat must start from an original stage5 seed0 trial, never another repeat')
        expected = compile_trial(trial, template, resolutions, policy, registry=registry)
        require(canonical(expected) == canonical(first_seed_configurations[trial.name]),
            'Closed first-seed configuration differs from its original20 compiled trial')
    repeated = second_seed(trials, selected_names=selected_names,
        selection_evidence=Evidence(selection_reference['path'], selection_reference['sha256']))
    item = next(row for row in repeated if row['trial']['name'] == selected_name + '_seed1')
    repeat_trial = _trial({**item['trial'], 'parameters': [list(p) for p in item['trial']['parameters']],
                         'requires': list(item['trial']['requires'])})
    original = next(t for t in trials if t.name == selected_name)
    require(repeat_trial.pretraining_seed == 1 and repeat_trial.scientific_identity == original.scientific_identity,
        'The existing second_seed planned scientific identity must remain unchanged')
    configuration = deepcopy(first_seed_configurations[selected_name])
    require(configuration.get('seed') == 0, 'Inspected original configuration must have seed0')
    configuration['seed'] = repeat_trial.pretraining_seed
    before, after = deepcopy(first_seed_configurations[selected_name]), deepcopy(configuration)
    before.pop('seed'); after.pop('seed')
    require(canonical(before) == canonical(after), 'Repeat configuration may change only the top-level pretraining seed')
    return configuration, {'trial': asdict(repeat_trial),
        'first_seed_trial': asdict(original),
        'planned_scientific_identity_sha256': original.scientific_identity,
        'selection': deepcopy(selection_reference), 'only_configuration_seed_changed': True,
        'future_actual_run_or_seed_SD_claimed': False}


def prepare_repeat(first_seed_trials, selected_name, base_request, resolutions, policy, output, *,
                   base_request_ref, selection_reference):
    """Strict original D5 base + real closed first seeds -> fresh UNADMITTED repeat.

    The CPU evidence inspector can read the already saved safe checkpoint. No
    model is constructed and no score, repeat winner or real data is generated.
    """
    from .v3_proxy_run import bind_inputs, validate_request
    selection = selection_document(selection_reference, policy)
    require(bound_json(base_request_ref) == base_request and base_request.get('mode') == 'authoritative_proxy',
        'Actual bound authoritative D5 proxy base request required')
    require(policy.reference is not None
        and registered_policy(policy.reference, expected_sha256=policy.sha256) == policy,
        'Actual registered original policy required')
    template, _, _ = validate_request(base_request, input_kind='authoritative_proxy')
    actual = bind_inputs(base_request, template)
    try:
        require(actual.index.role == 'TRAIN' and len(actual.index) == 240000,
            'Original complete authoritative D5 240k TRAIN population required')
        registry = actual.registry
    finally:
        actual.provider.close()
    trials = tuple(_trial(t) for t in first_seed_trials)
    if any(name in trial.requires for trial in trials
           for name in ('C1_selection_closed', 'C3_selection_closed')):
        require(type(resolutions.get('inputs')) is dict
            and resolve_inputs(resolutions['inputs'], policy) == resolutions,
            'Repeat must retain the actually re-inspected original C1/C3 dependencies')
    configurations = inspect_first_seeds(selection, policy)
    configuration, provenance = compile_repeat(trials, selected_name, template, resolutions, policy,
        registry=registry, selection_reference=selection_reference,
        selected_names=selection['selected_names'], first_seed_configurations=configurations)
    return _write_repeat_proposal(configuration, provenance, base_request, resolutions, policy, output,
        base_request_ref=base_request_ref, first_seed_run_sources=selection['first_seed_runs'])


def _write_repeat_proposal(configuration, provenance, base_request, resolutions, policy, output, *,
                           base_request_ref, first_seed_run_sources):
    """Metadata writer only; directly calling it never grants Data/run authority."""
    from .v3_proxy_run import REPOSITORY, identity
    root = Path(output)
    require(not root.exists() and not root.resolve().is_relative_to(REPOSITORY.resolve()),
        'Fresh outside-Git repeat output required')
    _concrete(configuration)
    root.mkdir(parents=True)
    cfgref = write_once(root / 'configuration.json', configuration)
    request = deepcopy(base_request)
    request.update(configuration=cfgref, scope='comparison', registrations={}, Root_admission=None)
    request.pop('long_run', None)
    request['architecture_preparation'] = {
        'kind': 'SECOND_SEED_REPEAT', 'trial_name': provenance['trial']['name'],
        'planned_scientific_identity_sha256': provenance['planned_scientific_identity_sha256'],
        'resolved_configuration_identity_sha256': identity(configuration),
        'base_request': deepcopy(base_request_ref), 'resolution_inputs': resolutions.get('inputs'),
        'resolutions_sha256': canonical(resolutions), 'policy_sha256': policy.sha256,
        'policy_reference': deepcopy(policy.reference), 'repeat': provenance,
        'first_seed_run_sources': deepcopy(first_seed_run_sources), 'frozen': False}
    _concrete(request)
    reqref = write_once(root / 'request.UNADMITTED.json', request)
    return write_once(root / 'PREPARED.json', {
        'schema': 'model_v3_architecture_prepared_v1', 'status': 'CONFIG_CONCRETE_UNADMITTED',
        'configuration': cfgref, 'request': reqref, 'repeat_preparation': provenance,
        'required_gates': ['new seed1 registrations and explicit fresh Root admission',
            'original actual D1-D5/240k TRAIN/PM7/all roles and source/resource gates',
            'actual future training and complete frozen panel; no fabricated score or SD'],
        'no_scientific_acceptance_or_freeze': True})