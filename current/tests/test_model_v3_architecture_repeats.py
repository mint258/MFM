"""UNIT metadata/compiler checks; never real Data or a scientific top-two claim."""
from copy import deepcopy
from dataclasses import asdict, replace
import json

import pytest

from phychem_mfm.phase1 import v3_architecture_repeats as repeats
from phychem_mfm.phase1.v3_architecture_readiness import compile_trial
from phychem_mfm.phase1.v3_sample_budget_events import read_bound, write_once
from test_model_v3_architecture_readiness import registry, setup
from test_model_v3_architecture_cli import cli, case, invoke


@pytest.fixture
def repeat_case(setup, tmp_path):
    request, template, policy, trials, resolutions, base_ref = setup
    chosen = (trials[0], trials[2])
    names = [t.name for t in chosen]
    configs = {t.name: compile_trial(t, template, resolutions, policy, registry=registry()) for t in chosen}
    # Only a parser/compiler fixture. inspect_run will reject these UNIT entries;
    # no Data authority or real accounting/provider is mocked into acceptance.
    selection = {'schema': repeats.SELECTION_SCHEMA, 'status': repeats.SELECTION_STATUS,
        'authority': repeats.SELECTION_AUTHORITY, 'policy_sha256': policy.sha256,
        'selected_names': names, 'first_seed_runs': {n: {'UNIT_NOT_AN_ACTUAL_RUN': True} for n in names},
        'panel': {'path': '/UNIT/not_opened', 'sha256': '1' * 64},
        'panel_preregistration_commit': 'a' * 40}
    ref = write_once(tmp_path / 'UNIT_selection_not_scientific_authority.json', selection)
    return dict(request=request, template=template, policy=policy, trials=chosen,
        resolutions=resolutions, base_ref=base_ref, names=names, configs=configs, selection=selection, ref=ref)


def compile_case(c, **changes):
    args = dict(first_seed_trials=c['trials'], selected_name=c['names'][0], template=c['template'],
        resolutions=c['resolutions'], policy=c['policy'], registry=registry(),
        selection_reference=c['ref'], selected_names=c['names'], first_seed_configurations=c['configs'])
    args.update(changes)
    return repeats.compile_repeat(**args)


def test_repeat_changes_only_seed_and_reuses_original_identity_without_mutating_inputs(repeat_case):
    c = repeat_case; before = deepcopy((c['template'], c['configs']))
    for name in c['names']:
        out, record = compile_case(c, selected_name=name)
        original = deepcopy(c['configs'][name]); original['seed'] = 1
        assert out == original and out['seed'] == 1
        trial = next(t for t in c['trials'] if t.name == name)
        assert record['planned_scientific_identity_sha256'] == trial.scientific_identity
        assert record['trial']['name'] == name + '_seed1'
        assert record['trial']['pretraining_seed'] == 1
        assert record['only_configuration_seed_changed'] is True
        assert record['future_actual_run_or_seed_SD_claimed'] is False
    assert (c['template'], c['configs']) == before


@pytest.mark.parametrize('fault', ('unknown_selected', 'duplicate_selected', 'missing_selected'))
def test_selected_names_must_be_exactly_the_closed_pair(repeat_case, fault):
    c = repeat_case
    changes = {'selected_name': 'unknown'} if fault == 'unknown_selected' else {
        'selected_names': [c['names'][0]] * (2 if fault == 'duplicate_selected' else 1)}
    with pytest.raises(ValueError): compile_case(c, **changes)


@pytest.mark.parametrize('fault', ('already_seed1', 'unknown_trial', 'extra_parameter', 'wrong_budget', 'duplicate_trial'))
def test_only_original20_seed0_trials_can_repeat(repeat_case, fault):
    c = repeat_case; trials = list(c['trials']); first = trials[0]
    if fault == 'already_seed1': trials[0] = replace(first, pretraining_seed=1)
    elif fault == 'unknown_trial': trials[0] = replace(first, name='not_original20')
    elif fault == 'extra_parameter': trials[0] = replace(first, parameters=tuple(sorted(first.parameters + (('unregistered', True),))))
    elif fault == 'wrong_budget': trials[0] = replace(first, sample_budget=first.sample_budget + 1)
    else: trials[1] = trials[0]
    with pytest.raises(ValueError): compile_case(c, first_seed_trials=trials)


@pytest.mark.parametrize('fault', ('changed_head', 'changed_lr', 'changed_seed'))
def test_closed_original_configuration_cannot_be_relabelled_as_another_trial(repeat_case, fault):
    c = repeat_case; cfgs = deepcopy(c['configs']); cfg = cfgs[c['names'][0]]
    if fault == 'changed_head': cfg['proxy_contract']['heads']['forms'] = 'H3'
    elif fault == 'changed_lr': cfg['proxy_contract']['optimizer']['lr'] = .001
    else: cfg['seed'] = 1
    with pytest.raises(ValueError, match='Closed first-seed configuration'):
        compile_case(c, first_seed_configurations=cfgs)


