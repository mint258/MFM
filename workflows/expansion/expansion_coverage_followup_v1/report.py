"""Reuse both closed190 populations; append actual fixed1M before/after evidence."""
import argparse
from pathlib import Path
import sqlite3
from ..alpha_runtime_v1 import common as Q, profile
from ..alpha_runtime_v1.guard import Guard
from ..current_baseline_report_v1.run import statistics, read
from ..current_baseline_report_v1 import state
from ..pubchem_generic_recovery_overlay_v1.runtime import VERSION
from ..exact_nn_cached_v1.engine import RECIPE, ALGORITHM


def nearest(ref, role, review, populations, common, out, before_reference=None):
    native = read(ref)
    Q.need(native['schema'] == 'EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1' and native['status'] == 'COMPLETE'
           and native['queries'] == native['projection']['rows'] == 1000000
           and native['nearest_similarity_exact'] is True and native['fingerprint_recipe'] == RECIPE
           and native['algorithm'] == ALGORITHM and native['reference_role'] == role
           and native['baseline_receipt'] == review['corrected_baseline_receipt_reference']
           and native['decontamination_applied_to_sample'] is False
           and native['candidate_pool_release_authorized'] is False,
           'Actual full fixed1M scientific coverage EOF; never cost scope or full-pool release relabel')
    proof = read(native['launcher_startup_proof_reference'])
    Q.need(proof['uid'] == 1264 and proof['endpoint'] == Q.ENDPOINT
           and proof['request']['producer_plan_reference'] == native['resource_plan'],
           'Original actual allocated coverage producer lineage')
    packed = read(native['reference_manifest'])
    Q.need(packed['status'] == 'COMPLETE' and packed['fingerprint_recipe'] == RECIPE
           and packed['targets_present'] is False, 'Exact complete reference recipe')
    groups = ['v1_common'] if role == 'before' else ['v1_common', 'R', 'N']
    if role == 'before':
        Q.need(native['reference_molecules'] == packed['molecules'] == 1196122
               and packed['input_manifest'] == common['authority_reference'], 'Same complete Common as190 statistics')
    else:
        Q.need(native['reference_molecules'] == packed['molecules'] == 3696122
               and packed['base_reference_manifest'] == before_reference and packed['added_molecules'] == 2500000
               and packed['original_reference_ordinals_preserved_as_exact_prefix'] is True,
               'Same complete Common prefix plus all2.5M actual R/N graph rows')
        source = read(packed['added_source_manifest'])
        for group in ('R', 'N'):
            pop = read(populations[group])
            Q.need(pop['authority_reference'] == packed['added_source_manifest']
                   and pop['expected_molecules'] == source['molecules_by_stream'][group] == 1250000,
                   'After exact reference and R/N statistics must bind the identical first batch')
    name = 'pubchem_to_v1' if role == 'before' else 'pubchem_to_augmented'
    evidence = dict(schema='PUBCHEM_NATIVE_COVERAGE_DISTRIBUTION_BINDING_V1', status='COMPLETE',
                    native_scientific_coverage_receipt_reference=ref, queries=1000000, nearest_similarity_exact=True,
                    query_population_manifest_reference=populations['pubchem_1m'],
                    reference_population_manifest_references=[populations[g] for g in groups],
                    native_receipt_or_projection_modified=False, new_per_job_Root_review_required=False)
    eref = Q.write(out / (name + '_producer_binding.json'), evidence)
    manifest = dict(schema='EXPANSION_EXACT_NEAREST_DISTRIBUTION_V1', status='COMPLETE', comparison=name,
                    nearest_similarity_exact=True, fingerprint_recipe=RECIPE, query_population='pubchem_1m',
                    query_population_manifest_reference=populations['pubchem_1m'], reference_populations=groups,
                    reference_population_manifest_references=[populations[g] for g in groups], expected_queries=1000000,
                    producer_evidence_reference=eref, results=dict(identity_column='full_key',
                    artifacts=[dict(native['projection'], format='jsonl')]), value_column='nearest_reference_tanimoto',
                    original_scientific_coverage_receipt_reference=ref, population_version=VERSION)
    return Q.write(out / (name + '_distribution.json'), manifest), native


