"""Metadata-only exact original coverage preparation in the deployed Alpha code."""
import argparse
import os
from pathlib import Path
from ..alpha_runtime_v1.common import ENDPOINT, UID, load, need, reference, verify, write
from ..pubchem_closed500_bulk_v2.plan import load_coverage

ORIGINAL_ROOT = Path('/gfshome/alpha/codex_data_v1_20261026')
RAW_SHA = '2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7'
SCIENCE = {'common.py': '8c988f617776ad05354deae1cf69933e7ff95210f7a2609f903e4826172ccbad', 'screen.py': 'bb31d57a4749f9ef9843dc075bc75f7c268cb781f60c7b4f0d77a121a73dcc88', 'features_legacy_compatible_v2.py': '164a9e23d8ad0252c0bf728073064b9d3c845f48da9357a36decaebfc96da2ad', 'features_generic_candidate_v1.py': '7bbe49bb82a635269da7c1820ee8c4083b57c738576fd0f6927b45f5c67a0ad2'}


def original_science():
    refs = []
    for name, expected in SCIENCE.items():
        ref = reference(ORIGINAL_ROOT / 'code/pubchem_science_frozen_v1' / name)
        need(ref['sha256'] == expected, 'Original frozen Alpha scientific version changed: ' + name)
        refs.append(ref)
    return refs


def prepare(coverage_path, resources_path, plan_path, filter_bindings_path=None):
    need(os.getuid() == UID, 'Prepare against actual Alpha metadata under UID1264')
    coverage_ref = reference(coverage_path)
    fragments = load_coverage(coverage_ref)
    coverage = load(coverage_path)
    frozen = load(verify(coverage['frozen_manifest_reference']))
    need(frozen['schema'] == 'ALPHA_PUBCHEM_EXCLUSIVE_ORDINAL_MANIFEST_V1' and frozen['source_raw_sha256'] == RAW_SHA and frozen['population_N'] == 124857440, 'Exact original PubChem snapshot authority required')
    original_plan_ref = reference(ORIGINAL_ROOT / 'control/pubchem_closed500_materialization_root_20261030_v1/stage/plan.json')
    old_plan = load(original_plan_ref['path'])
    need(old_plan['schema'] == 'ALPHA_CLOSED500_MATERIALIZATION_PLAN_V1' and old_plan['coverage_reference'] == coverage_ref and old_plan['fragment_count'] == 502 and old_plan['source_rows'] == 124857440 and old_plan['fragments'] == fragments, 'Original materialization metadata must bind exactly these same502 typed fragments')
    kernel_manifest_ref = old_plan['science']['frozen_manifest_reference']; verify(kernel_manifest_ref)
    resources = load(resources_path)
    allowed = {'runtime_profile_reference', 'quota_snapshot', 'quota_authority', 'workers', 'software_rss_budget_bytes', 'minimum_node_available_bytes', 'output_scope_root', 'output_directory', 'output_cap_bytes', 'other_future_reserved_bytes', 'minimum_free_bytes', 'duckdb_memory_bytes', 'batch_rows'}
    need(set(resources) == allowed, 'Exact reviewed Alpha working resources required; no scientific overrides')
    need(resources['quota_authority']['endpoint'] == ENDPOINT and resources['quota_authority']['uid'] == UID and resources['workers'] >= 16 and 1 <= resources['batch_rows'] <= 65536, 'Real Alpha resource identity/bounded batch required')
    out = Path(resources['output_directory']); scope = Path(resources['output_scope_root'])
    old_names = ('pubchem_C_alpha_v1', 'pubchem_resource_phase_alpha_v2', 'pubchem_continuation_alpha_v3', 'pubchem_packed_day32_alpha_v1', 'pubchem_consumed_partial_tail_alpha_v2', 'pubchem_closed500_materialization_alpha_v1')
    need(out.is_relative_to(scope) and scope.is_relative_to(Path('/gfshome/alpha')) and all(not out.is_relative_to(ORIGINAL_ROOT / 'artifacts' / name) for name in old_names), 'New private namespace required; old scientific outputs/partialSQLite untouched')
    here = Path(__file__).parent
    sources = [*sorted(here.glob('*.py')), *sorted((here.parent / 'alpha_runtime_v1').glob('*.py')), *sorted((here.parent / 'pubchem_closed500_bulk_v2').glob('*.py'))]
    sources += sorted((here.parent / 'portable_sources_v1').glob('*.py'))
    contract = here / 'original_function_contract.json'
    if contract.exists():
        from .scientific_contract import verify as verify_science
        verify_science(); sources.append(contract)
    plan = {'schema': 'ALPHA_ORIGINAL502_TYPED_HANDOFF_PLAN_V1', 'status': 'SOURCE_METADATA_PREPARED_ALLOCATED_BODY_SHA_PENDING', 'endpoint': ENDPOINT, 'uid': UID, 'coverage_reference': coverage_ref, 'frozen_manifest_reference': coverage['frozen_manifest_reference'], 'original_science_references': original_science(), 'source_snapshot_sha256': RAW_SHA, 'logical_descriptor_count': 500, 'fragment_count': 502, 'source_rows': 124857440, 'fragments': fragments, 'source_counts': coverage['counts'], 'code_references': [reference(p) for p in sources], 'resources_reference': reference(resources_path), 'arbitrary_wall_or_retry_limit': False, 'no_chemistry_or_journal_replay': True, **resources}
    plan['original_materialization_plan_reference'] = original_plan_ref
    plan['original_frozen_kernel_manifest_reference'] = kernel_manifest_ref
    plan['old_partial_SQLite_is_not_a_resume_source'] = True
    if filter_bindings_path is not None:
        bindings = load(filter_bindings_path)
        need(set(bindings) == {'exclusion_index_receipt', 'root_index_acceptance_reference', 'regression_reference', 'parent_transport_manifest'}, 'Only actual all11 source/acceptance/regression/transport pins may extend the filter plan')
        plan.update(bindings); plan['filter_bindings_reference'] = reference(filter_bindings_path)
    return write(plan_path, plan)


def validate(plan):
    need(plan['schema'] == 'ALPHA_ORIGINAL502_TYPED_HANDOFF_PLAN_V1' and plan['endpoint'] == ENDPOINT and plan['uid'] == UID and plan['logical_descriptor_count'] == 500 and plan['fragment_count'] == 502 and plan['source_rows'] == 124857440 and plan['source_snapshot_sha256'] == RAW_SHA, 'Honest original Alpha500logical/502physical full scope required')
    need(plan['fragments'] == load_coverage(plan['coverage_reference']), 'Exact original502 mapping changed')
    if 'original_materialization_plan_reference' in plan:
        original = load(verify(plan['original_materialization_plan_reference']))
        need(original['fragments'] == plan['fragments'] and original['coverage_reference'] == plan['coverage_reference'], 'Original metadata/data mapping changed')
        verify(plan['original_frozen_kernel_manifest_reference'])
    need(original_science() == plan['original_science_references'], 'Original Alpha scientific source pins changed')
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coverage', required=True); p.add_argument('--resources', required=True); p.add_argument('--plan', required=True)
    p.add_argument('--filter-bindings', help='Actual accepted origin receipts plus Alpha replica manifest; no pending placeholders')
    a = p.parse_args(); print(prepare(a.coverage, a.resources, a.plan, a.filter_bindings))


if __name__ == '__main__':main()
