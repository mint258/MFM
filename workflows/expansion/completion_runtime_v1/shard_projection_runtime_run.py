"""Full-reference exact NN with small immutable shards; no per-job approvals."""
import argparse
from collections import defaultdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from ..alpha_runtime_v1 import common as Q
from ..common import require
from ..portable_sources_v1.transport import bind_plan
from ..exact_nn_cached_v1.run import Guard, allocation_guard
from ..exact_nn_cached_v1.engine import RECIPE, ALGORITHM
from ..exact_nn_popcount_production_v1.workers import exact_batches
from ..exact_nn_cached_v1.sql_runtime import configure, literal
from ..exact_nn_cached_v1.domain import HydrogenDomainDB
from ..external_sort import create_queues
from .partition import assignment, predicate


class ShardGuard(Guard):
    def poll(self, force=False, reserve=0):
        # Preserve real aggregate quota checks, without walking it for every IPC batch.
        if force or time.monotonic() - self.last >= 30:
            super().poll(force=True, reserve=reserve)
            self.last = time.monotonic()  # A slow native check must not trigger another immediately.


def projection_sql(db, reference_sha):
    db.execute("""CREATE OR REPLACE TEMP TABLE ring_counts AS
        SELECT c.full_key,min(coalesce(r.n,0)) AS n
        FROM candidates c CROSS JOIN unnest(c.generic_ring_systems) t(key)
        LEFT JOIN rings r ON t.key=r.key GROUP BY c.full_key""")
    return """SELECT c.cid,c.full_key,c.heavy_atoms,c.element_combination,c.generic_murcko,
        c.generic_ring_systems,s.nearest_v1_tanimoto,coalesce(sc.n,0)::BIGINT AS v1_scaffold_count,
        coalesce(rc.n,1196122)::BIGINT AS v1_ring_system_count,
        """ + literal(reference_sha) + """ AS v1_reference_sha256
        FROM candidates c JOIN scored s USING(ecfp4_2048_hex)
        LEFT JOIN scaffolds sc ON c.generic_murcko=sc.key
        LEFT JOIN ring_counts rc ON c.full_key=rc.full_key"""


def native_preflight():
    """One small actual SQL check: duplicate FP preserves every MID and graph count."""
    import duckdb
    db = duckdb.connect()
    try:
        db.execute('CREATE TABLE candidates(cid BIGINT,full_key VARCHAR,heavy_atoms BIGINT,element_combination VARCHAR,generic_murcko VARCHAR,generic_ring_systems VARCHAR[],ecfp4_2048_hex VARCHAR)')
        db.executemany('INSERT INTO candidates VALUES(?,?,?,?,?,?,?)', [
            (1,'A'*14+'-'+'B'*10+'-N',3,'6','S',['R','missing'],'fp1'),
            (2,'C'*14+'-'+'D'*10+'-N',4,'6','T',[],'fp1'),
            (3,'E'*14+'-'+'F'*10+'-N',0,'','',[],'fp2')])
        db.execute("CREATE TABLE scored AS SELECT * FROM (VALUES ('fp1',0.25::DOUBLE),('fp2',0.0::DOUBLE)) t(ecfp4_2048_hex,nearest_v1_tanimoto)")
        db.execute("CREATE TABLE scaffolds AS SELECT * FROM (VALUES ('S',5::BIGINT),('T',2::BIGINT)) t(key,n)")
        db.execute("CREATE TABLE rings AS SELECT * FROM (VALUES ('R',7::BIGINT)) t(key,n)")
        db.execute('CREATE TABLE projected AS ' + projection_sql(db,'a'*64))
        require(db.execute('SELECT cid,nearest_v1_tanimoto,v1_scaffold_count,v1_ring_system_count FROM projected ORDER BY cid').fetchall()
                == [(1,0.25,5,0),(2,0.25,2,1196122),(3,0.0,0,1196122)], 'Original graph count defaults and FP multi-MID projection differ')
        require(db.execute("SELECT count(*) FROM projected WHERE heavy_atoms=0 AND element_combination=''").fetchone()[0] == 1,
                'H-only candidate disappeared')
        left = predicate(list('0123456789a')); right = predicate(list('bcdef'))
        require(db.execute('SELECT count(*) FROM candidates WHERE (' + left + ') OR (' + right + ')').fetchone()[0] == 3
                and db.execute('SELECT count(*) FROM candidates WHERE (' + left + ') AND (' + right + ')').fetchone()[0] == 0,
                'Actual SQL MD5 query work allocation must be complete and disjoint')
    finally:
        db.close()
    print(json.dumps({'event':'SHARDED_NOVELTY_SQL_PREFLIGHT','status':'PASS','case':'FP_MULTI_MID_MISSING_RING_EMPTY_RING_H_ONLY'}),flush=True)

