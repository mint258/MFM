"""Actual first2.5M graph rows to original four-population statistics inputs."""
import argparse
import os
from pathlib import Path
from ..alpha_runtime_v1 import common as Q, profile
from ..alpha_runtime_v1.guard import Guard
from ..alpha_closed500_handoff_v1.sql import SQLStopper, literal
from ..alpha_exact_key_filter_v1.core import POLICY
from ..alpha_exact_key_filter_v1.storage import Storage, write_shards
from ..exact_nn_cached_v1.sql_runtime import configure


def run(plan_path, proof_path):
    import duckdb
    plan = Q.load(plan_path); proof = Q.load(proof_path); actual = profile.admit(plan, minimum_workers=16)
    Q.need(plan['schema'] == 'PUBCHEM_RN_DISTRIBUTION_SOURCE_PLAN_V1'
           and proof['request']['producer_plan_reference'] == Q.reference(plan_path)
           and proof['request']['execution_argv'] == plan['execution_argv']
           and str(proof['job_id']) == actual['job_id'] == os.environ['SLURM_JOB_ID'] and proof['uid'] == 1264,
           'Actual allocated R/N statistical source preparation')
    for file in Path(__file__).parent.glob('*.py'):
        Q.need(Q.reference(file) in proof['request']['source_references'], 'Actual source preparation code pinned')
    source_ref = plan['ordered_source_manifest_reference']; source = Q.load(Q.verify(source_ref))
    Q.need(source['schema'] == 'PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1'
           and source['molecules'] == 2500000 and source['molecules_by_stream'] == {'R': 1250000, 'N': 1250000},
           'Whole actual ordered source graphs, not conformer success subset')
    rank_ref = source['ranking_receipt']; rank = Q.load(Q.verify(rank_ref))
    filtered_ref = rank['filtered_pool']; filtered = Q.load(Q.verify(filtered_ref))
    Q.need(filtered['schema'] == 'PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1' and filtered['status'] == 'COMPLETE'
           and filtered['policy'] == POLICY and source['typed_filtered_pool'] == filtered_ref,
           'Actual current exact-key filtered first batch')
    guard = Guard(plan); out = Path(plan['output_directory']); Q.need(not out.exists(), 'Fresh R/N statistical source directory')
    out.mkdir(mode=0o700); store = Storage(out, guard.check, Q.reference)
    db = duckdb.connect(':memory:'); monitor = None
    try:
        configure(db, plan, out / 'spill'); monitor = SQLStopper(db, store.check)
        db.read_parquet([str(Q.verify(ref)) for ref in filtered['candidates']]).create_view('candidates')
        batch_ref = rank['batch1']; db.read_parquet(str(Q.verify(batch_ref))).create_view('batch1')
        Q.need(db.execute('SELECT count(*),count(DISTINCT cid),count(DISTINCT full_key) FROM batch1').fetchone()
               == (2500000, 2500000, 2500000), 'Full first-batch unique membership')
        Q.need(db.execute('SELECT stream,count(*),min(stream_rank),max(stream_rank),count(DISTINCT stream_rank) FROM batch1 GROUP BY stream ORDER BY stream').fetchall()
               == [('N',1250000,1,1250000,1250000),('R',1250000,1,1250000,1250000)], 'Exact full stream domains')
        Q.need(db.execute('SELECT count(*) FROM batch1 ANTI JOIN candidates USING(cid,full_key)').fetchone()[0] == 0,
               'Every actual ranked source identity has original graph features')
        manifests = {}
        for stream in ('R', 'N'):
            sql = 'SELECT c.*,b.stream,b.stream_rank FROM candidates c JOIN batch1 b USING(cid,full_key) WHERE b.stream=' + literal(stream)
            parts, count, _ = write_shards(db.execute(sql).fetch_record_batch(131072), out / (stream + '_features'), store)
            Q.need(count == 1250000, 'All graph rows retained independently of UFF success')
            artifact = {**batch_ref, 'format': 'parquet'}
            population = dict(schema='EXPANSION_DISTRIBUTION_POPULATION_V1', status='COMPLETE',
                population=stream, stream=stream, population_scope='FULL_DECLARED_POPULATION', expected_molecules=count,
                authority_reference=source_ref, authority_count_pointer='/molecules_by_stream/' + stream,
                authority_kind='ACTUAL_ORDERED_FIRST_BATCH_GRAPH_MEMBERSHIP', is_sample=False,
                selection_status='FINAL_FIRST_BATCH_FROM_RELEASED_DECONTAMINATED_ORDER',
                membership=dict(identity_column='full_key', artifacts=[artifact], equals={'stream': stream}, maximum_stream_rank=1250000),
                features=dict(identity_column='full_key', artifacts=[dict(p, format='parquet') for p in parts]),
                allow_additive_descriptor_completion=False, source_pool_receipt=filtered['source_pool_receipt'],
                graph_statistics_scope='ALL_SELECTED_GRAPHS_INCLUDING_UFF_FAILURES', UFF_success_condition_applied=False)
            manifests[stream] = Q.write(out / (stream + '_population.json'), population)
        store.close()
        return Q.write(out / 'manifest.json', dict(schema='PUBCHEM_RN_DISTRIBUTION_SOURCES_V1', status='COMPLETE',
            population_manifests=manifests, ordered_source_manifest_reference=source_ref, ranking_receipt_reference=rank_ref,
            filtered_pool_reference=filtered_ref, molecules_by_stream={'R':1250000,'N':1250000},
            graph_feature_values_recomputed=False, functional_groups_computed_here=False,
            actual_parent=actual, plan_reference=Q.reference(plan_path)))
    finally:
        if monitor is not None: monitor.close()
        db.close(); store.close(); guard.close()


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--plan', required=True); p.add_argument('--startup-proof', required=True)
    args = p.parse_args(); print(run(args.plan, args.startup_proof))


if __name__ == '__main__': main()