@pytest.mark.parametrize('status', ('PENDING', 'FAILED', 'RULE_PROPOSAL', None))
def test_no_actual_closed_explicit_ranking_means_no_repeat(repeat_case, tmp_path, status):
    c = repeat_case; doc = deepcopy(c['selection']); doc['status'] = status
    ref = write_once(tmp_path / 'UNIT_pending_selection.json', doc)
    with pytest.raises(ValueError, match='closed explicit top-two'):
        repeats.selection_document(ref, c['policy'])


@pytest.mark.parametrize('fault', ('duplicate_names', 'missing_run', 'wrong_policy'))
def test_selection_header_rejects_incomplete_or_rebound_inputs(repeat_case, tmp_path, fault):
    c = repeat_case; doc = deepcopy(c['selection'])
    if fault == 'duplicate_names': doc['selected_names'] = [c['names'][0]] * 2
    elif fault == 'missing_run': doc['first_seed_runs'].pop(c['names'][1])
    else: doc['policy_sha256'] = '2' * 64
    ref = write_once(tmp_path / 'UNIT_bad_selection.json', doc)
    with pytest.raises(ValueError): repeats.selection_document(ref, c['policy'])


def test_closed_header_does_not_skip_the_real_original_run_inspector(repeat_case):
    c = repeat_case
    doc = repeats.selection_document(c['ref'], c['policy'])
    with pytest.raises(ValueError, match='Complete bound run evidence'):
        repeats.inspect_first_seeds(doc, c['policy'])


def test_actual_prepare_keeps_original_D5_authority_gate_and_creates_nothing(repeat_case, tmp_path):
    c = repeat_case; output = tmp_path / 'not_admitted'
    with pytest.raises(ValueError, match='authoritative D5'):
        repeats.prepare_repeat(c['trials'], c['names'][0], c['request'], c['resolutions'], c['policy'], output,
            base_request_ref=c['base_ref'], selection_reference=c['ref'])
    assert not output.exists()


def repeat_transport(c):
    request, config, trials, resolutions, base_ref, policy, sha = c
    return {'policy': policy, 'policy_sha256': sha, 'base_request': base_ref,
        'first_seed_trials': json.loads(json.dumps([asdict(trials[0]), asdict(trials[2])])),
        'selected_name': trials[0].name,
        'selection': {'path': '/UNIT/not_opened', 'sha256': '3' * 64}}


def test_repeat_CLI_is_only_a_thin_dispatch_not_a_new_authority(case, cli, tmp_path, monkeypatch):
    called = []
    def UNIT_dispatch_only(*args, **kwargs):
        called.append((args, kwargs))
        return {'scope': 'UNIT_DISPATCH_ONLY_NO_DATA_OR_SELECTION_AUTHORITY'}
    monkeypatch.setattr(repeats, 'prepare_repeat', UNIT_dispatch_only)
    manifest = repeat_transport(case)
    result = invoke(cli, tmp_path, 'repeat', manifest)
    assert result['scope'] == 'UNIT_DISPATCH_ONLY_NO_DATA_OR_SELECTION_AUTHORITY'
    args, kwargs = called.pop()
    assert args[0] == manifest['first_seed_trials'] and args[1] == manifest['selected_name']
    assert args[2] == read_bound(manifest['base_request']) and args[3] == {}
    assert kwargs['base_request_ref'] == manifest['base_request']
    assert kwargs['selection_reference'] == manifest['selection']

def test_the_actual_metadata_writer_clears_old_admission_and_never_grants_run_authority(repeat_case, tmp_path):
    c = repeat_case; configuration, provenance = compile_case(c)
    base = deepcopy(c['request'])
    base.update(registrations={'UNIT_OLD': True}, Root_admission={'UNIT_OLD': True}, long_run={'UNIT_OLD': True})
    original = deepcopy(base); output = tmp_path / 'UNIT_nonadmitted_proposal'
    result_ref = repeats._write_repeat_proposal(configuration, provenance, base, c['resolutions'],
        c['policy'], output, base_request_ref=c['base_ref'], first_seed_run_sources=c['selection']['first_seed_runs'])
    result = read_bound(result_ref); request = read_bound(result['request'])
    assert result['status'] == 'CONFIG_CONCRETE_UNADMITTED' and result['no_scientific_acceptance_or_freeze'] is True
    assert read_bound(result['configuration']) == configuration and configuration['seed'] == 1
    assert request['registrations'] == {} and request['Root_admission'] is None and 'long_run' not in request
    assert request['architecture_preparation']['repeat'] == json.loads(json.dumps(provenance))
    assert request['architecture_preparation']['first_seed_run_sources'] == c['selection']['first_seed_runs']
    assert base == original