def parts_by_bucket(filtered):
    """Each physical candidate identity occurs once; identical FP shares a bucket."""
    from ..alpha_exact_key_filter_v1.core import POLICY
    require(filtered['schema'] == 'PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1'
            and filtered['status'] == 'COMPLETE' and filtered['policy'] == POLICY,
            'Actual complete user exact-key policy filter required')
    groups = defaultdict(list)
    for part in filtered['candidates']:
        bucket = part['fp_bucket']
        require(bucket in '0123456789abcdef' and len(bucket) == 1, 'Invalid FP bucket')
        groups[bucket].append(part)
    require(sum(p['rows'] for p in filtered['candidates']) == filtered['eligible_molecules'],
            'Filtered shard census differs')
    return groups


def read_parts(db, parts, name):
    paths = [str(Q.verify(part)) for part in parts]
    require(paths, 'Nonempty shard list required')
    db.read_parquet(paths).create_view(name, replace=True)


def closed(path, rows, bucket, journal):
    with Path(path).open('rb') as stream:
        os.fsync(stream.fileno())
    ref = {**Q.reference(path), 'rows': rows, 'fp_bucket': bucket}
    journal.write(json.dumps(ref, sort_keys=True) + '\n')
    journal.flush()
    os.fsync(journal.fileno())
    return ref


def write_arrow(db, sql, target, bucket, journal, guard, rows_per_part=200000):
    """Bound every open Parquet file; each close is a real resumable checkpoint."""
    import pyarrow.parquet as pq
    target = Path(target); target.mkdir(parents=True, exist_ok=True)
    result = []
    reader = db.execute(sql).fetch_record_batch(rows_per_part)
    for batch in reader:
        path = target / ('part_%06d.parquet' % len(result))
        require(not path.exists(), 'Never overwrite a closed shard')
        pq.write_table(__import__('pyarrow').Table.from_batches([batch]), path, compression='zstd')
        result.append(closed(path, batch.num_rows, bucket, journal))
        guard.poll()  # Retain the real 30-second resource cadence across small closed projections.
    return result


def configure_db(db, plan, root):
    configure(db, plan, root / 'spill')


def load_counts(db, path):
    """Read the frozen v1 count tables once, with unchanged keys and integer counts."""
    import pyarrow as pa
    connection = sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)
    try:
        for name in ('scaffolds', 'rings'):
            db.execute('CREATE TABLE ' + name + '(key VARCHAR,n BIGINT)')
            cursor = connection.execute('SELECT key,n FROM ' + name)
            while True:
                rows = cursor.fetchmany(10000)
                if not rows:
                    break
                table = pa.table({'key': [r[0] for r in rows], 'n': [r[1] for r in rows]})
                db.register('_count_batch', table)
                db.execute('INSERT INTO ' + name + ' SELECT * FROM _count_batch')
                db.unregister('_count_batch')
    finally:
        connection.close()


def _start(plan_path):
    plan = Q.load(plan_path)
    bind_plan(plan)
    if plan['schema'] == 'ALPHA_SHARDED_EXACT_RANK_PLAN_V1':
        from ..alpha_runtime_v1.profile import admit
        admit(plan, minimum_workers=16)
        available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        require(available >= plan['parent_rss_cap_bytes'] + plan['minimum_node_available_bytes'], 'Actual SQL memory and reserve required')
    else:
        allocation_guard(plan)
    root = Path(plan['output_directory'])
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'parent.lock').open('a+b')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    guard = ShardGuard(plan, root); guard.poll(force=True)
    return plan, root, lock, guard


