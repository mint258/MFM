"""Full eligible typed pool to exact graph queries, preserving pool identities."""
from .runtime import allocated, frame, load, need, parent, pinned_frame, reference, verify, write_new
from .sql import SQLStopper, attempt, connection
from .projection import RECIPE, query_projection


def run(plan_path):
    plan = load(plan_path)
    need(plan['action'] == 'query_projection', 'Explicit typed query plan required')
    filtered = load(verify(plan['filtered_pool_receipt']))
    need(filtered['schema'] == 'expansion_filtered_columnar_pool_v1' and filtered['status'] == 'COMPLETE' and filtered['all_sources_all_splits_verified'] is True, 'Actual full all11 filtered pool required')
    path, before = pinned_frame(filtered['candidates'])
    with allocated(plan) as (stage, guard):
        final = stage / 'manifest.json'
        if final.exists():
            old = load(final)
            need(old['filtered_pool_receipt'] == plan['filtered_pool_receipt'], 'Closed query source differs')
            verify({k: old['projection'][k] for k in ('path', 'bytes', 'sha256')})
            return old
        out = attempt(stage); db = connection(out, plan['workers'], plan['duckdb_memory_bytes'])
        monitor = SQLStopper(db, guard.check)
        try:
            db.read_parquet(str(path)).create_view('eligible')
            projection = query_projection(db, 'eligible', out / 'eligible_query.jsonl', filtered['counts']['eligible_molecules'], guard.check)
            need(frame(path) == before, 'Whole-SHA-admitted eligible pool changed during query projection')
            guard.sample(); guard.check()
            result = {'schema': 'EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1', 'status': 'COMPLETE', 'fingerprint_recipe': RECIPE, 'targets_present': False, 'downstream_features_present': False, 'projection': projection, 'filtered_pool_receipt': plan['filtered_pool_receipt'], 'actual_parent': parent(), 'resource_plan': reference(plan_path), 'runtime': guard.receipt()}
            write_new(final, result)
            return result
        finally:
            monitor.close(); db.close()
