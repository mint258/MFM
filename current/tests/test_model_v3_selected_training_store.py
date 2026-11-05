"""Independent metadata-first TRAIN selection and native source transport checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
from phychem_mfm.phase1.v3_dev_panel import canonical
from phychem_mfm.phase1.v3_selected_training_store import (ROOT, DATASETS, SelectedTrainingStoreError,
    binding, frozen_modules, OriginalMetadataStore, select_plan, FrozenSelectedDecoder,
    validate_selection_request, publish_selected_store, ordered_bounded_map)


def key(i):
    return chr(65+i)*14+'-ABCDEFGHIJ-A'


@pytest.fixture(scope='module')
def source_modules():
    sources = json.loads((ROOT / 'configs/model_v3/existing_downstream_sources_v1.json').read_text())
    return frozen_modules(sources)[:3]


@pytest.fixture
def synthetic(tmp_path, source_modules):
    native, decoder, graph = source_modules
    panel = json.loads((ROOT / 'configs/dev_panel_v1.json').read_text())
    panel['source_roles']['selection'].update(max_train_molecule_groups=4, max_inner_validation_molecule_groups=1)
    tasks = {d: [r['field'] for r in panel['tasks'] if r['dataset_id'] == d] for d in DATASETS}
    definitions = {d: {'tasks': [{'task_id': t, 'unit': 'synthetic'} for t in tasks[d]],
                       'output_level': 'atom' if d == 'cyp_isoform' else 'graph'} for d in DATASETS}
    members = {}; views = {}; refs = {}; expansion_rows = []
    for dataset, n in (('qm9', 24), ('cyp_isoform', 12), ('expansionrx', 20)):
        bucket = 'expansionrx_train' if dataset == 'expansionrx' else dataset
        members[bucket] = []
        for i in range(n):
            row = {'dataset': dataset, 'member_index': i, 'member_uid': f'{dataset}:{i}',
                'label_masks': 'NOT_MATERIALIZED', 'inchikey': None if dataset == 'expansionrx' else key(i if dataset == 'qm9' else i%6),
                'sample_id': str(i), 'fold': i%10,
                'source_frame': {'native_n_atoms': 2, 'path': str(tmp_path / f'native_{i}.xyz'), 'record_id': f'cyp:3A4.sdf:{i+1}'},
                'geometry_artifact_ref': {'native_n_atoms': 2, 'status': 'GEOMETRY_READY'}}
            if dataset == 'expansionrx':
                row['declared_role'] = 'train'; row['member_uid'] = 'expansionrx_train:'+str(i+1)
            members[bucket].append(row)
        fold = 'official' if dataset == 'expansionrx' else '0'
        for role in ('train', 'train_inner_validation'):
            ids = (list(range(n)) if role == 'train' else []) if dataset == 'expansionrx' else [i for i in range(n)
                if (i%10 not in (0, 1) if role == 'train' else i%10 == 1)]
            views[dataset, fold, role] = ids; refs[dataset, fold, role] = None
    # Only byte framing of this fixture is performed; no numeric conversion.
    from phychem_mfm.phase1.downstream_source_records import _csv_rows
    exp_path = tmp_path / 'official_TRAIN.csv'
    exp_path.write_text(','.join(['SMILES', 'Molecule Name', *tasks['expansionrx']])+'\n'+''.join(
        ','.join(['CO', f'Mol{i}', *['1.25']*len(tasks['expansionrx'])])+'\n' for i in range(20)))
    raw = exp_path.read_bytes(); ref = binding(exp_path); frames = list(_csv_rows(raw, with_spans=True))
    for i, (start, end, fields, spans) in enumerate(frames[1:]):
        row = members['expansionrx_train'][i]
        row['source_frame'] = {'source_file': ref, 'record_ordinal_1based': i+1, 'frame_start': start, 'frame_end': end,
            'raw_frame_sha256': hashlib.sha256(raw[start:end]).hexdigest(),
            'smiles_value_utf8_sha256': hashlib.sha256(fields[0]).hexdigest(), 'smiles_physical_span': spans[0],
            'source_name_utf8_sha256': hashlib.sha256(fields[1]).hexdigest()}
        expansion_rows.append(native.seal({'member_uid': row['member_uid'], 'declared_role': 'train',
            'source_member_index': i, 'member_row_sha256': native.canonical(row),
            'raw_frame_sha256': row['source_frame']['raw_frame_sha256'], 'target_fields_decoded': False,
            'full_inchikey': key(i%5), 'native_n_atoms': 2, 'status': 'GEOMETRY_READY',
            'native_x': [5, 0], 'native_coordinates_float64': [[0., 0., 0.], [1., 0., 0.]]}))
    qm_path = tmp_path / 'QM_assignment.csv'
    qm_path.write_text(','.join(['dataset', 'sample_id', 'fold', 'xyz_path', *tasks['qm9']])+'\n'+''.join(
        ','.join(['qm9', str(i), str(i%10), str(tmp_path / f'native_{i}.xyz'), *['DO_NOT_NUMERICALLY_DECODE']*len(tasks['qm9'])])+'\n'
        for i in range(24)))
    for row in members['qm9']:
        row['assignment_source'] = binding(qm_path)
    membership = SimpleNamespace(rows=members, views=views, view_refs=refs)
    expansion = native.seal({'complete': True, 'target_fields_decoded': False, 'records': expansion_rows})
    store = OriginalMetadataStore(membership, expansion, definitions, panel, native)
    plan = select_plan(store, panel, native)
    ctx = {'native': native, 'decoder': decoder, 'graph': graph, 'membership': membership, 'store': store,
           'definitions': definitions, 'protocol': {}, 'sources': {'budgets': {'workers': 2}}}
    return ctx, panel, expansion, plan


def test_selection_uses_original_roles_full_keys_and_group_caps_without_targets(synthetic):
    ctx, panel, _, plan = synthetic
    assert plan['target_values_decoded'] is False
    assert len(plan['records']['qm9']) == 5
    assert len(plan['records']['expansionrx']) == 20
    assert len({r['full_inchikey'] for r in plan['records']['expansionrx']}) == 5
    for dataset in DATASETS:
        cohorts = plan['cohorts'][dataset]['roles']
        assert {r['full_inchikey'] for r in cohorts['train']}.isdisjoint(r['full_inchikey'] for r in cohorts['train_inner_validation'])
        for row in plan['records'][dataset]:
            if dataset != 'expansionrx':
                assert row['original_member']['fold'] != 0
            assert row['original_member_row_sha256'] == ctx['native'].canonical(row['original_member'])
    assert plan['cohorts']['cyp_isoform']['purged_optimization_member_indices']
    with pytest.raises(SelectedTrainingStoreError, match='cannot get/decode'):
        ctx['store'].get('qm9', 1)
    with pytest.raises(SelectedTrainingStoreError, match='Outer roles'):
        ctx['store'].view('qm9', '0', role='final')


def test_expansion_train_identity_comes_from_its_sealed_native_geometry(synthetic):
    ctx, panel, expansion, _ = synthetic
    assert all(r['inchikey'] is None for r in ctx['membership'].rows['expansionrx_train'])
    altered = deepcopy(expansion); altered['records'][0]['full_inchikey'] = None
    altered['records'][0].pop('content_sha256'); ctx['native'].seal(altered['records'][0])
    altered.pop('content_sha256'); ctx['native'].seal(altered)
    with pytest.raises(SelectedTrainingStoreError, match='full source chemical identity'):
        OriginalMetadataStore(ctx['membership'], altered, ctx['definitions'], panel, ctx['native'])
    drift = deepcopy(expansion); drift['records'][0]['member_row_sha256'] = '0'*64
    drift['records'][0].pop('content_sha256'); ctx['native'].seal(drift['records'][0])
    drift.pop('content_sha256'); ctx['native'].seal(drift)
    with pytest.raises(SelectedTrainingStoreError, match='identity/native source join'):
        OriginalMetadataStore(ctx['membership'], drift, ctx['definitions'], panel, ctx['native'])


def test_request_mutation_and_new_native_members_reject_before_target_decode(synthetic):
    ctx, panel, _, plan = synthetic
    request = {'schema': 'model_v3_selected_train_materialization_request_v1', 'status': 'FROZEN_LABEL_FREE_SELECTION',
        'outer_target_decoding_permitted': False, 'failed_partial_reuse_permitted': False,
        'complete_for_selected_TRAIN_only': True, 'budgets': ctx['sources']['budgets'],
        'selection': deepcopy(plan), 'selection_sha256': canonical(plan)}
    assert validate_selection_request(ctx, request, panel) == plan
    request['selection']['records']['qm9'][0]['member_index'] = 999
    with pytest.raises(SelectedTrainingStoreError, match='Selection content SHA'):
        validate_selection_request(ctx, request, panel)
    request['selection_sha256'] = canonical(request['selection'])
    with pytest.raises(SelectedTrainingStoreError, match='selection changed before target decode'):
        validate_selection_request(ctx, request, panel)


def test_numeric_framing_is_opaque_and_only_authorized_native_targets_decode(synthetic):
    ctx, _, _, plan = synthetic
    calls = []; source = ctx['decoder']
    def observed(raw, pattern):
        calls.append(raw)
        return source.observed_scalar(raw, pattern)
    ctx = {**ctx, 'decoder': SimpleNamespace(observed_scalar=observed, NUMERIC_RECIPE=source.NUMERIC_RECIPE)}
    decoder = FrozenSelectedDecoder(ctx, plan)
    decoder.prepare_numeric_frames()
    assert not calls  # Excluded/nonselected QM rows contain invalid numeric tokens.
    selected = plan['records']['expansionrx'][0]
    result = decoder.decode('expansionrx', selected['member_index'], role=selected['selected_role'])
    assert result['targets'] == [[1.25]*3] and len(calls) == 3
    assert result['coordinates'] == [[0., 0., 0.], [1., 0., 0.]]
    before = len(calls)
    with pytest.raises(SelectedTrainingStoreError, match='allowlist'):
        decoder.decode('expansionrx', 999, role='train')
    with pytest.raises(SelectedTrainingStoreError, match='allowlist'):
        decoder.decode('qm9', 0, role='train')
    with pytest.raises(SelectedTrainingStoreError, match='allowlist'):
        decoder.decode('expansionrx', 1, role='final')
    with pytest.raises(SelectedTrainingStoreError, match='only once'):
        decoder.decode('expansionrx', selected['member_index'], role=selected['selected_role'])
    assert len(calls) == before


def publication_arguments(tmp_path, synthetic):
    ctx, _, _, plan = synthetic
    output = tmp_path / 'native_output'; output.mkdir()
    seen = []
    def decode(dataset, index, *, role):
        selected = next(row for row in plan['records'][dataset] if row['member_index'] == index)
        assert role == selected['selected_role']; seen.append((dataset, index, role))
        tasks = plan['contracts'][dataset]['tasks']; rows = 2 if dataset == 'cyp_isoform' else 1
        targets = [[float((index+i)%2)]*len(tasks) for i in range(rows)]
        masks = [[True]*len(tasks) for _ in range(rows)]
        targets[0][0] = float('nan'); masks[0][0] = False
        return {'x': (5, 0), 'coordinates': [[0., 0., 0.], [1., 0., 0.]], 'targets': targets,
            'candidate': [[True]*len(tasks) for _ in range(rows)], 'supervision': masks,
            'annotation_state': 'SYNTHETIC_SOURCE', 'source_proof': {'original': selected['original_member_row_sha256']}}
    return dict(plan=plan, native=ctx['native'], decode=decode, output=output,
        request_ref={'path': 'synthetic_request.json', 'sha256': 'a'*64},
        source_contracts={d: {'path': 'synthetic_metadata_contract.json', 'sha256': 'b'*64} for d in DATASETS},
        definitions=ctx['definitions'], protocol=ctx['protocol'], workers=2), seen


def test_new_train_store_closes_then_existing_reader_replays_identical_membership(tmp_path, synthetic):
    args, seen = publication_arguments(tmp_path, synthetic)
    result = publish_selected_store(**args)
    assert result['status'] == 'COMPLETE_FOR_SELECTED_TRAIN' and result['cohort_replay_exact']
    assert len(seen) == result['records'] == sum(len(rows) for rows in args['plan']['records'].values())
    assert [(d, i) for d, i, _ in seen] != []
    store_ref = result['training_store']; store = TrainOnlyPackedStore(store_ref['path'], store_ref['sha256'])
    manifest = json.loads(Path(result['manifest']['path']).read_text())
    assert manifest['closure_scope'] == 'complete_for_selected_TRAIN' and manifest['historical_full_store_claimed'] is False
    for dataset in DATASETS:
        row = args['plan']['records'][dataset][0]; sample = store.get(dataset, row['member_index'])
        assert sample.member_uid == row['member_uid'] and sample.source_atom_ids.tolist() == [0, 1]
        assert torch.isnan(sample.targets[0, 0]) and not sample.supervision_mask[0, 0] and sample.candidate_mask[0, 0]
    with pytest.raises(ValueError, match='outside'):
        store.get('qm9', 0)


def test_source_postcheck_failure_leaves_partial_without_complete_manifest(tmp_path, synthetic):
    args, _ = publication_arguments(tmp_path, synthetic)
    def fail():
        raise ValueError('synthetic source changed during decode')
    with pytest.raises(ValueError, match='source changed'):
        publish_selected_store(**args, close_source=fail)
    assert (args['output'] / 'records.bin').exists()
    assert (args['output'] / 'training_store.PENDING.json').exists()
    assert not (args['output'] / 'training_store.json').exists()
    assert not (args['output'] / 'selected_store_manifest.json').exists()


def test_bounded_parallel_writer_keeps_input_order_and_rejects_worker_overflow():
    assert list(ordered_bounded_map(lambda i: i*i, range(12), workers=3)) == [i*i for i in range(12)]
    with pytest.raises(SelectedTrainingStoreError):
        list(ordered_bounded_map(lambda i: i, [1], workers=17))