def run_nn(plan_path):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    plan, root, lock, guard = _start(plan_path)
    require(plan['schema'] == 'ALPHA_SHARDED_EXACT_NOVELTY_PLAN_V1', 'Wrong novelty plan')
    native_preflight()
    assigned = assignment(plan)
    selected_predicate = predicate(assigned)
    filtered = Q.load(Q.verify(plan['filtered_pool_reference']))
    groups = parts_by_bucket(filtered)
    inverted = plan.get('compiled_backend_implementation') == 'INTEGER_INVERTED_CSR_PRIVATE_COPY_PROTOTYPE_V1'
    if inverted:
        from ..exact_nn_inverted_production_v1.authority import adopted
        from ..exact_nn_inverted_production_v1.workers import exact_batches as run_batches
    else:
        require(plan.get('compiled_backend_implementation') in (None, 'INTEGER_GROUP_POPCOUNT_PRIVATE_COPY_PROTOTYPE_V1'),
                'Explicit known exact implementation only')
        from ..exact_nn_popcount_production_v1.authority import adopted
        run_batches = exact_batches
    adoption, _ = adopted(plan['backend_adoption_reference'])
    require(adoption['reference_manifest_reference'] == plan['reference_manifest'],
            'Native backend and ranking counts/keys must use the same actual full reference')
    packed = Q.load(Q.verify(plan['reference_manifest']))
    require(packed['status'] == 'COMPLETE' and packed['molecules'] == 1196122
            and packed['fingerprint_recipe'] == RECIPE and packed['targets_present'] is False,
            'Frozen complete Common reference required')
    fp_path = Q.verify(packed['fingerprints'])
    key_path = Q.verify(packed['keys'])
    counts_path = Q.verify(packed['counts'])
    manifest_path = root / 'manifest.json'
    if inverted and (root / 'source_binding.json').exists():
        from ..exact_nn_inverted_production_v1.authority import previous_writers
        previous_writers(plan, Q.load(root / 'source_binding.json'))
    if manifest_path.exists():
        value = Q.load(manifest_path)
        require(value['status'] == 'SHARD_COMPLETE' and value['filtered_pool_reference'] == plan['filtered_pool_reference']
                and value['reference'] == plan['reference_manifest']
                and value['assigned_hash_buckets'] == assigned and value['partition_id'] == plan['partition_id']
                and value['scope_key'] == plan['scope_key']
                and (not inverted or value['backend_adoption_reference'] == plan['backend_adoption_reference']),
                'Closed novelty has different inputs/work partition/backend; never relabel an immutable complete manifest')
        return value
    began = time.monotonic()
    journal = (root / ('closed_files_' + uuid.uuid4().hex + '.jsonl')).open('x', encoding='utf-8')
    score_parts = []
    known = defaultdict(list)
    binding = {'filtered_pool_reference': plan['filtered_pool_reference'],
               'reference': plan['reference_manifest'],
               'backend_adoption_reference': plan['backend_adoption_reference'],
               'assigned_hash_buckets': assigned, 'partition_id': plan['partition_id'],
               'scope_key': plan['scope_key']}
    binding_path = root / 'source_binding.json'
    continuation_ref = None
    if inverted:
        from ..exact_nn_inverted_production_v1.binding import establish
        binding_ref, continuation_ref = establish(root, binding, adoption)
        binding_path = Path(binding_ref['path'])
    elif binding_path.exists():
        require(Q.load(binding_path) == binding, 'Closed shard cache input binding differs')
    else:
        Q.write(binding_path, binding)
    for journal_path in sorted(root.glob('closed_files*.jsonl')):
        with journal_path.open('rb') as prior:
            for line in prior:
                if not line.endswith(b'\n'):
                    break  # Preserve crash tail; append only to this attempt's fresh journal.
                part = json.loads(line)
                path = Path(part['path'])
                require(path.is_relative_to(root), 'Closed cache outside the actual output root')
                if path.is_relative_to(root / 'scores'):
                    Q.verify(part)
                    require(pq.ParquetFile(path).metadata.num_rows == part['rows'], 'Closed score rows differ')
                    known[part['fp_bucket']].append(part)
    db = duckdb.connect()
    configure_db(db, plan, root)
    per_bucket_unique = {}
    full_input_rows = {}; selected_input_rows = {}
    worker_log = (root / 'workers.jsonl').open('a', encoding='utf-8')
    def ready(value):
        require(value['reference_records_loaded'] == packed['molecules'], 'Worker reference subset forbidden')
        worker_log.write(json.dumps({'kind': 'reference_loaded', **value}) + '\n')
        worker_log.flush()
    def batches():
        for bucket in sorted(groups):
            read_parts(db, groups[bucket], 'all_candidates')
            total, bad = db.execute("""SELECT count(*),count(*) FILTER(WHERE ecfp4_2048_hex IS NULL
                OR NOT regexp_full_match(ecfp4_2048_hex,'[0-9a-f]{512}')
                OR substr(ecfp4_2048_hex,1,1)<>?) FROM all_candidates""", [bucket]).fetchone()
            require(bad == 0 and total == sum(p['rows'] for p in groups[bucket]), 'Full physical bucket census/FP width differs')
            full_input_rows[bucket] = total
            db.execute('CREATE OR REPLACE TEMP VIEW candidates AS SELECT * FROM all_candidates WHERE ' + selected_predicate)
            selected_input_rows[bucket] = db.execute('SELECT count(*) FROM candidates').fetchone()[0]
            per_bucket_unique[bucket] = 0
            previous = list(known[bucket])
            if previous:
                read_parts(db, previous, 'previous_scores')
                require(db.execute('SELECT count(*) FROM previous_scores WHERE NOT (' + selected_predicate + ')').fetchone()[0] == 0,
                        'Closed cache contains another assigned work partition')
            # Sparse ECFP leading bits are skewed. Large physical buckets use a
            # deterministic hash partition ONLY for bounded exact query dedup;
            # all FPs and all reference molecules remain searched.
            subgroups = assigned if sum(p['rows'] for p in groups[bucket]) > 8000000 else [None]
            for subgroup in subgroups:
                condition = 'true' if subgroup is None else 'substr(md5(ecfp4_2048_hex),1,1)=' + literal(subgroup)
                db.execute('CREATE OR REPLACE TEMP VIEW current_fp AS SELECT ecfp4_2048_hex FROM candidates WHERE ' + condition)
                per_bucket_unique[bucket] += db.execute('SELECT count(DISTINCT ecfp4_2048_hex) FROM current_fp').fetchone()[0]
                if previous:
                    db.execute('CREATE OR REPLACE TEMP VIEW scored AS SELECT * FROM previous_scores WHERE ' + condition)
                    count, unique, invalid = db.execute("""SELECT count(*),count(DISTINCT ecfp4_2048_hex),
                        count(*) FILTER(WHERE reference_molecules<>1196122 OR reference_ordinal<0
                        OR reference_ordinal>=1196122 OR score_denominator<=0
                        OR score_numerator<0 OR score_numerator>score_denominator
                        OR nearest_v1_tanimoto<>(score_numerator::DOUBLE/score_denominator::DOUBLE))
                        FROM scored""").fetchone()
                    require(count == unique and invalid == 0, 'Invalid closed score cache')
                    require(db.execute('SELECT count(*) FROM scored ANTI JOIN current_fp USING(ecfp4_2048_hex)').fetchone()[0] == 0,
                            'Closed cache FP outside candidate partition')
                    query = 'SELECT DISTINCT c.ecfp4_2048_hex FROM current_fp c ANTI JOIN scored s USING(ecfp4_2048_hex) ORDER BY 1'
                else:
                    query = 'SELECT DISTINCT ecfp4_2048_hex FROM current_fp ORDER BY 1'
                cursor = db.execute(query)
                while True:
                    rows = cursor.fetchmany(plan.get('query_batch', 128))
                    if not rows:
                        break
                    yield [(row[0], bytes.fromhex(row[0])) for row in rows]
            guard.poll(force=True)
    buffers = defaultdict(list)
    with key_path.open('rb') as keys:
        def flush(bucket):
            rows = buffers[bucket]
            if not rows:
                return
            folder = root / 'scores' / bucket; folder.mkdir(parents=True, exist_ok=True)
            # Previously closed immutable files are never overwritten.
            index = uuid.uuid4().hex
            path = folder / ('part_' + index + '.parquet')
            require(not path.exists(), 'Closed cache filename collision')
            pq.write_table(pa.Table.from_pylist(rows), path, compression='zstd')
            part = closed(path, len(rows), bucket, journal)
            known[bucket].append(part); buffers[bucket] = []
            guard.poll()  # Keep the native 30-second quota cadence across small immutable checkpoints.
        try:
            for result in run_batches(fp_path, packed['molecules'], batches(), workers=plan['workers'],
                    worker_rss_cap_bytes=plan['worker_rss_cap_bytes'], ready_callback=ready,
                    backend_adoption_reference=plan['backend_adoption_reference']):
                for identity, raw, value in result.pop('results'):
                    require(raw.hex() == identity, 'Worker FP identity changed')
                    require(hashlib.md5(identity.encode('ascii')).hexdigest()[0] in assigned,
                            'Worker result outside exact assigned MD5 work partition')
                    keys.seek(value['reference_ordinal'] * 28)
                    key = keys.read(28).decode('ascii').rstrip('\n')
                    row = {'ecfp4_2048_hex': identity, 'nearest_v1_key': key,
                           'nearest_v1_tanimoto': value.pop('score'), **value}
                    bucket = identity[0]; buffers[bucket].append(row)
                    if len(buffers[bucket]) >= 4096:
                        flush(bucket)
                worker_log.write(json.dumps({'kind': 'exact_batch', **result}) + '\n')
                worker_log.flush()
                guard.poll()
            for bucket in sorted(buffers):
                flush(bucket)
        finally:
            worker_log.close()
    db.close()
    # No workers remain during the count joins / projection export.
    db = duckdb.connect(); configure_db(db, plan, root)
    load_counts(db, counts_path)
    projections = []
    for bucket in sorted(groups):
        bucket_manifest = root / ('projection_' + bucket + '.json')
        if bucket_manifest.exists():
            done = Q.load(bucket_manifest)
            require(done['filtered_pool_reference'] == plan['filtered_pool_reference']
                    and done['reference'] == plan['reference_manifest']
                    and done['assigned_hash_buckets'] == assigned
                    and done['partition_id'] == plan['partition_id'] and done['scope_key'] == plan['scope_key']
                    and done['queries'] == selected_input_rows[bucket]
                    and sum(p['rows'] for p in done['parts']) == selected_input_rows[bucket], 'Old projection binding differs')
            for part in done['parts']:
                Q.verify(part)
            projections.extend(done['parts']); continue
        read_parts(db, groups[bucket], 'all_candidates')
        db.execute('CREATE OR REPLACE TEMP VIEW candidates AS SELECT * FROM all_candidates WHERE ' + selected_predicate)
        if selected_input_rows[bucket] == 0:
            require(per_bucket_unique[bucket] == 0 and not known[bucket], 'Empty work bucket cannot have cached FP results')
            Q.write(bucket_manifest, {'parts': [], **binding, 'queries': 0})
            continue
        read_parts(db, known[bucket], 'scored')
        require(db.execute('SELECT count(*),count(DISTINCT ecfp4_2048_hex) FROM scored').fetchone()
                == (per_bucket_unique[bucket], per_bucket_unique[bucket]), 'Incomplete unique-FP exact coverage')
        require(db.execute('SELECT count(*) FROM candidates ANTI JOIN scored USING(ecfp4_2048_hex)').fetchone()[0] == 0,
                'Some actual candidates lack exact full-reference NN')
        sql = projection_sql(db, plan['reference_manifest']['sha256'])
        out = write_arrow(db, sql, root / 'projections' / bucket / ('attempt_' + uuid.uuid4().hex), bucket, journal, guard)
        require(sum(p['rows'] for p in out) == selected_input_rows[bucket],
                'Projection identity count amplified/lost')
        Q.write(bucket_manifest, {'parts': out, **binding, 'queries': selected_input_rows[bucket]})
        projections.extend(out)
    db.close(); journal.close(); guard.poll(force=True); lock.close()
    selected_rows = sum(selected_input_rows.values())
    require(sum(full_input_rows.values()) == filtered['eligible_molecules']
            and sum(p['rows'] for p in projections) == selected_rows
            and 0 <= selected_rows <= filtered['eligible_molecules'], 'Whole input and assigned partition projection EOF differ')
    value = {'schema': 'PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1', 'status': 'SHARD_COMPLETE',
             'producer_schema': 'PUBCHEM_PARTITIONED_EXACT_NOVELTY_SHARD_V1',
             'partition_id': plan['partition_id'], 'scope_key': plan['scope_key'],
             'assigned_hash_buckets': assigned, 'partition_rule': 'MD5_OF_CANONICAL_FP_HEX_TEXT_FIRST_NIBBLE',
             'filtered_pool_reference': plan['filtered_pool_reference'], 'reference': plan['reference_manifest'],
             'queries': selected_rows, 'whole_filtered_input_rows': filtered['eligible_molecules'],
             'unselected_population_rows': filtered['eligible_molecules'] - selected_rows,
             'full_input_rows_by_physical_FP_bucket': full_input_rows,
             'selected_input_rows_by_physical_FP_bucket': selected_input_rows,
             'complete_filtered_population_processed': False,
             'source_binding_reference': Q.reference(binding_path),
             'backend_adoption_reference': plan['backend_adoption_reference'],
             'reference_fingerprints': packed['fingerprints'], 'reference_keys': packed['keys'],
             'reference_counts': packed['counts'],
             'distinct_query_fingerprints': sum(per_bucket_unique.values()),
             'projection_parts': projections, 'fingerprint_recipe': RECIPE, 'algorithm': ALGORITHM,
             'reference_molecules': packed['molecules'], 'nearest_similarity_exact': True,
             'downstream_features_used': False, 'resource_plan': Q.reference(plan_path),
             'wall_seconds_this_attempt': time.monotonic()-began}
    if inverted:
        value.update(backend_implementation=plan['compiled_backend_implementation'],
                     equivalent_backend_continuation_reference=continuation_ref)
    Q.write(manifest_path, value)
    return value


