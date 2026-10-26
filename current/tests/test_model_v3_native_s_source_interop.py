"""Real read-only native source contract, distinct from synthetic training tests.

Root sets MODEL_V3_REQUIRE_NATIVE_S_INTEROP=1 in the dedicated CPU request.
Public environments without the original corpus get an explicit opt-in skip.
"""
from dataclasses import asdict
import json
import os

import pytest
import torch

from phychem_mfm.phase1.v3_native_s_precision_data import ExistingNativeSInputs, SCOPE, VAL_ROLE
from phychem_mfm.phase1.full_corpus_loader import collate_native_views


@pytest.mark.skipif(os.environ.get('MODEL_V3_REQUIRE_NATIVE_S_INTEROP') != '1',
                    reason='actual native corpus test requires explicit Root data admission')
def test_actual_native_TRAIN_and_fixed_PRETRAIN_VAL_reader_bridge_and_close(tmp_path):
    source = ExistingNativeSInputs(seed=0, workers=2)
    try:
        assert source.scope == SCOPE and source.read_only and source.node_local is False
        assert source.disjoint_receipt['TRAIN_records_checked'] == 11104772
        assert source.bindings['validation_records'] == 1024
        assert source.bindings['validation_atoms'] == 55650
        assert source.bindings['TRAIN_UNSEEN_CONFORMATION'] == 'NOT_PROVIDED_D5'
        # Real native source I/O: one actual TRAIN and one frozen VAL member.
        indices = source.train.sampler._next(source.train.sampler._cursor)[0]
        train_index = indices[0]
        train_row = source.train.dataset[train_index]
        source.train.dataset.close()
        validation_index = source.validation_rows[0]['logical_index']
        validation_row = source.validation_dataset[validation_index]
        source.validation_dataset.close()
        train = source._prepared(collate_native_views([train_row]), source.train.index, role='TRAIN', seed=0)
        validation = source._prepared(collate_native_views([validation_row]), source.validation_index, role=VAL_ROLE, seed=0)
        for prepared in (train, validation):
            assert len(prepared.choices) == 1
            assert prepared.views.batch.x.dtype == torch.long
            assert prepared.views.batch.pos.dtype == torch.float32
            assert prepared.views.batch.num_graphs == 3
            assert hasattr(prepared.views.batch, 'rdkit_bond_index')
            assert hasattr(prepared.views.batch, 'rdkit_bond_order')
            assert source.train.committed_base_samples == 0
        # An actual uncommitted loader batch must not alter checkpoint cursor.
        cursor = source.sampler.state_dict()
        first = source.train.next()
        assert source.sampler.state_dict() == cursor
        source.sampler.load_state_dict(cursor)
        replay = source.train.next()
        assert first.logical_indices == replay.logical_indices and first.record_keys == replay.record_keys
        assert source.sampler.samples_consumed == 0
        (tmp_path / 'actual_native_reader_receipt.json').write_text(json.dumps({
            'scope': SCOPE, 'TRAIN_record_decodes_direct': 1, 'PRETRAIN_VAL_record_decodes_direct': 1,
            'frozen_validation_records_metadata_verified': 1024, 'frozen_validation_atoms': 55650,
            'full_TRAIN_disjointness': source.disjoint_receipt, 'optimizer_updates': 0,
            'actual_uncommitted_loader_batch_replayed': True, 'D5_authority': False,
            'node_local': False, 'source_data_version': source.data_version}, sort_keys=True) + '\n')
    finally:
        source.close()
    assert source.closed and source.train.last_cleanup['input_descriptors_closed']
