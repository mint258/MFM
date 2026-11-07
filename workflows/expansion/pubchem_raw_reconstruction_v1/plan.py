"""Freeze actual Main inventory locators after connection; no invented future pins."""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
from .support import BASELINE, N, canonical, load, need, reference, verify, write_new


def ast_sha(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def scientific_source_check():
    root = Path(__file__).parent
    contract = load(root / 'scientific_origin_contract.json')
    need(contract['schema'] == 'PUBCHEM_RECONSTRUCTION_FROZEN_SCIENCE_CONTRACT_V1' and contract['full_snapshot_rows'] == N, 'Original frozen science contract required')
    for row in contract['frozen_science_files']:
        actual = reference(root / row['relative_path'])
        need(all(actual[key] == row[key] for key in ('bytes', 'sha256')), 'Byte-identical frozen feature code required: ' + row['relative_path'])
    tree = ast.parse((root / 'kernel.py').read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name, expected in contract['kernel_function_original_AST_sha256'].items():
        node = functions[name]
        if name == 'chemical_task':
            relocations = [n for n in ast.walk(node) if isinstance(n, ast.ImportFrom) and n.module == 'science']
            need(len(relocations) == 1 and relocations[0].level == 1 and [(a.name, a.asname) for a in relocations[0].names] == [('features_legacy_compatible_v2', 'compatible')], 'Only the declared byte-identical science import relocation is allowed')
            relocations[0].module, relocations[0].level = None, 2
        need(ast_sha(node) == expected, 'Original four-function scientific AST differs: ' + name)
    constants = {target.id: node for node in tree.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}
    for name, expected in contract['kernel_constant_original_AST_sha256'].items():
        need(ast_sha(constants[name]) == expected, 'Original scientific field constants differ')
    facts = {node.name: node for node in ast.parse((root / 'facts.py').read_text()).body if isinstance(node, ast.FunctionDef)}
    for name, expected in contract['source_fact_original_AST_sha256'].items():
        need(ast_sha(facts[name]) == expected, 'Original source-row provenance AST differs: ' + name)
    return reference(root / 'scientific_origin_contract.json')


def prepare(inventory_path, acquisition_path, output, plan_path, *, workers, batch_rows, resource_parameters):
    allowed_resources = {'output_cap_bytes', 'software_rss_budget_bytes', 'minimum_node_available_bytes', 'minimum_free_bytes', 'other_future_reserved_bytes', 'quota_feed_path', 'quota_device', 'maximum_quota_observation_age_seconds', 'quota_snapshot', 'quota_authority', 'cpu21_authorization_reference'}
    need(set(resource_parameters) <= allowed_resources, 'Working resource JSON must not override scientific inputs or scope fields')
    inventory_ref, acquisition_ref = reference(inventory_path), reference(acquisition_path)
    inventory, acquisition = load(inventory_path), load(acquisition_path)
    need(inventory['schema'] == 'SB5_PUBCHEM_RAW_INVENTORY_RECEIPT_V2' and inventory['status'] == 'RAW_FULL_EOF_INVENTORY_COMPLETE_NO_CHEMICAL_SCREENING' and inventory['job_id'] == '4521093', 'Actual original Main full inventory required')
    need(inventory['raw_complete_SHA_verified'] is True and inventory['gzip_EOF_CRC_revalidated'] is True and inventory['counts']['records'] == N and inventory['counts']['cid_records'] == N and inventory['counts']['global_unique_cids_proven'] is True and inventory['counts']['strictly_increasing_cids'] is True and inventory['counts']['maximum_source_line_bytes'] == 3786, 'Original complete snapshot authority differs')
    need(acquisition['schema'] == 'pubchem_download_complete_v1' and acquisition['job_id'] == '4520348' and acquisition['file'] == inventory['raw_source'], 'Original acquisition/inventory raw snapshot pins must agree')
    index_ref = inventory['source_index']['reference']
    index_path = verify(index_ref)
    parts = [__import__('json').loads(line) for line in index_path.read_text().splitlines()]
    next_ordinal, total_bytes = 1, 0
    for index, part in enumerate(parts):
        need(set(part) == {'index', 'first_ordinal', 'last_ordinal', 'records', 'bytes', 'first_cid', 'last_cid', 'reference'} and part['index'] == index and part['first_ordinal'] == next_ordinal and part['last_ordinal'] == next_ordinal + part['records'] - 1 and part['bytes'] == part['reference']['bytes'], 'Original descriptor metadata sequence changed')
        need(part['reference']['path'] == str(index_path.parent / ('source_%06d.tsv' % index)), 'Actual original inventory part path differs')
        need(Path(part['reference']['path']).is_file() and Path(part['reference']['path']).stat().st_size == part['bytes'], 'Physical original raw part absent or size differs')
        next_ordinal = part['last_ordinal'] + 1
        total_bytes += part['bytes']
    need(len(parts) == inventory['source_index']['part_count'] == 500 and next_ordinal == N + 1 and total_bytes == inventory['counts']['uncompressed_bytes'] == 8880849781, 'All original500 raw descriptors must conserve')
    contract_ref = scientific_source_check()
    scope = {'schema': 'PUBCHEM_FULL_RAW_RECONSTRUCTION_SCIENTIFIC_SCOPE_V1', 'inventory_reference': inventory_ref, 'acquisition_reference': acquisition_ref, 'raw_reference': acquisition['file'], 'source_index_reference': index_ref, 'parts': parts, 'science_contract_sha256': contract_ref['sha256'], 'source_rows': N, 'source_version': acquisition['source_version'], 'recomputes_original_scope_not_narrow_pool': True}
    scope_sha = hashlib.sha256(canonical(scope)).hexdigest()
    plan = {'schema': 'PUBCHEM_FULL_RAW_RECONSTRUCTION_PLAN_V1', 'status': 'SOURCE_AND_METADATA_PREPARED_CPU_RAW_SHA_ADMISSION_PENDING', 'endpoint': '202.38.247.57:22', 'uid': 1278, 'scientific_scope': scope, 'scientific_scope_sha256': scope_sha, 'output_directory': str(Path(output).absolute()), 'workers': workers, 'batch_rows': batch_rows, 'old_baseline_counts': BASELINE, 'old_counts_match_forced': False, 'arbitrary_wall_or_retry_limit': False, **resource_parameters}
    need(type(workers) is int and workers >= 16 and type(batch_rows) is int and 1 <= batch_rows <= 4096, 'Actual CPU workers and bounded IPC batches required')
    for name in ('output_cap_bytes', 'software_rss_budget_bytes', 'minimum_node_available_bytes'):
        need(type(plan[name]) is int and plan[name] > 0, 'Actual Root-reviewed working resource values required')
    for name in ('minimum_free_bytes', 'other_future_reserved_bytes'):
        need(type(plan[name]) is int and plan[name] >= 0, 'Actual Root all-future storage reservation required')
    if 'quota_snapshot' in plan:
        need(plan['quota_snapshot'] and plan['quota_authority']['endpoint'] == '202.38.247.57:22' and plan['quota_authority']['uid'] == 1278, 'Root shared actual quota authority required')
        need(plan['quota_authority'].get('kind') == 'lustre' or plan['quota_authority'].get('filesystem'), 'Actual filesystem-specific quota authority required')
    else:
        need(plan['quota_feed_path'] and plan['quota_device'], 'Root live account quota feed required before production data work')
    return write_new(plan_path, plan)


def validate(plan):
    need(plan['schema'] == 'PUBCHEM_FULL_RAW_RECONSTRUCTION_PLAN_V1' and plan['endpoint'] == '202.38.247.57:22' and plan['uid'] == 1278 and plan['scientific_scope']['source_rows'] == N and len(plan['scientific_scope']['parts']) == 500, 'No narrowed fallback scope is permitted')
    need(hashlib.sha256(canonical(plan['scientific_scope'])).hexdigest() == plan['scientific_scope_sha256'], 'Immutable source scope seal differs')
    need(scientific_source_check()['sha256'] == plan['scientific_scope']['science_contract_sha256'], 'Scientific source contract changed')
    return plan
