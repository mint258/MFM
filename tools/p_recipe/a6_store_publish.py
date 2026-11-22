"""Original selected-store publisher with byte reuse of already closed native records.

Only the per-record input branch differs. New records use the original frozen
decoder and native packing; publication and cohort sealing follow the original.
"""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
from phychem_mfm.phase1.v3_dev_panel import ALLOWED_ROLES, canonical
from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
from phychem_mfm.phase1.v3_dev_store import TrainOnlyPackedStore
from phychem_mfm.phase1.v3_selected_training_store import (
    DATASETS, require, ordered_bounded_map, binding, write_json, units_for, encoded)
from a6_native_reuse import materialization_one

def publish_reusing_selected_store(plan, native, decode, *, output, request_ref, source_contracts, definitions,
                           protocol, reuse, workers=16, check=lambda: None, close_source=lambda: None):
    """Write a new native store in fixed source order; no inherited partials."""
    output = Path(output); require(output.is_dir() and not any(output.iterdir()), 'Fresh empty selected-store output required')
    path = output / 'records.bin'; rows, groups, proofs = [], [], []
    jobs = [(dataset, row) for dataset in DATASETS for row in plan['records'][dataset]]
    def one(job):
        return materialization_one(job, reuse, decode)
    with path.open('xb') as stream:
        stream.write(native.RECORD_MAGIC)
        for dataset, source, actual in ordered_bounded_map(one, jobs, workers=workers):
            check()
            require(actual['annotation_state'] != 'MALFORMED', 'Malformed source cannot publish a successful selected store')
            reused = actual.get('reused_metadata')
            raw = (actual['reused_frame'] if reused is not None else
                   native.record_bytes(actual['x'], actual['coordinates'], actual['targets'], actual['candidate'], actual['supervision']))
            row = {'dataset_id': dataset, 'member_index': source['member_index'], 'member_uid': source['member_uid'],
                'native_n_atoms': reused['native_n_atoms'] if reused is not None else len(actual['x']),
                'target_rows': reused['target_rows'] if reused is not None else len(actual['targets']),
                'tasks': plan['contracts'][dataset]['tasks'],
                'geometry_ready': reused['geometry_ready'] if reused is not None else actual['coordinates'] is not None,
                'offset': stream.tell(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            require(row['native_n_atoms'] == source['native_n_atoms'], 'Packed source native atom count changed')
            stream.write(raw); rows.append(row)
            groups.append({k: source[k] for k in ('member_index', 'member_uid', 'full_inchikey')} | {'dataset_id': dataset})
            proofs.append({'dataset_id': dataset, 'member_index': source['member_index'], 'selected_role': source['selected_role'],
                'original_member_row_sha256': source['original_member_row_sha256'], 'source_proof': actual['source_proof']})
        stream.flush(); os.fsync(stream.fileno())
    payload_ref = binding(path)
    index_ref = write_json(output / 'record_index.json', {'schema': 'model_v3_selected_TRAIN_native_index_v1', 'records': rows})
    proof_ref = write_json(output / 'source_proofs.json', {'records': proofs, 'selected_numeric_or_annotation_values_written': False})
    contracts = []
    for dataset in DATASETS:
        contract = deepcopy(plan['contracts'][dataset]); contract['source_contract_sha256'] = source_contracts[dataset]['sha256']
        contracts.append(contract)
    contract_ref = write_json(output / 'contracts.json', {'contracts': contracts})
    manifest = {'schema': 'model_v3_selected_TRAIN_store_manifest_v1', 'complete': True,
        'closure_scope': 'complete_for_selected_TRAIN', 'historical_full_store_claimed': False,
        'selection_request': request_ref, 'selection_sha256': canonical(plan), 'records_file': payload_ref,
        'record_index': index_ref, 'contracts': contract_ref, 'source_proofs': proof_ref,
        'source_contracts': source_contracts, 'records': len(rows), 'outer_target_records_decoded': 0,
        'new_geometry_or_chemical_identity_generated': False,
        'native_units': {dataset: units_for(definitions[dataset], protocol) for dataset in DATASETS}}
    manifest_raw = encoded(manifest)+b'\n'
    manifest_ref = {'path': str(output / 'selected_store_manifest.json'), 'bytes': len(manifest_raw),
                    'sha256': hashlib.sha256(manifest_raw).hexdigest()}
    document = {'schema': 'model_v3_training_role_store_v1', 'source_complete': True,
        'closure_scope': 'complete_for_selected_TRAIN', 'source_kind': 'new_model_side_frozen_source_TRAIN_materialization',
        'historical_full_store_claimed': False, 'targets_in_metadata': False, 'native_record_hashes_preserved': True,
        'native_record_hash_origin': 'new closed selected-TRAIN index; no historical failed partial used',
        'source_store_manifest_sha256': manifest_ref['sha256'],
        'data_version': 'selectedTRAIN-v1-'+request_ref['sha256'][:16]+'-'+manifest_ref['sha256'][:16],
        'records_file': payload_ref, 'records': rows, 'contracts': contracts, 'molecule_groups': groups,
        'selected_store_manifest': manifest_ref}
    # Validate a deliberately named pending projection before publishing any
    # complete source manifest or final consumable sidecar. Preserve it later.
    sidecar_ref = write_json(output / 'training_store.PENDING.json', document)
    store = TrainOnlyPackedStore(sidecar_ref['path'], sidecar_ref['sha256'])
    for dataset in DATASETS:
        selection = plan['cohorts'][dataset]
        view = GroupedTrainingView(store, dataset, selection['source_fold_id'], store.group_map,
            seed=selection['seed'], max_train_groups=selection['caps'][ALLOWED_ROLES[0]],
            max_validation_groups=selection['caps'][ALLOWED_ROLES[1]])
        require(all(list(view.view(role)) == [r['member_index'] for r in selection['roles'][role]] for role in ALLOWED_ROLES),
                'Published selected-store replay changes the sealed cohort')
    check(); close_source(); check()
    require(write_json(output / 'selected_store_manifest.json', manifest) == manifest_ref,
            'Final selected-store manifest bytes differ')
    sidecar_ref = write_json(output / 'training_store.json', document)
    return {'status': 'COMPLETE_FOR_SELECTED_TRAIN', 'training_store': sidecar_ref, 'manifest': manifest_ref,
            'records': len(rows), 'outer_target_records_decoded': 0, 'cohort_replay_exact': True}