def run_rank(plan_path):
    import duckdb
    plan, root, lock, guard = _start(plan_path)
    require(plan['schema'] == 'ALPHA_SHARDED_EXACT_RANK_PLAN_V1', 'Wrong rank plan')
    novelty = Q.load(Q.verify(plan['novelty_reference']))
    require(novelty['schema'] == 'PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1'
            and novelty['status'] == 'COMPLETE' and novelty['nearest_similarity_exact'] is True
            and novelty['reference_molecules'] == 1196122, 'Full exact novelty required')
    require(not (root / 'receipt.json').exists(), 'Reuse closed ranking output')
    began = time.monotonic(); db = duckdb.connect()
    configure_db(db, plan, root)
    read_parts(db, novelty['projection_parts'], 'pool')
    require(db.execute('SELECT count(*) FROM pool').fetchone()[0] == novelty['queries'], 'NN projection census differs')
    Q.verify(novelty['reference'])
    filtered = Q.load(Q.verify(novelty['filtered_pool_reference']))
    read_parts(db, filtered['candidates'], 'candidates')
    from ..exact_nn_cached_v1.typed_rank import check_membership
    check_membership(db, filtered['eligible_molecules'])
    require(db.execute('SELECT count(DISTINCT v1_reference_sha256),min(v1_reference_sha256) FROM pool').fetchone()
            == (1, novelty['reference']['sha256']), 'Actual frozen Common reference pin differs')
    guard.poll(force=True)
    adapted = HydrogenDomainDB(db)
    n = create_queues(adapted, seed=20261025, queue_size=5000000)
    require(adapted.extended_predicates == 1, 'Original H-only validation adapter differs')
    for name, query in (
            ('queues', 'SELECT * FROM queues ORDER BY stream,stream_rank'),
            ('batch1', 'SELECT * FROM queues WHERE stream_rank<=1250000 ORDER BY stream,stream_rank'),
            ('novelty_strata', 'SELECT heavy_stratum,element_combination,count(*) AS remaining_pubchem_population FROM n_candidates GROUP BY ALL ORDER BY ALL')):
        db.execute('COPY (' + query + ') TO ' + literal(root / (name + '.parquet')) + ' (FORMAT PARQUET,COMPRESSION ZSTD)')
        guard.poll(force=True)
    require(db.execute('SELECT stream,count(*),min(stream_rank),max(stream_rank) FROM queues WHERE stream_rank<=1250000 GROUP BY stream ORDER BY stream').fetchall()
            == [('N',1250000,1,1250000),('R',1250000,1,1250000)], 'Actual first batch differs')
    db.close(); guard.poll(force=True); lock.close()
    receipt = {'schema': 'expansion_nested_queues_v1', 'status': 'CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED',
               'novelty_receipt': plan['novelty_reference'], 'filtered_pool': novelty['filtered_pool_reference'],
               'pool_molecules': n, 'workers': plan['workers'], 'seed': 20261025,
               'queue_molecules_each': 5000000, 'first_batch_molecules_each': 1250000,
               'R_rule': 'uniform_sha256_full_identity',
               'N_rule': 'v1_only_lexicographic_novelty_with_exact_size_element_proportional_interleaving',
               'original_create_queues_source': Q.reference(Path(create_queues.__code__.co_filename)),
               'queues': Q.reference(root / 'queues.parquet'), 'batch1': Q.reference(root / 'batch1.parquet'),
               'strata': Q.reference(root / 'novelty_strata.parquet'), 'downstream_features_used': False,
               'resource_plan': Q.reference(plan_path), 'actual_parent': {'job_id': os.environ['SLURM_JOB_ID'], 'uid': os.getuid(), 'hostname': __import__('socket').gethostname(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}, 'wall_seconds': time.monotonic()-began}
    Q.write(root / 'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--stage', choices=['nn', 'rank'])
    parser.add_argument('--startup-proof', required=True)
    args = parser.parse_args()
    plan = Q.load(args.plan); proof = Q.load(args.startup_proof)
    require(proof['request']['producer_plan_reference'] == Q.reference(args.plan)
            and proof['uid'] == os.getuid() == 1264
            and str(proof['job_id']) == os.environ['SLURM_JOB_ID'], 'Actual allocated source/plan binding required')
    for path in Path(__file__).parent.glob('*.py'):
        require(Q.reference(path) in plan['code_references']
                and Q.reference(path) in proof['request']['source_references'], 'Actual sharded source must be startup pinned')
    if plan.get('compiled_backend_implementation') == 'INTEGER_INVERTED_CSR_PRIVATE_COPY_PROTOTYPE_V1':
        from .. import exact_nn_inverted_production_v1 as inverted_package
        for path in Path(inverted_package.__file__).parent.glob('*.py'):
            require(Q.reference(path) in plan['code_references']
                    and Q.reference(path) in proof['request']['source_references'], 'Actual inverted production adapter source pinned')
    stage = args.stage or ('nn' if plan['schema'] == 'ALPHA_SHARDED_EXACT_NOVELTY_PLAN_V1' else 'rank')
    (run_nn if stage == 'nn' else run_rank)(args.plan)


if __name__ == '__main__':
    main()
