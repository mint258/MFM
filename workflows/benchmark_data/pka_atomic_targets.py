"""Project the closed, user-approved single-site proposal into formal atom targets."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from .pprime_tmpfs_queue import capacity
from .shared_access import completed_evidence

DEFINITION = 'AUTHOR_TABLE_S2_37_CATALOG_V1'
NAMESPACE = 'pKahub_atomic_single_site_v1:'
AUTHORITY = Path(__file__).resolve().parents[2]/'configs/benchmark_data/pKahub_atomic_definition_approved_20261121.json'


def validate_authority(authority):
    if (authority.get('schema') != 'PKAHUB_ATOMIC_SINGLE_SITE_DEFINITION_AUTHORITY_V1'
            or authority.get('definition_id') != DEFINITION or authority.get('approved') is not True
            or authority.get('authority_kind') != 'explicit_user_message_question_reply'
            or not authority.get('question_item_id') or not authority.get('user_reply')
            or authority.get('proposal_job') != 4536942 or authority.get('catalog_patterns') != 37):
        raise ValueError('Explicit approval of this closed site-definition proposal is required')


def promote_table(table, authority):
    validate_authority(authority)
    required = {'record_id', 'endpoint', 'target_value', 'benchmark_role', 'geometry_dataset',
                'geometry_record_id', 'source_atom_index', 'model_atom_index',
                'eligibility_status', 'definition_approved',
                'experimental_macro_reused_under_single_site_definition',
                'experimental_microscopic_annotation'}
    if not required.issubset(table.column_names) or 'macro_record_id' in table.column_names:
        raise ValueError('Input is not the closed atomic proposal schema')
    if table.schema.field('target_value').type != pa.float64():
        raise ValueError('Original F64 macro target type must be preserved')
    metadata = table.select(sorted(required - {'target_value'})).to_pylist()
    ids, sites, roles = [], [], Counter()
    for row in metadata:
        if (row['eligibility_status'] != 'PROPOSED_SOURCE_CATALOG_DEFINITION_NOT_FROZEN'
                or row['definition_approved'] is not False
                or row['experimental_macro_reused_under_single_site_definition'] is not True
                or row['experimental_microscopic_annotation'] is not False
                or row['endpoint'] not in {'atomic_pKa_acid', 'atomic_pKa_base'}
                or row['benchmark_role'] not in {'TRAIN_POOL', 'EXTERNAL_BLIND'}
                or not isinstance(row['record_id'], str) or not row['record_id']
                or any(type(row[k]) is not int or row[k] < 0 for k in ('model_atom_index', 'source_atom_index'))
                or not row['geometry_dataset'] or not row['geometry_record_id']):
            raise ValueError('Unapproved, ambiguous or unmapped atomic proposal row')
        ids.append(NAMESPACE + row['record_id'])
        sites.append('atomic_site:v1:' + row['geometry_dataset'] + ':' + row['geometry_record_id']
                     + ':source_atom:' + str(row['source_atom_index']))
        roles[row['benchmark_role']] += 1
    if len(set(ids)) != len(ids):
        raise ValueError('Atomic target IDs must be unique across roles and endpoints')
    result = table.append_column('macro_record_id', table['record_id'])
    updates = {'record_id': pa.array(ids, type=pa.string()),
               'atom_site_id': pa.array(sites, type=pa.string()),
               'eligibility_status': pa.array(['APPROVED_SINGLE_SITE_ATOMIC_TARGET'] * len(ids)),
               'definition_approved': pa.array([True] * len(ids), type=pa.bool_()),
               'single_site_definition_id': pa.array([DEFINITION] * len(ids), type=pa.string())}
    for name, column in updates.items():
        if name in result.column_names:
            result = result.set_column(result.schema.get_field_index(name), name, column)
        else:
            result = result.append_column(name, column)
    return result, dict(roles)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--quota-snapshot', type=Path, required=True)
    parser.add_argument('--attempt', required=True)
    a = parser.parse_args()
    def safe():
        capacity(a.root, a.quota_snapshot, needed=256 * 1024**2)
    authority = json.loads(AUTHORITY.read_text()); validate_authority(authority)
    source = a.root/'directive19/pKahub/job_4536942/manifest.json'
    proposal = json.loads(source.read_text())
    if (proposal['status'] != 'SITE_DEFINITION_PROPOSAL_READY_NOT_TRAINING_LABELS'
            or proposal['single_site_definition_frozen'] or proposal['atomic_mechanism_ready']
            or proposal['source_catalog_patterns'] != 37):
        raise ValueError('Expected original closed, unfrozen 37-pattern proposal')
    native = completed_evidence(4536942)
    safe()
    table, counts = promote_table(pq.read_table(proposal['proposed_atomic_targets']), authority)
    expected = {role: proposal['counts'][role + ':PROPOSED_ATOMIC_ENDPOINTS']
                for role in ('TRAIN_POOL', 'EXTERNAL_BLIND')}
    if counts != expected:
        raise ValueError('Formal projection lost or added proposed endpoints')
    out = a.root/'directive19/pKahub'/a.attempt
    safe(); out.mkdir(exist_ok=False)
    paths = {}
    for role, key in (('TRAIN_POOL', 'training_targets'), ('EXTERNAL_BLIND', 'blind_targets')):
        safe()
        path = out/(key + '.parquet')
        pq.write_table(table.filter(pc.equal(table['benchmark_role'], role)), path, compression='zstd')
        paths[key] = str(path)
    manifest = dict(status='ATOMIC_SINGLE_SITE_TARGETS_READY', schema='PKAHUB_ATOMIC_SINGLE_SITE_TARGETS_V1',
        producer_job=os.environ['SLURM_JOB_ID'], source_proposal_manifest=str(source),
        source_proposal_native_closure=native, source_macro_manifest=proposal['source_macro_manifest'],
        site_evidence=proposal['evidence'], source_catalog=proposal['source_catalog'],
        source_catalog_reference=proposal['source_catalog_reference'], source_catalog_patterns=37,
        single_site_definition_frozen=True, atomic_mechanism_ready=True,
        user_definition_authority=authority, user_definition_authority_file=str(AUTHORITY),
        **paths, atomic_endpoints_by_role=counts, source_site_counts=proposal['counts'],
        record_namespace=NAMESPACE, macro_record_id_preserved=True,
        atom_indices='0-based; source_atom_index in original source atom order; model_atom_index in declared model_smiles',
        target_precision='Original Arrow F64 arrays retained; no numeric cast or recomputation',
        microscopic_experimental_records=0, experimental_macro_reused_under_single_site_definition=True,
        predicted_microspecies_used_as_experimental=False, multi_site_microscopic_assignment=False,
        unresolved_sites_excluded=True, all_molecular_macro_targets_unchanged=True,
        definition_caveat=proposal['definition_caveat'], chemistry_rescanned=False,
        new_QM_calls=0, new_geometries=0, original_data_deleted=False,
        new_content_hashes=False, independent_numeric_readback=False)
    safe(); (out/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print('PKA_ATOMIC_TARGETS_CLOSED', out/'manifest.json', counts, flush=True)


if __name__ == '__main__':
    main()
