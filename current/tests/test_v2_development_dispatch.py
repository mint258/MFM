"""Preserve the existing scientific CLIs when dispatching follow-on trials."""
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location('development_dispatch',
    Path(__file__).resolve().parents[2] / 'tools/model_v3/v2_run_development.py')
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


def test_native_s_passes_the_original_index_recipe_and_seed_without_reinterpreting_them():
    configuration = dict(index_path='/original/S240k/records.parquet',
        output=str(dispatch.BASE/'S_C1_a_seed1'), distance_bias='C1-a', views='three',
        seed=1, samples=6000000, batch_size=32, microbatch_size=4, lr=.0003,
        schedule='cosine', clip=1., workers=14)
    argv = dispatch.command('native_s', configuration, '/trial.json', python='python')
    options = dict(zip(argv[4::2], argv[5::2]))
    assert options == {'--'+k.replace('_','-'):str(v) for k,v in configuration.items()}
    assert argv[:4] == ['python','-B','-u','tools/model_v3/v2_train_s.py']


def test_v31_passes_the_same_configuration_to_the_existing_trainer():
    configuration = dict(root='/published/D6', output=str(dispatch.BASE/'P_repeat'), seed=1)
    assert dispatch.command('v31',configuration,'/original.json',python='python') == [
        'python','-B','-u','tools/model_v3/v2_train_v31.py','--configuration','/original.json']


def test_dev_keeps_the_original_panel_and_optional_structural_validation():
    configuration = dict(checkpoint='/original/samples_6000000.pt',
        output=str(dispatch.BASE/'S_repeat/dev_eval'), validation_index='/original/validation.parquet')
    argv = dispatch.command('dev',configuration,'/trial.json',python='python')
    assert argv[3:] == ['tools/model_v3/v2_evaluate_s.py','--checkpoint',configuration['checkpoint'],
        '--output',configuration['output'],'--validation-index',configuration['validation_index']]
    assert '--store' not in argv


@pytest.mark.parametrize('mode,extra', [('v31',{}), ('native_s',{'index_path':'index','model':{}}),
    ('dev',{'checkpoint':'checkpoint','store':'other-store'}), ('unknown',{})])
def test_missing_published_root_or_unsupported_cli_options_are_rejected(mode,extra):
    with pytest.raises(ValueError):
        dispatch.command(mode,dict(output=str(dispatch.BASE/'trial'),**extra),'/trial.json')


@pytest.mark.parametrize('output', ['/tmp/trial', str(dispatch.BASE), str(dispatch.BASE/'../outside')])
def test_unregistered_filesystems_and_parent_output_cannot_be_selected(output):
    with pytest.raises(ValueError):
        dispatch.command('v31',dict(output=output,root='/published/D6'),'/trial.json')


def test_train_and_its_dev_outputs_share_one_registered_root():
    root = dispatch.BASE/'registered_trial'
    registry = dict(schema='MODEL_OUTPUT_BUDGET_V1', roots=[str(root)])
    dispatch.require_registered_output(root, registry)
    dispatch.require_registered_output(root/'dev_eval', registry)
    with pytest.raises(ValueError, match='Register'):
        dispatch.require_registered_output(dispatch.BASE/'another_trial',registry)


def test_registry_cannot_authorize_an_outside_or_parent_model_directory():
    for root in (str(dispatch.BASE), '/tmp/other', str(dispatch.BASE/'../outside')):
        with pytest.raises(ValueError):
            dispatch.require_registered_output(dispatch.BASE/'trial',
                dict(schema='MODEL_OUTPUT_BUDGET_V1', roots=[root]))


def test_paired_validation_keeps_full_routine_and_training_holdout_inputs_separate():
    configuration = dict(checkpoint='/closed/samples_6000000.pt',
        output=str(dispatch.BASE/'closed/validation/full_and_unseen.json'),
        unseen_root='/published/D6', train_root='/published/D6',
        unseen_subset='/frozen/ROUTINE.parquet', train_subset='/original/TRAIN240k.parquet',
        batch_size=16)
    argv = dispatch.command('validation', configuration, '/validation.json', python='python')
    assert argv == ['python','-B','-u','tools/model_v3/v2_validate_v31.py',
        '--checkpoint','/closed/samples_6000000.pt','--output',configuration['output'],
        '--unseen-root','/published/D6','--train-root','/published/D6',
        '--unseen-subset','/frozen/ROUTINE.parquet',
        '--train-subset','/original/TRAIN240k.parquet','--batch-size','16']


@pytest.mark.parametrize('extra', [
    {'unseen_split':'TEST'},
    {'normalizations':'/refit-on-validation'},
    {'checkpoint':None},
])
def test_paired_validation_cannot_read_test_or_override_frozen_normalization(extra):
    configuration = dict(checkpoint='/closed/samples_6000000.pt',
        output=str(dispatch.BASE/'closed/validation/result.json'))
    configuration.update(extra)
    with pytest.raises(ValueError):
        dispatch.command('validation', configuration, '/validation.json')
