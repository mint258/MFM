"""Close disjoint actual NN work manifests without copying projection data."""
import argparse
import json
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from ..alpha_exact_key_filter_v1.core import POLICY
from ..exact_nn_cached_v1.engine import RECIPE, ALGORITHM
from .partition import assignment, cover

RULE = 'MD5_OF_CANONICAL_FP_HEX_TEXT_FIRST_NIBBLE'


def aggregate(shard_references, output):
    """Call in rank allocation prepare; no job, Root approval or fake future pin."""
    import pyarrow.parquet as pq
    Q.need(len(shard_references) == 2, 'Two actual disjoint NN work manifests required')
    values = []
    for ref in shard_references:
        Q.need(ref['bytes'] <= 2 << 20, 'Small actual shard manifest required')
        value = Q.load(Q.verify(ref))
        Q.need(value['schema'] == 'PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1'
               and value['producer_schema'] == 'PUBCHEM_PARTITIONED_EXACT_NOVELTY_SHARD_V1'
               and value['status'] == 'SHARD_COMPLETE' and value['partition_rule'] == RULE
               and value['fingerprint_recipe'] == RECIPE and value['algorithm'] == ALGORITHM
               and value['nearest_similarity_exact'] is True and value['reference_molecules'] == 1196122
               and value['downstream_features_used'] is False
               and value['complete_filtered_population_processed'] is False,
               'Actual completed assigned subset; never a relabelled full population')
        assignment(value)
        binding = Q.load(Q.verify(value['source_binding_reference']))
        Q.need(binding == {k: value[k] for k in ('filtered_pool_reference', 'reference',
               'backend_adoption_reference', 'assigned_hash_buckets', 'partition_id', 'scope_key')},
               'Actual closed source binding must retain exact partition and source/reference pins')
        values.append(value)
    Q.need(values[0]['partition_id'] != values[1]['partition_id'], 'Distinct work partition IDs required')
    buckets = cover([value['assigned_hash_buckets'] for value in values])
    same = ('filtered_pool_reference', 'reference', 'backend_adoption_reference', 'reference_fingerprints',
            'reference_keys', 'reference_counts', 'fingerprint_recipe', 'algorithm', 'partition_rule')
    Q.need(all(values[0][key] == values[1][key] for key in same), 'Both shards must bind identical full source/reference/math')
    first = values[0]
    filtered = Q.load(Q.verify(first['filtered_pool_reference']))
    Q.need(filtered['schema'] == 'PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1' and filtered['status'] == 'COMPLETE'
           and filtered['policy'] == POLICY, 'Actual whole exact-key filtered source required')
    Q.verify(first['reference'])
    total = filtered['eligible_molecules']
    Q.need(sum(part['rows'] for part in filtered['candidates']) == total, 'Whole filtered physical part census differs')
    parts = []; seen_paths = set(); seen_inodes = set()
    for value in values:
        queries = value['queries']
        Q.need(type(queries) is int and 0 <= queries <= total
               and type(value['distinct_query_fingerprints']) is int
               and 0 <= value['distinct_query_fingerprints'] <= queries
               and value['whole_filtered_input_rows'] == total
               and value['unselected_population_rows'] + queries == total
               and sum(value['full_input_rows_by_physical_FP_bucket'].values()) == total
               and sum(value['selected_input_rows_by_physical_FP_bucket'].values()) == queries
               and sum(part['rows'] for part in value['projection_parts']) == queries,
               'Complete-input versus selected-partition conservation must be explicit')
        observed = 0
        for part in value['projection_parts']:
            path = Path(part['path']); before = Q.frame(path)
            Q.need(str(path) not in seen_paths and (before[0], before[1]) not in seen_inodes
                   and before[2] == part['bytes'] and type(part['rows']) is int and part['rows'] > 0,
                   'Distinct physical closed projection files required; no repeated part inputs')
            rows = pq.ParquetFile(path).metadata.num_rows
            Q.need(rows == part['rows'] and Q.frame(path) == before, 'Actual closed Parquet footer/frame row census differs')
            seen_paths.add(str(path)); seen_inodes.add((before[0], before[1])); observed += rows
            parts.append(part)
        Q.need(observed == queries, 'Every assigned query identity must have one physical projection row')
    Q.need(sum(value['queries'] for value in values) == total, 'Disjoint work partitions must cover every eligible identity')
    result = dict(schema='PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1', status='COMPLETE',
                  producer_schema='PUBCHEM_PARTITIONED_EXACT_NOVELTY_AGGREGATE_V1',
                  filtered_pool_reference=first['filtered_pool_reference'], reference=first['reference'],
                  queries=total, whole_filtered_input_rows=total,
                  distinct_query_fingerprints=sum(v['distinct_query_fingerprints'] for v in values),
                  projection_parts=parts, fingerprint_recipe=RECIPE, algorithm=ALGORITHM,
                  reference_molecules=1196122, nearest_similarity_exact=True, downstream_features_used=False,
                  complete_filtered_population_processed=True, backend_adoption_reference=first['backend_adoption_reference'],
                  partition_rule=RULE, assigned_hash_buckets=buckets,
                  partition_manifest_references=shard_references,
                  partitions=[dict(partition_id=v['partition_id'], assigned_hash_buckets=v['assigned_hash_buckets'],
                                   queries=v['queries'], distinct_query_fingerprints=v['distinct_query_fingerprints']) for v in values],
                  pairwise_disjoint_hash_assignments_and_complete_cover=True,
                  physical_projection_footer_rows_verified=True,
                  projection_body_full_SHA_recomputed_during_aggregation=False,
                  producer_projection_body_SHA_references_preserved=True)
    return Q.write(output, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shard-manifest', action='append', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(aggregate([Q.reference(path) for path in args.shard_manifest], args.output), sort_keys=True))


if __name__ == '__main__':
    main()