def run(plan_path, proof_path):
    plan = Q.load(plan_path); proof = Q.load(proof_path); actual = profile.admit(plan, minimum_workers=16)
    Q.need(plan['schema'] == 'PUBCHEM_DISTRIBUTION_FOLLOWUP_REPORT_PLAN_V1'
           and plan['report_scope'] in ('baseline', 'batch_graph')
           and proof['request']['producer_plan_reference'] == Q.reference(plan_path)
           and proof['request']['execution_argv'] == plan['execution_argv']
           and str(proof['job_id']) == actual['job_id'] and proof['uid'] == 1264,
           'Actual report allocation and exact plan binding')
    for path in Path(__file__).parent.glob('*.py'):
        Q.need(Q.reference(path) in proof['request']['source_references'], 'Actual followup source pins')
    guard = Guard(plan); out = Path(plan['output_directory']); Q.need(not out.exists(), 'Fresh counted report namespace')
    try:
        out.mkdir(mode=0o700)
        review, original, refs, q, common = statistics(plan['statistics_actual_review_reference'])
        from ..distribution_report_v1 import __main__ as runtime, aggregate, io, functional_groups, population_tables, render
        byname = {Path(ref['path']).name: ref for ref in original['source_references']}
        Q.need(len(byname) == 10, 'Original ten statistics sources reused unchanged')
        for ref in byname.values():
            Q.verify(ref); Q.need(ref in proof['request']['source_references'], 'Original statistics sources startup pinned')
        for module in (runtime, aggregate, io, functional_groups, population_tables, render):
            Q.need(Path(module.__file__).resolve() == Path(byname[Path(module.__file__).name]['path']).resolve(),
                   'Actual original190 statistics implementation, no descriptor/statistical rewrite')
        Q.need(functional_groups.recipe() == read(original['functional_group_recipe_reference']), 'Same fixed functional-group definition')
        expected = {name: (ref, review['populations'][name], 1) for name, ref in refs.items()}
        database = out / 'counted_statistics.sqlite'
        clone = state.clone(review['closed_database_path'], review['closed_database_frame'], database, expected, guard.check)
        populations = dict(refs); rn_refs = []
        batch = plan['report_scope'] == 'batch_graph'
        if batch:
            prepared = read(plan['rn_population_sources_reference'])
            Q.need(prepared['schema'] == 'PUBCHEM_RN_DISTRIBUTION_SOURCES_V1' and prepared['status'] == 'COMPLETE',
                   'Actual full R/N graph statistical sources required')
            for group in ('R', 'N'):
                populations[group] = prepared['population_manifests'][group]; rn_refs.append(populations[group])
        before_ref, before = nearest(plan['before_coverage_reference'], 'before', review, populations, common, out)
        nearest_refs = [before_ref]
        if batch:
            after_ref, after = nearest(plan['after_coverage_reference'], 'after', review, populations, common, out,
                                       before_reference=before['reference_manifest'])
            nearest_refs.append(after_ref)
        derived = dict(plan, schema='EXPANSION_DISTRIBUTION_PLAN_V1', population_manifests=rn_refs,
                       nearest_manifests=nearest_refs)
        dpath = out / 'original_distribution_plan.json'; Q.write(dpath, derived)
        if batch:
            result = runtime.run(dpath, 'all', startup_proof=proof_path)
        else:
            runtime.run(dpath, 'nearest', startup_proof=proof_path)
            result = runtime.run(dpath, 'baseline_report', startup_proof=proof_path)
        db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
        try:
            unchanged = state.digests(db, guard.check)
            Q.need(unchanged == clone['population_logical_digests'], 'All five tables for both190 populations remain unchanged')
        finally: db.close()
        guard.sample(); guard.check()
        return Q.write(out / 'manifest.json', dict(schema='PUBCHEM_DISTRIBUTION_FOLLOWUP_REPORT_V1', status='COMPLETE',
            report_scope='TASK2_1_AND_TASK2_9_GRAPH_DISTRIBUTIONS' if batch else 'TASK2_1_BASELINE',
            statistics_actual_review_reference=plan['statistics_actual_review_reference'],
            original190_populations_recomputed=0, population_clone_proof=clone,
            before_coverage_reference=plan['before_coverage_reference'],
            after_coverage_reference=plan.get('after_coverage_reference'), original_distribution_report=result,
            actual_parent=actual, source_plan_reference=Q.reference(plan_path), startup_proof_reference=Q.reference(proof_path),
            new_per_job_Root_acceptance_required=False, UFF_D_quality_or_final_batch_completion_claimed=False))
    finally: guard.close()


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--plan', required=True); p.add_argument('--startup-proof', required=True)
    args = p.parse_args(); print(run(args.plan, args.startup_proof))


if __name__ == '__main__': main()
