"""Known checkpoint envelopes bind actual source 512/384 encoders, without data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import torch

from phychem_mfm.factory import build_model
from phychem_mfm.phase1.v3_dev_panel import NativeGeometry, FrozenH0Cache, canonical
from phychem_mfm.phase1.v3_encoder_bridge import (EncoderBindingError, load_encoder_pair,
                                                source_model_configuration)


ROOT = Path(__file__).absolute().parents[2]


def binding(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes': path.stat().st_size}


def json_file(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
    return binding(path)


def checkpoint_file(path, value):
    torch.save(value, path)
    return binding(path)


def geometries():
    return (NativeGeometry('synthetic', 'member:0', 0,
        torch.tensor([[5], [0], [0]]), torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]),
        torch.tensor([2, 0, 1])), NativeGeometry('synthetic', 'member:1', 1,
        torch.tensor([[7], [0]]), torch.tensor([[0., 0., 0.], [0., 0., 1.]]), torch.tensor([1, 0])))


@pytest.fixture(scope='module')
def primary(tmp_path_factory):
    root = tmp_path_factory.mktemp('source_512_checkpoint')
    config = deepcopy(json.loads((ROOT / 'workflows/s_denoise/configs/A4_seed0_v3.json').read_text())['model'])
    config['backbone'].update(dim=512, layers=6, heads=8)
    config['expert']['heads'] = 8
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        model = build_model(config).eval()
    configuration = {'seed': 7, 'model': config}
    config_ref = json_file(root / 'original_configuration.json', configuration)
    payload = {'model': model.state_dict(), 'config_sha256': config_ref['sha256'],
               'scientific_stop': False, 'development_only': True}
    checkpoint_ref = checkpoint_file(root / 'source_S_synthetic.pt', payload)
    return root, model, configuration, config_ref, payload, checkpoint_ref


def load_primary(fixture, checkpoint_ref=None, configuration_ref=None, **kwargs):
    _, _, configuration, config_ref, _, original_checkpoint_ref = fixture
    return load_encoder_pair(checkpoint_ref or original_checkpoint_ref, configuration_ref or config_ref,
        architecture_sha256=canonical(source_model_configuration(configuration)), pretraining_seed=7, **kwargs)


def assert_native_h0(pair, expected, tmp_path):
    from torch_geometric.data import Batch, Data
    records = geometries()
    source_batch = Batch.from_data_list([Data(x=r.x, pos=r.pos) for r in records])
    with torch.no_grad():
        source_h0 = expected.encode_atoms(source_batch)
    cache = FrozenH0Cache(tmp_path / 'cache', repository_root=ROOT)
    rows, metadata = cache.get_or_compute(pair.candidate, records,
        architecture_sha256=pair.provenance['architecture_sha256'], membership_sha256='a'*64,
        execution_source={'loader': pair.provenance['loader_implementation'],
                          'checkpoint': pair.provenance['checkpoint']}, max_graphs=2)
    torch.testing.assert_close(torch.cat([r.h0 for r in rows]), source_h0, rtol=1e-5, atol=1e-6)
    assert all(torch.equal(row.source_atom_ids, source.source_atom_ids) for row, source in zip(rows, records))
    assert metadata['binding']['effective_runtime']['H0_output_dtype'] == 'torch.float32'
    assert pair.candidate.config_dict() == pair.random_reference.config_dict() == expected.config_dict()
    assert pair.provenance['checkpoint_encoder_state_sha256'] != pair.provenance['random_encoder_state_sha256']
    assert pair.provenance['downstream_target_records_read'] == 0


def test_actual_source_512_s_configuration_and_frozen_h0(primary, tmp_path):
    pair = load_primary(primary)
    assert pair.candidate.latent_dim == pair.random_reference.latent_dim == 512
    assert sum(p.numel() for p in pair.candidate.parameters()) == 22_352_859
    assert pair.provenance['pretraining_seed'] == 7 and pair.provenance['random_reference_seed'] == 20261025
    assert_native_h0(pair, primary[1], tmp_path)


def test_s_raw_configuration_mismatch_rejects_even_same_shape(primary, tmp_path):
    configuration = deepcopy(primary[2]); configuration['model']['backbone']['radius'] += .25
    ref = json_file(tmp_path / 'same_shape_changed_radius.json', configuration)
    with pytest.raises(EncoderBindingError, match='original configuration SHA differs'):
        load_encoder_pair(primary[5], ref,
            architecture_sha256=canonical(configuration['model']), pretraining_seed=7)
    with pytest.raises(EncoderBindingError, match='pretraining seed'):
        load_encoder_pair(primary[5], primary[3], architecture_sha256=canonical(primary[2]['model']), pretraining_seed=8)


def test_checkpoint_ownership_schema_and_dtype_are_strict(primary, tmp_path):
    bad_ref = {**primary[5], 'sha256': '0'*64}
    with pytest.raises(EncoderBindingError, match='Source file bytes differ'):
        load_primary(primary, bad_ref)
    unsupported = checkpoint_file(tmp_path / 'unsupported.pt', {'model_state': {}})
    with pytest.raises(EncoderBindingError, match='Unsupported checkpoint schema'):
        load_primary(primary, unsupported)
    state = dict(primary[4]['model']); key = next(k for k, v in state.items() if isinstance(v, torch.Tensor) and v.is_floating_point())
    state[key] = state[key].to(torch.float16)
    dtype_ref = checkpoint_file(tmp_path / 'different_dtype.pt', {**primary[4], 'model': state})
    with pytest.raises(EncoderBindingError, match='shape/dtype/finiteness'):
        load_primary(primary, dtype_ref)
    with pytest.raises(EncoderBindingError, match='state-key schema'):
        load_primary(primary, expected_state_key='model_state')


def test_generic_training_v1_keeps_original_semantics_and_state_key(primary, tmp_path):
    from phychem_mfm.training.checkpoint import semantic_config, contract_hash
    configuration = deepcopy(primary[2]['model']); configuration['training'] = {'seed': 7}
    semantics = semantic_config(configuration)
    payload = {'format_version': 1, 'model_state': primary[1].state_dict(),
        'model_config': primary[1].config_dict(), 'seed': 7,
        'semantic_config': semantics, 'semantic_config_sha256': contract_hash(semantics)}
    ref = checkpoint_file(tmp_path / 'generic.pt', payload)
    config_ref = json_file(tmp_path / 'generic_configuration.json', configuration)
    pair = load_primary(primary, ref, config_ref, expected_state_key='model_state')
    assert pair.provenance['checkpoint_schema'] == 'source_training_checkpoint_v1'
    changed = deepcopy(configuration); changed['training']['seed'] = 8
    changed_ref = json_file(tmp_path / 'changed_recipe.json', changed)
    with pytest.raises(EncoderBindingError, match='full training recipe differs'):
        load_primary(primary, ref, changed_ref)
    # Serialized model_config includes options that need not change tensor shapes.
    altered = deepcopy(payload['model_config']); altered['backbone_config']['radius'] += .25
    wrong = checkpoint_file(tmp_path / 'same_shape_model_config.pt', {**payload, 'model_config': altered})
    with pytest.raises(EncoderBindingError, match='same-shape semantic options'):
        load_primary(primary, wrong, config_ref)


def test_full_corpus_typed_envelope_is_checked_before_h0(primary, tmp_path):
    from phychem_mfm.phase1.formal_gate import canonical_sha256
    from phychem_mfm.phase1.downstream_training import checkpoint_content_sha256
    runtime_recipe = {'seed': 7, 'epochs': 1, 'description': 'synthetic metadata only'}
    payload = {'schema_version': 'phase1_full_corpus_checkpoint_v1', 'config': runtime_recipe,
        'config_sha256': canonical_sha256(runtime_recipe), 'model_config': primary[1].config_dict(),
        'model_state': primary[1].state_dict(), 'status': 'partial'}
    payload['checkpoint_content_sha256'] = checkpoint_content_sha256(payload)
    pair = load_primary(primary, checkpoint_file(tmp_path / 'full_corpus.pt', payload))
    assert pair.provenance['checkpoint_schema'] == 'source_full_corpus_typed_checkpoint'
    assert pair.provenance['source_checkpoint_status'] == 'partial'
    broken = {**payload, 'model_state': {}, 'checkpoint_content_sha256': '0'*64}
    with pytest.raises(EncoderBindingError, match='typed checkpoint seal differs'):
        load_primary(primary, checkpoint_file(tmp_path / 'broken_seal.pt', broken))
    stopped = checkpoint_file(tmp_path / 'stopped.pt', {**primary[4], 'model': {}, 'scientific_stop': True})
    with pytest.raises(EncoderBindingError, match='scientifically stopped'):
        load_primary(primary, stopped)


class UnsafeFixture:
    pass


def test_no_unsafe_pickle_fallback(primary, tmp_path):
    ref = checkpoint_file(tmp_path / 'requires_unsafe_global.pt', {'custom': UnsafeFixture()})
    with pytest.raises(EncoderBindingError, match='safe weights-only path'):
        load_primary(primary, ref)


@pytest.fixture(scope='module')
def historical(tmp_path_factory):
    root = tmp_path_factory.mktemp('source_B3_384_checkpoint')
    original = json.loads((ROOT / 'workflows/sprime_s/formal_s/B3_seed0_v2.json').read_text())
    # Synthetic weights/cursors retain the actual old architecture and source
    # helper. They are deliberately unrelated to real scientific results.
    configuration = {key: deepcopy(original[key]) for key in (
        'kind', 'variant', 'seed', 'epochs', 'model', 'memory_implementation_sha256')}
    configuration['train_records'] = 2
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0); model = build_model(configuration['model']).eval()
    config_ref = json_file(root / 'synthetic_B3.json', configuration)
    payload = {'model': model.state_dict(), 'config_sha256': config_ref['sha256'],
        'memory_implementation_sha256': configuration['memory_implementation_sha256'],
        'development_only': False, 'scientific_stop': False, 'consumed_records': 6, 'optimizer_updates': 5}
    checkpoint_ref = checkpoint_file(root / 'synthetic_B3.pt', payload)
    cursors = {'consumed_records': 6, 'optimizer_updates': 5, 'label': 'segment_final'}
    receipt_ref = json_file(root / 'synthetic_receipt.json', {**checkpoint_ref, **cursors})
    reference = json.loads((ROOT / 'configs/model_v3/historical_B3_H0_reference_v1.json').read_text())
    reference.update(configuration=config_ref, checkpoint={**checkpoint_ref, 'state_key': 'model'},
                     source_receipt=receipt_ref, observed_cursors=cursors)
    reference_ref = json_file(root / 'synthetic_reference.json', reference)
    return model, configuration, config_ref, payload, checkpoint_ref, reference_ref


def test_actual_source_384_b3_requires_physical_identity_and_matching_random(historical, tmp_path):
    model, configuration, config_ref, _, checkpoint_ref, reference_ref = historical
    kwargs = dict(architecture_sha256=canonical(configuration['model']), pretraining_seed=0,
                  reference_kind='historical_sanity_only')
    with pytest.raises(EncoderBindingError, match='frozen physical reference'):
        load_encoder_pair(checkpoint_ref, config_ref, **kwargs)
    pair = load_encoder_pair(checkpoint_ref, config_ref, historical_reference=reference_ref, **kwargs)
    assert pair.candidate.latent_dim == pair.random_reference.latent_dim == 384
    assert sum(p.numel() for p in pair.candidate.parameters()) == 10_216_035
    assert pair.candidate.s_memory_implementation == pair.random_reference.s_memory_implementation
    assert pair.candidate.s_memory_implementation['pair_rows'] == 65536
    assert_native_h0(pair, model, tmp_path)
    wrong_reference = json.loads(Path(reference_ref['path']).read_text())
    wrong_reference['configuration']['sha256'] = '0'*64
    wrong_ref = json_file(tmp_path / 'wrong_reference.json', wrong_reference)
    with pytest.raises(EncoderBindingError, match='frozen physical reference'):
        load_encoder_pair(checkpoint_ref, config_ref, historical_reference=wrong_ref, **kwargs)


def test_real_b3_receipt_is_a_source_reference_without_loading_real_weights():
    reference = json.loads((ROOT / 'configs/model_v3/historical_B3_H0_reference_v1.json').read_text())
    receipt_path = ROOT / reference['source_receipt']['path']
    assert binding(receipt_path)['sha256'] == reference['source_receipt']['sha256']
    receipt = json.loads(receipt_path.read_text())
    assert receipt['sha256'] == reference['checkpoint']['sha256'] == 'f4a67719950277341017ae8f492ad65f721761a5523390ab97a654945a74c322'
    assert receipt['consumed_records'] == 33_314_316 and receipt['optimizer_updates'] == 81_751
    config_ref = binding(ROOT / reference['configuration']['repository_path'])
    assert config_ref['sha256'] == reference['configuration']['sha256'] == '64f1e0a85f81b774d4a00cd4728766143662e196d9d8e5189550b69ad8bfed1f'
    assert reference['status'] == 'SOURCE_RECEIPT_AND_CONFIGURATION_PINNED_WEIGHTS_NOT_YET_RELOADED'
